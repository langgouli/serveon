"""v2 工具箱：7 个确定性工具 + 统一 JSON 信封（§3.5 协议）。

信封协议（每个工具只返回三种之一）：
  ① 成功       {ok: true,  status: "done",      data: {...}}
  ② 缺参追问   {ok: false, status: "need_args", missing_fields, ask, retry, max_retry}
  ③ 无法完成   {ok: false, status: "blocked"|"failed", reason, detail, needs_human}

工具内部全部复用现行实现（只读 import 不改）：query_order / query_logistics /
verify_identity / order_facts / evaluate_support / _advance_refund 状态机 /
generate_order_list / create_ticket 等。

每个工具统一签名 fn(args: dict, slots: dict, session_id: str) -> envelope；
需要更新 slot 的工具（advance_refund）在信封里带 "slots" 字段由调用方写回。
"""
from __future__ import annotations

import re
from typing import Any

from app.config import Config
from app.graph.nodes.aftersales import (
    _advance_refund,
    _find_order_record,
    _format_progress,
)
from app.graph.refund_subgraph import CURRENT_USER_ID
from app.services.order_slot import generate_order_list
from app.services.refund_service import get_refund_by_order, unavailable_message
from app.services.transfer_service import create_ticket, notify_user
from app.tools.logistics_tools import query_logistics
from app.utils.logger import log_event
from app.tools.mock_data import get_recent_orders, search_policies
from app.tools.order_tools import query_order

# 追问上限（v2 默认口径，设计文档 §0.2/§4）
ASK_ORDER_MAX = 3
ASK_TYPE_MAX = 3
ASK_IDENTITY_MAX = 3
# 参数校验模型侧重试上限（连续不合法打回 2 次，第 3 次走兜底答复）
PARAM_RETRY_MAX = 2

_ORDER_RE = re.compile(r"^ORD\d+$", re.IGNORECASE)


# ============================ 信封 ============================
def ok_envelope(data: dict | None = None, **kw) -> dict:
    body: dict[str, Any] = {"ok": True, "status": "done", "needs_human": False}
    if data is not None:
        body["data"] = data
    body.update(kw)
    return body


def need_args(missing: list[str], ask: str, retry: int = 1,
              max_retry: int = ASK_ORDER_MAX, status: str = "need_args") -> dict:
    return {
        "ok": False,
        "status": status,
        "needs_human": False,
        "missing_fields": missing,
        "ask": ask,
        "retry": min(retry, max_retry),
        "max_retry": max_retry,
    }


def blocked(reason: str, detail: str, needs_human: bool = True) -> dict:
    return {
        "ok": False,
        "status": "blocked",
        "needs_human": needs_human,
        "reason": reason,
        "detail": detail,
    }


# ============================ 工具实现 ============================

def tl_get_order_detail(args: dict, slots: dict, session_id: str) -> dict:
    """查订单明细。"""
    order_no = args.get("order_no") or ""
    if not order_no:
        return need_args(["order_no"], "请提供订单号（ORD 开头 + 数字，如 ORD001）。")
    if not _ORDER_RE.match(order_no):
        return need_args(["order_no"], "订单号格式应为 ORD 开头 + 数字（如 ORD001），请核对。")
    order = query_order(order_no)
    if not order:
        return blocked("order_not_found", "订单不存在或异常，无法查询。")
    if order.get("user_id") != CURRENT_USER_ID:
        return blocked("not_owner", "抱歉，您只能查询本人名下订单。", needs_human=False)
    data = dict(order)
    signed = order.get("signed_at")
    if signed:
        try:
            from datetime import datetime
            data["sign_days"] = (datetime.now() - datetime.fromisoformat(signed)).days
        except (ValueError, TypeError):
            data["sign_days"] = None
    return ok_envelope(data=data)


def tl_get_logistics(args: dict, slots: dict, session_id: str) -> dict:
    """查询物流轨迹/预计送达。"""
    order_no = args.get("order_no") or ""
    if not order_no:
        return need_args(["order_no"], "请提供订单号（ORD 开头 + 数字，如 ORD001）。")
    if not _ORDER_RE.match(order_no):
        return need_args(["order_no"], "订单号格式应为 ORD 开头 + 数字（如 ORD001），请核对。")
    order = query_order(order_no)
    if not order:
        return blocked("order_not_found", "订单不存在或异常，无法查询物流。")
    if order.get("user_id") != CURRENT_USER_ID:
        return blocked("not_owner", "抱歉，您只能查询本人名下订单的物流。", needs_human=False)
    logistics = query_logistics(order_no)
    if logistics is None:
        return ok_envelope(data={"order_number": order_no, "logistics": None,
                                 "note": "暂无物流轨迹记录。"})
    return ok_envelope(data={"order_number": order_no, "logistics": logistics})


def tl_get_user_orders(args: dict, slots: dict, session_id: str) -> dict:
    """拉取用户最近订单列表（无单号/多订单时用）。"""
    limit = args.get("limit") or 5
    try:
        limit = max(1, min(int(limit), 10))
    except (TypeError, ValueError):
        limit = 5
    orders = get_recent_orders(CURRENT_USER_ID, limit=limit)
    return ok_envelope(data={
        "orders": orders,
        "order_list_text": generate_order_list(CURRENT_USER_ID, limit=limit),
    })


def tl_get_refund_records(args: dict, slots: dict, session_id: str) -> dict:
    """按订单号查售后历史记录与进行中流程进度。"""
    order_no = args.get("order_no") or ""
    if not order_no:
        return need_args(["order_no"], "请提供订单号（ORD 开头 + 数字，如 ORD001）。")
    rec = None
    recs = get_refund_by_order(order_no)
    if recs:
        rec = recs[0]
    if rec is None:
        # 内存无记录 → 再查一次状态机索引（可能在途流程）
        rec = _find_order_record(session_id, order_no)
    if rec is None:
        return ok_envelope(data={"order_number": order_no, "records": [],
                                 "progress_text": "未查询到该订单的售后记录。"})
    return ok_envelope(data={
        "order_number": order_no,
        "records": [rec],
        "progress_text": _format_progress({
            "order_number": order_no,
            "refund_record": rec,
            "request_type": rec.get("refund_type"),
            "amount": rec.get("amount"),
            "_refund_status": rec.get("status", "done"),
        }),
    })


def tl_search_policy(args: dict, slots: dict, session_id: str) -> dict:
    """检索政策条款。

    模型按用户问题判断主题放入 topic（如'退换货'）；用 topic 检索政策库，
    命中返回条款原文；未命中返回统一未收录口径（不转人）。
    """
    topic = (args.get("topic") or "").strip()
    if not topic:
        return need_args(["topic"], "请将政策主题（如退换货/运费/到账/保修/换货/特殊商品）放入 topic 参数。")
    matches = search_policies(topic, top_k=3)
    if not matches:
        return ok_envelope(data={
            "topic": topic,
            "matches": [],
            "note": "暂无该类目相关政策，您可咨询退换货/运费/退款到账/保修/换货/特殊商品政策。",
        })
    return ok_envelope(data={
        "topic": topic,
        "matches": [{
            "title": m["title"], "clause_id": m["clause_id"], "content": m["content"],
            "category": m["category"],
        } for m in matches],
    })


def tl_advance_refund(args: dict, slots: dict, session_id: str) -> dict:
    """推进售后流程（复用现行 _advance_refund 状态机，语义不变）。

    参数不齐全时不阻断：内部状态机自行走 ask_order/ask_type/ask_identity 追问
    分支。返回信封 data 含 status / final_response / needs_human；
    need_args 缺 user_msg 时提醒模型补参。
    """
    user_msg = args.get("user_msg") or ""
    # 安全网：user_msg 必须为真实用户本轮原话。模型自拟（如"确认，办理吧"）会
    # 绕过确认/取消/离题计数，用 slot 里的真实消息覆盖。
    real_msg = (slots or {}).get("_last_user_msg") or user_msg
    user_msg = real_msg.strip() or user_msg
    if not user_msg:
        return need_args(["user_msg"], "请将用户本轮原话完整传入 user_msg 参数。")

    refund_info = dict(slots.get("refund_info", {}) or {})
    order_no = args.get("order_no") or refund_info.get("order_number")
    refund_info["order_number"] = order_no or None
    # request_type 不由模型传参覆盖：由状态机从 user_msg 提取（extract_refund_type）。
    # 否则确认环节模型传 request_type=EXCHANGE 会覆盖原类型，使类型切换检测失效、
    # 误将「我要换货ORD001」当 confirm 建单（O4 回归）。

    # M1：受理模型判定参数 eligibility（暂透传暂存，M2 状态机消费）
    # verdict=supported → 进确认链路；unsupported → 模型按模板输出不支持答复
    _judge_eligibility = None
    eff = args.get("eligibility")
    if isinstance(eff, dict):
        verdict = str(eff.get("verdict") or "").strip().lower()
        if verdict in ("supported", "unsupported"):
            _judge_eligibility = {
                "verdict": verdict,
                "evidence": eff.get("evidence", ""),
                "policy_refs": eff.get("policy_refs", []) or [],
                "reasoning": eff.get("reasoning", ""),
            }
            refund_info["_eligibility_param"] = _judge_eligibility
            # 无效负结论标记：证据与引用均空 → M2 将打回（M1 只设标）
            if verdict == "unsupported" and not str(eff.get("evidence") or "").strip() and not _judge_eligibility.get("policy_refs"):
                refund_info["_judge_invalid"] = True
    # unsupported 答复模板（§5.4）：工具固定给模型的结构提示，模型照此作答不自造条款号
    _unsupported_template = ""
    if _judge_eligibility and _judge_eligibility["verdict"] == "unsupported":
        _unsupported_template = (
            "不支持答复结构：①订单信息（订单编号+关键事实：状态/签收天数/金额/是否特殊商品）"
            "②政策支持情况（引用 policy_refs 中至少一条条款原文）"
            "③不支持理由（综合上述订单事实与政策依据给出一句）"
        )

    # 会话历史用于跨轮上下文抽取（第1轮"我要退款"→第2轮只回订单号时，
    # parse_aftersales(msg, history) 需要历史消息才能保留 request_type，避免误判缺类型）
    from app.react_v2.memory import store as _store
    work_state = {
        "user_message": user_msg,
        "session_id": session_id,
        "conversation_history": _store.get_history(session_id),
        "entity_slots": {"refund_info": refund_info},
        "processing_results": [],
    }
    result = _advance_refund(work_state, refund_info)

    # need_args：判定缺参打回（M2）；失败计数已写回 refund_info 供下轮续计
    out_slots = dict(slots)
    out_slots["refund_info"] = refund_info
    if refund_info.get("order_number"):
        out_slots["current_order"] = refund_info["order_number"]
    if result.get("status") == "need_args":
        _nc = refund_info.get("_judge_miss_count", 0)
        envelope = need_args(["eligibility"], result.get("ask", "请传入 eligibility 判定参数。"),
                             retry=min(_nc, Config.JUDGE_MISS_MAX), max_retry=Config.JUDGE_MISS_MAX)
        envelope["slots"] = out_slots
        return envelope

    final_response = (result.get("final_response") or "").strip()
    needs_human = bool(result.get("needs_human", False))
    status = refund_info.get("_refund_status", "")

    # 静默场景（canceled/done 且用户未问进度）：给模型确定的收口提示，防止模型自编
    # unsupported 状态不补话术：final_response 留空，让模型按 unsupported_template 写正文
    if not final_response:
        if status == "canceled":
            final_response = "好的，本次售后申请已为您取消。如有需要，可随时重新发起。"
        elif status in ("done", "blocked"):
            final_response = "已为您按流程处理完毕，如需其他帮助请随时告知。"

    data = {
        "status": status,
        "final_response": final_response,
        "needs_human": needs_human,
        "hint": "按 final_response 原样转述用户；needs_human=true 时按 T2 转人工。",
    }
    if status == "ask_order":
        # 缺单号 + 政策咨询混合场景：先答政策再列列表，防止模型直接转人/丢失政策答复
        data["hint"] = ("若用户消息含政策咨询意图（政策/规定/条款），先调用 search_policy 作答政策，"
                        "再输出订单列表引导提供订单号；订单列表必须原样完整转述。")
    if _judge_eligibility:
        data["eligibility"] = _judge_eligibility
    if _unsupported_template:
        data["unsupported_template"] = _unsupported_template
        data["hint"] += " 本轮判定为「不支持」：请按 unsupported_template 结构输出给用户，本轮结束售后流程，不建单不转人。"
    envelope = ok_envelope(data=data)
    envelope["slots"] = out_slots  # 调用方写回
    if needs_human:
        envelope.update({
            "ok": False, "status": "blocked", "needs_human": True,
            "reason": "refund_flow_needs_human", "detail": final_response,
        })
        envelope["data"] = data
    return envelope


def tl_transfer_to_human(args: dict, slots: dict, session_id: str) -> dict:
    """触发转人工（T1/T2/T3）：创建工单并返回通知话术。

    安全网：售后诉求缺单号（无在途流程 + 消息含售后词 + 无订单号）→ 不建工单，
    返回订单列表引导（避免模型直接转人代替 ask_order 列表引导）。
    """
    # 安全网：售后诉求缺单号 → 列表引导不转人
    refund_info = (slots or {}).get("refund_info") or {}
    if not refund_info:
        msg = (slots or {}).get("_last_user_msg") or ""
        if msg and any(k in msg for k in ("退货", "退款", "换货", "换个", "售后")) and not re.search(r"ORD\d+", msg, re.I):
            return ok_envelope(data={
                "status": "ask_order",
                "final_response": generate_order_list(CURRENT_USER_ID),
            }, needs_human=False)
    handoff = {
        "会话摘要": [],
        "用户消息": [],
        "当前订单": (slots or {}).get("current_order", ""),
        "退款记录": [],
        "情绪": "",
        "触发原因": args.get("reason") or "manual",
        "AI建议": "",
    }
    ticket_id = create_ticket(handoff, args.get("reason") or "manual")
    notice = notify_user(ticket_id)
    return ok_envelope(data={"ticket_id": ticket_id, "notice": notice},
                      needs_human=True)


# ============================ 调度表 ============================
_TOOL_IMPLS = {
    "get_order_detail": tl_get_order_detail,
    "get_logistics": tl_get_logistics,
    "get_user_orders": tl_get_user_orders,
    "get_refund_records": tl_get_refund_records,
    "search_policy": tl_search_policy,
    "advance_refund": tl_advance_refund,
    "transfer_to_human": tl_transfer_to_human,
}


def _tool_required_fields(name: str) -> list[str]:
    """从 TOOL_DEFS 提取必填字段。"""
    for d in TOOL_DEFS:
        fn = d.get("function", {})
        if fn.get("name") == name:
            return list(fn.get("parameters", {}).get("required", []))
    return []


def _validate_args(name: str, args: dict, slots: dict) -> dict | None:
    """工具参数校验（模型侧重试）：不合法 → need_args 打回；连续 PARAM_RETRY_MAX+1 次
    仍不合法 → 兜底答复（无法办理/查询失败），不转人。

    返回 None 表示校验通过；返回 dict 为应直接返回的信封。
    """
    missing: list[str] = []
    for f in _tool_required_fields(name):
        v = args.get(f)
        if v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and not v):
            missing.append(f)
    # 枚举值校验（如 request_type）
    for d in TOOL_DEFS:
        fn = d.get("function", {})
        if fn.get("name") == name:
            props = fn.get("parameters", {}).get("properties", {})
            rt = props.get("request_type", {})
            if "request_type" in args and rt.get("enum") and args["request_type"] not in rt["enum"]:
                missing.append("request_type")
    if not missing:
        slots["_param_invalid_count"] = 0
        return None
    cnt = int(slots.get("_param_invalid_count", 0) or 0) + 1
    slots["_param_invalid_count"] = cnt
    if cnt > PARAM_RETRY_MAX:
        # 连续第 3 次不合法 → 兜底答复，不再给模型重试机会（不转人）
        kind = "query" if name in ("get_order_detail", "get_logistics",
                                   "get_user_orders", "get_refund_records") else "aftersales"
        msg = unavailable_message(kind)
        return ok_envelope(data={"status": "unavailable", "final_response": msg})
    ask_map = {
        "order_no": "请提供订单号（ORD 开头 + 数字，如 ORD001）。",
        "query": "请把用户原话完整传入 query 参数。",
        "user_msg": "请将用户本轮原话完整传入 user_msg 参数。",
        "reason": "请提供转人原因简述。",
    }
    ask = "；".join(dict.fromkeys(ask_map.get(f, f) for f in missing))
    return need_args(missing, ask, retry=min(cnt, PARAM_RETRY_MAX), max_retry=PARAM_RETRY_MAX)


def run_tool(name: str, arguments: dict, slots: dict, session_id: str) -> dict:
    """按名执行工具（信封返回）。

    双层重试：①参数校验（模型侧重试：need_args 打回，连续超限兜底答复）；
    ②执行异常（系统侧重试：非 advance_refund 自动重试最多 2 次，仍失败转人；
    advance_refund 的建单/入库/话术在 refund_subgraph 节点内已重试 2 次，异常直接转人）。
    """
    fn = _TOOL_IMPLS.get(name)
    if fn is None:
        log_event("-", "v2_unknown", input=f"name={name!r}", output="")
        return blocked("unknown_tool", f"未知工具：{name}")
    # ① 参数校验（模型侧重试）
    invalid = _validate_args(name, dict(arguments or {}), slots)
    if invalid is not None:
        return invalid
    if name == "advance_refund":
        try:
            return fn(dict(arguments or {}), slots, session_id) or {
                "ok": False, "status": "failed", "reason": "empty_result",
            }
        except Exception as e:
            log_event(session_id, "v2_tool_exception", input=f"name={name}",
                      output=f"{type(e).__name__}: {e}")
            return blocked("tool_exception", f"工具执行异常：{type(e).__name__}: {e}")
    # ② 系统侧重试（其他工具：执行异常自动重试最多 2 次）
    last_exc: Exception | None = None
    for attempt in range(PARAM_RETRY_MAX + 1):
        try:
            return fn(dict(arguments or {}), slots, session_id) or {
                "ok": False, "status": "failed", "reason": "empty_result",
            }
        except Exception as e:
            last_exc = e
            log_event(session_id, "v2_tool_retry", input=f"name={name} attempt={attempt+1}",
                      output=f"{type(e).__name__}: {e}")
    return blocked("tool_exception",
                   f"工具执行异常（已重试 {PARAM_RETRY_MAX} 次）：{type(last_exc).__name__}: {last_exc}")


# ============================ OpenAI tools 注册描述（§3.5.1） ============================

TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "get_order_detail",
            "description": (
                "查询订单明细：状态/金额/商品/签收时间/是否特殊商品。"
                "order_no 必填（ORD 开头+数字，如 ORD001）。"
                "没有订单号时，先从【会话背景】的用户订单/当前订单里取；"
                "取不到就调 get_user_orders 列列表让用户选，绝不猜订单号。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_no": {"type": "string", "description": "订单号，ORD 开头+数字（如 ORD001），必填"},
                },
                "required": ["order_no"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_logistics",
            "description": (
                "查询订单物流轨迹/预计送达/异常。order_no 必填（ORD 开头+数字）。"
                "签收状态、预计送达只取工具返回，不得自行推断。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_no": {"type": "string", "description": "订单号，ORD 开头+数字（如 ORD001），必填"},
                },
                "required": ["order_no"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_orders",
            "description": (
                "拉取用户最近订单列表，供无单号/多订单时让用户选择。"
                "可一次返回多单；调用后必须把工具返回的 order_list_text 原样完整转述给用户。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "返回条数，默认 5"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_refund_records",
            "description": (
                "按订单号查询售后历史记录与进行中流程进度。无记录返回空列表（非报错）。"
                "order_no 必填（ORD 开头+数字）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_no": {"type": "string", "description": "订单号，ORD 开头+数字，必填"},
                },
                "required": ["order_no"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_policy",
            "description": (
                "检索退换货/运费/退款到账/保修/换货/特殊商品六类政策条款。"
                "调用时把从用户问题判断的政策主题放入 topic 参数（如'退换货'），"
                "不要传用户原话。未匹配到条款时工具返回统一口径"
                "「暂无该类目相关政策，您可咨询退换货/运费/退款到账/保修/换货/特殊商品政策」，"
                "原样转述即可，不要套用通用条款、不要编造条款编号。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string",
                              "description": "政策主题（从用户问题判断，如退换货/运费/到账/保修/换货/特殊商品），必填"},
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "advance_refund",
            "description": (
                "推进售后流程（退货退款/仅退款/换货）：取订单→识别类型→资格判定→"
                "明细预览→确认/取消/离题处理，全部在工具内部完成，你只传参+转述。"
                "user_msg 必填，传用户本轮原话（确认/取消词靠它判定）。"
                "order_no/request_type 可不传；缺参时工具内部走对应追问分支。"
                "返回的信封含 status/final_response/needs_human；needs_human=true 按 T2 转人工。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_no": {"type": "string",
                                 "description": "订单号（ORD 开头+数字），可省略，缺省由工具内部追问"},
                    "request_type": {
                        "type": "string",
                        "enum": ["REFUND_ONLY", "RETURN_REFUND", "EXCHANGE"],
                        "description": "售后类型；不明确时可省略，由工具追问",
                    },
                    "user_msg": {"type": "string", "description": "用户本轮原话，必填"},
                },
                "required": ["user_msg"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_to_human",
            "description": (
                "触发转人工（仅 3 种：用户点名转人工、工具返回 needs_human、金额超 2000 元售后）。"
                "其余限制判定（特殊商品/超期/未收录等）一律按不支持答复输出，不调用本工具。"
                "用户只是寒暄/闲聊/问笑话/越界内容（无业务诉求）时绝不调用本工具。"
                "返回的通知话术（已为您转接人工客服…工单号…）原样转述给用户，"
                "且若本轮已检索到政策/订单结果，必须先把这些业务答复转述给用户，再给工单话术。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "触发原因简述，如 多次未提供订单号"},
                },
                "required": ["reason"],
            },
        },
    },
]
