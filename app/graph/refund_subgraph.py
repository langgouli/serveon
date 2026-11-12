"""退款子图节点（F4）。

流程：extract_order → verify_identity → precheck_eligibility
      → (soft_block/hard_block/transfer_human) 或 collect_info
      → preview_detail → (reask) → create_refund_record
"""
from __future__ import annotations

from app.config import Config
from app.services.extract import extract_amount, extract_refund_type
from app.services.identity import verify_identity
from app.services.llm import get_llm_client
from app.services.order_slot import generate_order_list, get_order_number
from app.services.refund_service import (
    create_refund_record,
    format_refund_detail,
    precheck_eligibility,
    route_refund_type,
    refund_stage,
)
from app.tools.order_tools import query_order
from app.utils.logger import log_event

CURRENT_USER_ID = 1001


def extract_order(state: dict) -> dict:
    """获取订单号（三级策略）。"""
    msg = state["user_message"]
    slots = state.get("entity_slots", {})
    processing = state.get("processing_results", []) or []
    order_no, _ = get_order_number(msg, processing, slots)
    if order_no:
        return {"order_number": order_no, "status": "extracting_done"}
    return {"order_number": None, "status": "extracting"}


def ask_order(state: dict) -> dict:
    return {"final_response": generate_order_list(CURRENT_USER_ID), "status": "asking_order"}


def verify_identity_node(state: dict) -> dict:
    order_no = state.get("order_number")
    if not order_no:
        return {"status": "verifying"}
    ident = verify_identity(CURRENT_USER_ID, order_no)
    if ident["ok"]:
        return {"user_id": CURRENT_USER_ID, "status": "verifying_done"}
    if ident["reason"] == "order_not_found":
        return {"user_id": CURRENT_USER_ID, "status": "order_not_found"}
    if ident["reason"] == "not_owner":
        return {"status": "not_owner"}
    return {"status": "verifying"}


def ask_identity(state: dict) -> dict:
    return {"final_response": "请确认您的账号信息。", "status": "asking_identity"}


def precheck_node(state: dict) -> dict:
    order_no = state["order_number"]
    user_id = state.get("user_id", CURRENT_USER_ID)
    elig = precheck_eligibility(order_no, user_id)
    return {"eligibility": elig, "status": "prechecking_done"}


def soft_block(state: dict) -> dict:
    """物流未签收软阻断：告知预计可退时间。"""
    elig = state["eligibility"]
    eta = elig["eligibility_data"].get("eta")
    msg = f"物流未签收，预计{eta}送达，签收后7天内可申请退款。您可以等待或加急。"
    return {"final_response": msg, "needs_human": False, "status": "done"}


def hard_block(state: dict) -> dict:
    """硬阻断：告知政策限制，转人工。"""
    reason = (state.get("eligibility") or {}).get("reason", "")
    label = "换货" if (state.get("request_type") or "") == "EXCHANGE" else "退款"
    msg_by_reason = {
        "over_15_days": f"签收已超过15天，常规不支持{label}。已为您转人工处理。",
        "not_support_return": f"该商品为定制/虚拟类商品，按政策签收后不支持退换。已为您转人工处理，看是否有例外方案。",
    }
    final = msg_by_reason.get(reason, f"根据政策，该订单暂不支持{label}退货处理，已为您转人工处理。")
    return {
        "final_response": final,
        "needs_human": True,
        "status": "done",
    }


def collect_info(state: dict) -> dict:
    """收集退款原因/类型/金额，写入 refund_info（跨轮保留）。"""
    msg = state["user_message"]
    slots = state.get("entity_slots", {})
    refund_info = dict(slots.get("refund_info", {}))

    # 关键词抽取仅兜底缺失类型，不得覆盖已有 request_type
    # （否则 msg 先提"退货退款单(ORD002)"再提"换货"时会把换货回退成退货退款）
    rtype = extract_refund_type(msg)
    if rtype and not refund_info.get("request_type"):
        refund_info["request_type"] = rtype

    if not refund_info.get("reason"):
        refund_info["reason"] = msg

    amount = extract_amount(msg)
    if amount:
        refund_info["amount"] = amount

    order = query_order(state["order_number"])
    if not refund_info.get("amount"):
        refund_info["amount"] = order["amount"]  # 默认全额

    new_slots = dict(slots)
    new_slots["refund_info"] = refund_info

    return {
        "request_type": refund_info.get("request_type"),
        "reason": refund_info.get("reason"),
        "amount": refund_info.get("amount"),
        "entity_slots": new_slots,
        "status": "collecting_done",
    }


def preview_detail(state: dict) -> dict:
    """明细预览，请求用户确认。"""
    order = query_order(state["order_number"])
    rtype = state.get("request_type")
    amount = state.get("amount")
    reason = state.get("reason")
    if not rtype:
        return {"final_response": "您选择仅退款、退货退款还是换货？", "status": "previewing"}
    detail = format_refund_detail(order, rtype, amount, reason)
    if state.get("tier_note"):
        detail += f"\n  （{state['tier_note']}）"
    return {"final_response": detail + "\n请回复确认。确认后才会创建申请，AI不会在您确认前执行退款/换货。", "status": "previewing_done"}


def reask(state: dict) -> dict:
    """明细未确认重问，超 3 次转人工。"""
    ask_count = state.get("_ask_confirm_count", 0) + 1
    if ask_count > Config.ASK_CONFIRM_MAX:
        return {"final_response": "多次未确认，已转人工。", "needs_human": True, "status": "done"}
    return {
        "final_response": "请确认退款信息，回复确认。",
        "_ask_confirm_count": ask_count,
        "status": "previewing",
    }


def create_refund_record_node(state: dict) -> dict:
    """创建退款记录入库 + 类型分流 + 通知（系统操作：建单/入库/话术重试最多 2 次）。"""
    order_no = state["order_number"]
    user_id = state.get("user_id", CURRENT_USER_ID)
    rtype = state.get("request_type")
    amount = state.get("amount")
    reason = state.get("reason")
    session_id = state.get("session_id", "-")

    def _build() -> dict:
        record = create_refund_record(order_no, user_id, rtype, amount, reason)
        record["status"] = route_refund_type(rtype)
        llm = get_llm_client()
        explain = llm.complete(
            "refund_explain", "",
            order_number=order_no, amount=amount,
            request_type=rtype, stage=refund_stage(rtype),
            tier_note=state.get("tier_note", ""),
        )
        # 退款记录持久化 MySQL（内存槽位仅供当前进程，落库才能跨重启查询）
        from app.tools.mysql_store import get_store
        get_store().save_refund({
            "session_id": session_id,
            "order_number": order_no,
            "user_id": user_id,
            "request_type": rtype,
            "amount": amount,
            "reason": reason,
            "_refund_status": "done",
            "refund_record": record,
        })
        return {"refund_record": record, "final_response": explain["text"], "status": "done"}

    last_exc: Exception | None = None
    for attempt in range(3):  # 首次 + 重试 2 次
        try:
            return _build()
        except Exception as e:
            last_exc = e
            log_event(session_id, "refund_create_retry",
                      input=f"attempt={attempt+1}", output=f"{type(e).__name__}: {e}")
    raise last_exc


def route_refund_step(state: dict) -> str:
    """退款子图条件路由：按 status 分发下一节点。"""
    status = state.get("status", "")
    order_no = state.get("order_number")
    user_id = state.get("user_id")
    elig = state.get("eligibility", {}) or {}

    if status == "extracting" and not order_no:
        return "ask_order"
    if status == "asking_order":
        return "extract_order"
    if status == "verifying" and not user_id:
        return "ask_identity"
    if status == "order_not_found":
        return "hard_block"
    if status == "asking_identity":
        return "verify_identity_node"
    if status == "verifying_done":
        return "precheck_node"
    if status == "prechecking_done":
        if elig.get("result") == "blocked":
            return "hard_block" if elig.get("block_type") == "hard" else "soft_block"
        if elig.get("result") == "need_human":
            return "hard_block"  # 通用转人工（主图处理）
        return "collect_info"
    if status == "collecting_done":
        return "preview_detail"
    if status == "previewing_done":
        msg = state.get("user_message", "")
        if any(k in msg for k in ["确认", "好的", "可以", "同意"]):
            return "create_refund_record_node"
        return "reask"
    if status == "previewing":
        return "reask"
    return "hard_block"  # 兜底


def build_refund_graph():
    """构建退款子图 StateGraph。"""
    from langgraph.graph import END, StateGraph

    from app.graph.state import RefundState

    g = StateGraph(RefundState)
    g.add_node("extract_order", extract_order)
    g.add_node("ask_order", ask_order)
    g.add_node("verify_identity_node", verify_identity_node)
    g.add_node("ask_identity", ask_identity)
    g.add_node("precheck_node", precheck_node)
    g.add_node("soft_block", soft_block)
    g.add_node("hard_block", hard_block)
    g.add_node("collect_info", collect_info)
    g.add_node("preview_detail", preview_detail)
    g.add_node("reask", reask)
    g.add_node("create_refund_record_node", create_refund_record_node)

    g.set_entry_point("extract_order")
    for node in [
        "extract_order", "ask_order", "verify_identity_node", "ask_identity",
        "precheck_node", "collect_info", "preview_detail", "reask",
    ]:
        g.add_conditional_edges(node, route_refund_step)
    g.add_edge("soft_block", END)
    g.add_edge("hard_block", END)
    g.add_edge("create_refund_record_node", END)
    return g.compile()
