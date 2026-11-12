"""转人工服务（F5）。"""
from __future__ import annotations

from app.config import Config

_TICKETS: dict[str, dict] = {}
_TICKET_COUNTER = 0

_T1_KEYWORDS = ["转人工", "找客服", "人工客服", "转接人工", "人工处理", "要人工"]


def check_transfer_trigger(state: dict) -> dict:
    """检测转人工触发条件（保守触发 T1/T2/T3）。

    - T1 用户主动要求
    - T2 AI 无法解决（needs_human / 资格预检异常 / 意图置信度低）
    - T3 金额超阈值

    保守原则：情绪激动不直接触发。
    """
    msg = state.get("user_message", "")
    eligibility = state.get("eligibility", {}) or {}
    needs_human = state.get("needs_human", False)
    intent = state.get("intent_result", {}) or {}

    # T1 用户主动要求
    if any(k in msg for k in _T1_KEYWORDS):
        return {"triggered": True, "reason_code": "T1"}

    # T3 金额超阈值
    if eligibility.get("reason") == "amount_over_threshold":
        return {"triggered": True, "reason_code": "T3"}

    # T2 AI 无法解决
    if needs_human:
        return {"triggered": True, "reason_code": "T2"}
    if not intent.get("intents") and intent.get("confidence", 1.0) < 0.3:
        return {"triggered": True, "reason_code": "T2"}

    # 保守：情绪激动不直接触发
    return {"triggered": False, "reason_code": ""}


def _risk_tags(state: dict) -> list:
    tags = []
    elig = state.get("eligibility", {}) or {}
    amount = elig.get("eligibility_data", {}).get("amount")
    if amount and amount > Config.AMOUNT_THRESHOLD:
        tags.append("金额超阈值")
    emotion = state.get("emotion_result", {}) or {}
    if emotion.get("emotion") == "angry":
        tags.append("情绪激动")
    return tags


def _history_summary(state: dict) -> list:
    hist = state.get("conversation_history", []) or []
    return [m.get("content", "") for m in hist[-3:]]


def build_handoff_package(state: dict) -> dict:
    """生成结构化交接包（7 字段）。"""
    slots = state.get("entity_slots", {}) or {}
    return {
        "会话摘要": {
            "诉求": (state.get("intent_result", {}) or {}).get("intents", []),
            "已收集信息": slots.get("refund_info", {}),
        },
        "识别意图": (state.get("intent_result", {}) or {}).get("intents", []),
        "资格预检结果": state.get("eligibility", {}),
        "风险标签": _risk_tags(state),
        "历史摘要": _history_summary(state),
        "触发原因": state.get("_transfer_reason", ""),
        "建议处理方向": "参考会话摘要与资格预检结果",
    }


def create_ticket(handoff: dict, reason_code: str) -> str:
    """创建工单，记录触发原因。"""
    global _TICKET_COUNTER
    _TICKET_COUNTER += 1
    ticket_id = f"TK{_TICKET_COUNTER:06d}"
    _TICKETS[ticket_id] = {"handoff": handoff, "reason": reason_code}
    return ticket_id


def get_tickets() -> list[dict]:
    return list(_TICKETS.values())


def notify_user(ticket_id: str) -> str:
    return f"已为您转接人工客服，工单号{ticket_id}，请稍候。"
