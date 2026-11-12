"""售后 agent 节点（F4）：手动驱动退款子图。

流程：①模型解析（订单号+售后类型）→ 订单事实 → 已有有效售后单校验 → 支持性判定
     → 支持：collect_info → preview（明细预览）→ 确认环节三分类：
         confirm（确认）→ create_refund_record；cancel（取消）→ 终态取消；
         other（离题）→ 挂账提醒，离题计数不清零，满3次自动取消本次申请
     → 不支持：政策引用回复（不建档）；超阈值：转人工审核
每轮推进到下一个需要用户输入的节点：自动节点（facts/evaluate/collect）在一轮内链式执行，
只在 ask_order / ask_type / ask_identity / preview(请求确认) / reask / blocked / canceled / done 处停下。
退款进度保存在 entity_slots.refund_info._refund_status，跨轮保留。

入口路由（用户三条规则）：
- 类型未识别 → 追问（R1）
- 类型已知 / 收到状态查询消息 → 判断该订单是否已在售后流程：
  在进行中 → 回显当前阶段进度，不驱动新流程；已有记录 → 回显记录状态；
  全新 → 从零走售后流程
- 售后状态查询只按订单号，无需售后单号（AS/RF 单号不识别，引导提供 ORD 订单号）
- 申请入口查单：该订单已有有效售后单（pending/wait_return/wait_send/done）→ 回显售后单信息
  并说明无法再发起新的售后（不转人工，回复可继续咨询）
"""
from __future__ import annotations

from app.config import Config
from app.graph.refund_subgraph import (
    CURRENT_USER_ID,
    ask_identity,
    ask_order,
    collect_info,
    create_refund_record_node,
    extract_order,
    preview_detail,
    verify_identity_node,
)
from app.services.extract import extract_order_number, extract_refund_type
from app.services.refund_service import (
    auto_cancel_message,
    classify_confirm_action,
    confirm_reminder_message,
    evaluate_support,
    get_refund_by_order,
    is_active_refund,
    order_facts,
    parse_aftersales,
    review_message,
    render_unsupported_template,
    unsupported_message,
)
from app.utils.logger import log_event, node_log

_CONFIRM_KEYWORDS = ["确认", "好的", "可以", "同意"]
_CANCEL_KEYWORDS = ["先不退", "先不换", "不退了", "不换了", "不要了", "不想要了", "取消", "算了", "不用了", "别处理"]

# 政策提问词：含这些词时不算类型词（"退换货政策"的"换货"不触发类型切换，防 O5/O8 劫持）
_POLICY_WORDS = ("政策", "规定", "条款")

# 退款进度查询关键词：命中时 done 状态直接回显记录
_PROGRESS_KEYWORDS = ["进度", "状态", "到账", "怎么样", "如何", "办了吗", "结果", "什么情况", "申请过", "申请了", "不是已经"]

# 进行中的售后流程状态（非终态）：命中状态查询 → 回显当前阶段，不重新驱动
_IN_PROGRESS_STATUSES = {
    "ask_order", "ask_type", "ask_identity",
    "verifying", "verifying_done", "collect_info", "preview",
    "previewing", "previewing_done",
}

# 进行中状态 → 阶段文案 + 下一步
_STAGE_TEXT: dict[str, tuple[str, str]] = {
    "ask_order": ("等待确认订单号", "请回复需要办理售后的订单号（ORD 开头）。"),
    "ask_type": ("等待确认售后类型", "请回复：仅退款 / 退货退款 / 换货。"),
    "ask_identity": ("等待确认账号信息", "请回复确认，才能继续为您办理。"),
    "verifying": ("订单核验中", "正在查询订单签收状态与售后资格。"),
    "verifying_done": ("资格核验中", "正在判定签收时间/商品类型/金额是否符合售后条件。"),
    "collect_info": ("所需信息收集中", "请说明售后原因与金额（金额默认全额，可指定部分金额）。"),
    "preview": ("明细已准备", "退款/换货明细已生成，请回复确认后创建申请。"),
    "previewing": ("明细确认环节", "退款/换货明细已再次展示，回复确认后创建申请。"),
    "previewing_done": ("明细确认环节", "退款/换货明细已展示，回复确认后创建申请。"),
}


def _order_not_found_block(refund_info: dict, session_id: str) -> dict:
    """订单不存在时直接无法办理答复（不转人工）。"""
    log_event(session_id, "refund_step", input="status=order_not_found", output="")
    refund_info["_block_response"] = "订单不存在或异常，无法办理本次申请。"
    refund_info["_block_needs_human"] = False
    refund_info["_refund_status"] = "blocked"
    return {"final_response": refund_info["_block_response"], "needs_human": False, "status": "done"}


def _blocked(refund_info: dict, response: str, needs_human: bool = True) -> dict:
    refund_info["_block_response"] = response
    refund_info["_block_needs_human"] = needs_human
    refund_info["_refund_status"] = "blocked"
    return {"final_response": response, "needs_human": needs_human, "status": "done"}


def _format_in_progress(refund_info: dict) -> str:
    """进行中的售后流程 → 回显当前阶段与下一步（仅按订单号定位，不驱动新流程）。"""
    order_no = refund_info.get("order_number", "")
    rtype = refund_info.get("request_type") or ""
    label = {"EXCHANGE": "换货", "RETURN_REFUND": "退货退款", "REFUND_ONLY": "仅退款"}.get(rtype, "售后")
    stage, next_step = _STAGE_TEXT.get(refund_info.get("_refund_status", ""), ("流程处理中", "请继续等待"))
    detail = ""
    amt = refund_info.get("amount")
    if amt is not None and refund_info.get("_refund_status", "").startswith("preview"):
        detail = f"，明细金额¥{float(amt):.2f}（按您的指定）"
    return (
        f"已为您查询订单 {order_no} 的售后流程状态：{stage}（{label}申请）{detail}。{next_step}"
    )


def _unwrap_record(rec: dict) -> dict:
    """内存索引存的是 create_refund_record 原始记录，MySQL 按退款单行存储；统一取出退款记录体。"""
    inner = rec.get("refund_record")
    return inner if isinstance(inner, dict) and inner else rec


def _find_order_record(session_id: str, order_no: str) -> dict:
    """按订单号找售后记录：内存索引（含本进程内新建）→ MySQL 跨会话；无则返回 None。"""
    from app.services.refund_service import get_refund_by_order
    recs = get_refund_by_order(order_no, limit=1)
    if not recs:
        from app.tools.mysql_store import get_store
        recs = get_store().get_refund_by_order(order_no, limit=1)
    return _unwrap_record(recs[0]) if recs else None


def _status_query_guard(msg: str, refund_info: dict, session_id: str) -> dict | None:
    """规则 2/3：用户只问售后进度/状态 → 仅按订单号查（槽位→记录），回显后不驱动新流程。

    - 该订单在进行中 → 回显当前阶段
    - 该订单已有记录（done 等）/ 新会话仅凭订单号 → 回显记录状态
    - 无流程无记录（含订单不存在）→ 返回 None，继续走售后申请流程（订单不存在/AS 单号
      会在流程内按各自的兜底处理）
    """
    if not any(k in msg for k in _PROGRESS_KEYWORDS):
        return None
    if any(k in msg for k in _CONFIRM_KEYWORDS) or any(k in msg for k in _CANCEL_KEYWORDS):
        return None  # 确认/取消语义 → 继续驱动流程（R7 取消出口不受影响）
    order_no = extract_order_number(msg) or refund_info.get("order_number")
    if not order_no:
        return None  # 未指明订单 → 由流程追问/引导
    status = refund_info.get("_refund_status", "")
    if order_no == refund_info.get("order_number"):
        if status in _IN_PROGRESS_STATUSES:
            return {"final_response": _format_in_progress(refund_info)}
        if status == "done" and refund_info.get("refund_record"):
            return {"final_response": _format_progress(refund_info)}
        return None  # canceled/blocked 等 → 交状态分派（原取消/阻断行为不变）
    if status in ("", "extracting", "canceled", "blocked"):
        rec = _find_order_record(session_id, order_no)
        if rec:
            view = {
                "order_number": order_no,
                "refund_record": rec,
                "request_type": rec.get("refund_type"),
                "amount": rec.get("amount"),
                "_refund_status": rec.get("_refund_status", ""),
            }
            return {"final_response": _format_progress(view)}
    return None


def _canceled_progress_message(order_no: str) -> str:
    """已取消订单问进度 → 回显取消状态（按订单号定位，无需售后单号）。"""
    return (
        f"该订单{order_no}的售后申请已为您取消"
        "（按订单号定位，无需售后单号），没有进行中的进度；"
        "如需办理请重新发起售后申请。"
    )


def _try_restore_refund(state: dict, refund_info: dict) -> dict:
    """内存槽位缺失时（服务重启/新会话）从记忆索引或 MySQL 恢复退款记录。"""
    if refund_info:
        return refund_info
    msg = state["user_message"]
    session_id = state.get("session_id", "-")
    # 订单号可能在本条消息，也可能在历史消息（"我刚才申请过"）中
    order_no = extract_order({"user_message": msg}).get("order_number")
    if not order_no:
        history = state.get("conversation_history") or []
        text = "\n".join(h.get("content", "") for h in history[-4:])
        order_no = extract_order({"user_message": text}).get("order_number")
    if not order_no:
        return refund_info
    rec = _find_order_record(session_id, order_no)
    if rec:
        refund_info = {
            "order_number": order_no,
            "_refund_status": rec.get("_refund_status", "done"),
            "refund_record": rec,
            "request_type": rec.get("refund_type"),
            "amount": rec.get("amount"),
            "reason": rec.get("reason"),
        }
        log_event(session_id, "refund_restore", input="memory-or-mysql", output=f"order={order_no} status={refund_info['_refund_status']}")
    return refund_info


def _format_progress(refund_info: dict) -> str:
    """done 状态 + 进度查询 → 回显退款/换货记录。"""
    rec = refund_info.get("refund_record", {}) or {}
    order_no = refund_info.get("order_number") or rec.get("order_number", "")
    amount = refund_info.get("amount") if refund_info.get("amount") is not None else rec.get("amount", 0)
    status = refund_info.get("_refund_status") or rec.get("status", "processing")
    rtype = refund_info.get("request_type") or rec.get("refund_type", "")
    p = "换货" if rtype == "EXCHANGE" else "退款"
    lines = [
        "已为您查询换货/退款进度：",
        f"  订单号：{order_no}",
        f"  {p}类型：{rtype}",
        f"  {p}金额：¥{float(amount):.2f}",
        f"  {p}状态：{status}",
    ]
    if rtype == "EXCHANGE":
        lines.append("  商家收到寄回商品后将发出新货，换货完成后更新状态为已完成。")
    elif "1-3" not in lines[-1]:
        lines.append("  预计1-3个工作日到账，退款将原路退回至支付账户。")
    return "\n".join(lines)


def _advance_refund(state: dict, refund_info: dict) -> dict:
    """推进售后子流程到下一个用户输入节点。"""
    msg = state["user_message"]
    session_id = state.get("session_id", "-")
    history = state.get("conversation_history") or []
    work_state = dict(state)
    work_slots = dict(state.get("entity_slots", {}) or {})
    work_slots["refund_info"] = refund_info
    work_state["entity_slots"] = work_slots
    result: dict = {}

    # 规则 2/3：进度查询消息 → 仅按订单号查在途/已建档记录，回显进度后停下（每轮只判一次，
    # 放在入口：避免流程链式推进（解析→核验）中途被截流挡住订单不存在等事实检查）
    guard = _status_query_guard(msg, refund_info, session_id)
    if guard is not None:
        return {"final_response": guard["final_response"], "status": "done"}

    loop_guard = 0
    while True:
        loop_guard += 1
        if loop_guard > 20:  # 死循环安全阀：赔偿推进异常时兜底退出
            log_event(session_id, "refund_loop_warn", input=msg, output="cap")
            break
        status = refund_info.get("_refund_status", "extracting")
        # 状态推进记录（流程可回放）
        log_event(
            session_id, "refund_step",
            input=f"status={status}",
            output=msg,
        )
        # 同步 work_state，供 refund_subgraph 节点函数读取
        if refund_info.get("order_number"):
            work_state["order_number"] = refund_info["order_number"]
        if refund_info.get("user_id"):
            work_state["user_id"] = refund_info["user_id"]
        work_state["request_type"] = refund_info.get("request_type")
        work_state["amount"] = refund_info.get("amount")
        work_state["reason"] = refund_info.get("reason")
        work_state["tier_note"] = refund_info.get("tier_note")

        # canceled/blocked 终态：用户明确提出新售后申请 → 重置重来（保留订单号）；
        # 含进度词的查询不算新申请（交 canceled 分支回显已取消状态）
        # 注意："退换货政策是什么"里含"换货"但属政策提问，不算类型词，防劫持（O5 回归）
        has_policy_question = any(k in msg for k in _POLICY_WORDS)
        has_type_word = any(k in msg for k in ("仅退款", "退货退款", "换货", "更换")) and not has_policy_question
        restart = has_type_word or (bool(extract_order_number(msg)) and not any(k in msg for k in _PROGRESS_KEYWORDS))
        if status in ("canceled", "blocked", "unsupported") and restart:
            for _k in ("amount", "reason", "request_type", "tier_note", "refund_record",
                       "_ask_confirm_count", "_ask_type_count", "_ask_order_count", "eligibility"):
                refund_info.pop(_k, None)
            refund_info["_refund_status"] = "extracting"
            status = "extracting"

        # 在途流程 + 当前消息换订单号 → 重置流程走新订单（不受 A 在途流程影响），不重走 match 逻辑
        # 用消息中最后一个 ORD 号作为目标（样例里旧单在前、目标单在后，首个正则号是旧单会死循环）
        import re as _re
        msg_order = _re.findall(r"ORD\d+", msg, _re.IGNORECASE)
        msg_order = msg_order[-1].upper() if msg_order else None
        if (msg_order and refund_info.get("order_number") and msg_order != refund_info["order_number"]
                and status not in ("canceled", "blocked", "unsupported")):
            for _k in ("amount", "reason", "request_type", "tier_note",
                       "_ask_confirm_count", "_ask_type_count", "_ask_order_count", "eligibility"):
                refund_info.pop(_k, None)
            refund_info["order_number"] = msg_order
            work_state["order_number"] = msg_order
            refund_info["_refund_status"] = "extracting"
            status = "extracting"

        if status == "canceled":
            # 统一回显取消口径（含进度问）：机器定稿，避免空 final_response 让模型复读
            result = {
                "final_response": _canceled_progress_message(
                    refund_info.get("order_number", ""),
                ),
                "needs_human": False,
            }
            break

        if status == "blocked" and not refund_info.get("_block_response"):
            break

        if status in ("extracting", "ask_order", "ask_type"):
            # ① 模型解析：订单号 + 售后类型（LLM 为主，正则兜底）
            parsed = parse_aftersales(msg, history)
            if parsed.get("order_number"):
                refund_info["order_number"] = parsed["order_number"]
            if parsed.get("request_type"):
                refund_info["request_type"] = parsed["request_type"]
                refund_info["_ask_type_count"] = 0
            if parsed.get("amount"):
                refund_info["amount"] = parsed["amount"]
            if not refund_info.get("order_number"):
                refund_info["_refund_status"] = "ask_order"
                ask_count = refund_info.get("_ask_order_count", 0) + 1
                refund_info["_ask_order_count"] = ask_count
                if ask_count >= Config.ASK_ORDER_MAX:
                    result = _blocked(refund_info, "多次未能获取订单号，无法继续办理本次申请。如需帮助请重新发起售后申请。",
                                      needs_human=False)
                    break
                result = ask_order(work_state)
                break
            # 入口查单校验（新设计）：该订单已有有效售后单 → 回显售后单信息 + 拒办（不转人工，可继续咨询）
            rec = _find_order_record(session_id, refund_info["order_number"])
            if rec and is_active_refund(rec.get("status")):
                view = {
                    "order_number": refund_info["order_number"],
                    "refund_record": rec,
                    "request_type": rec.get("refund_type"),
                    "amount": rec.get("amount"),
                    "_refund_status": rec.get("status", ""),
                }
                result = {
                    "final_response": _format_progress(view)
                    + "该订单已有有效售后单，无法再发起新的售后；如有其他疑问可以随时告诉我。",
                    "needs_human": False,
                    "status": "done",
                }
                break
            # 类型未明不阻塞：先查订单事实（不存在/非本人优先暴露），再补类型追问
            refund_info["_refund_status"] = "verifying"

        elif status == "verifying":
            r = verify_identity_node(work_state)
            if r.get("status") == "order_not_found":
                result = _order_not_found_block(refund_info, session_id)
                break
            if r.get("status") == "not_owner":
                result = _blocked(refund_info, "您不是该订单归属人，无法继续办理本次申请。",
                                  needs_human=False)
                break
            if r.get("user_id"):
                refund_info["user_id"] = r["user_id"]
                refund_info["_refund_status"] = "verifying_done"
            else:
                refund_info["_refund_status"] = "ask_identity"

        elif status == "ask_identity":
            r = verify_identity_node(work_state)
            if r.get("status") == "order_not_found":
                result = _order_not_found_block(refund_info, session_id)
                break
            if r.get("status") == "not_owner":
                result = _blocked(refund_info, "您不是该订单归属人，无法继续办理本次申请。",
                                  needs_human=False)
                break
            if r.get("user_id"):
                refund_info["user_id"] = r["user_id"]
                refund_info["_refund_status"] = "verifying_done"
            else:
                result = ask_identity(work_state)
                break

        elif status == "verifying_done":
            # 订单事实查询（守卫材料 + 兜底判据复用）——存在/归属不变动
            facts = order_facts(refund_info["order_number"], refund_info.get("user_id", CURRENT_USER_ID))
            if not facts.get("found"):
                if facts.get("reason") == "order_not_found":
                    result = _order_not_found_block(refund_info, session_id)
                    break
                result = _blocked(
                    refund_info,
                    "您不是该订单归属人，无法继续办理本次申请。",
                    needs_human=False,
                )
                break
            rtype = refund_info.get("request_type")
            if not rtype:
                # R1：订单事实已明确，仅类型未明 → 追问（超限转人工）
                refund_info["_refund_status"] = "ask_type"
                ask_count = refund_info.get("_ask_type_count", 0) + 1
                refund_info["_ask_type_count"] = ask_count
                if ask_count >= Config.ASK_REFUND_TYPE_MAX:
                    result = _blocked(refund_info, "多次未明确售后类型，无法继续办理本次申请。如需帮助请重新发起售后申请。",
                                      needs_human=False)
                    break
                result = {
                    "final_response": "请告知您需要的售后类型：仅退款/退货退款/换货。",
                    "status": "done",
                }
                break
            # M2：判定主体移交模型——先消费模型传入的 eligibility 参数；
            # 缺参打回（首次）/兜底规则判据（第 2 次起）
            elig = refund_info.get("_eligibility_param")
            if not elig:
                miss = refund_info.get("_judge_miss_count", 0) + 1
                refund_info["_judge_miss_count"] = miss
                if miss > Config.JUDGE_MISS_MAX:
                    # 兜底：模型无法产出判定 → 回退规则判据（行为同现状，source=rules）
                    ev = evaluate_support(rtype, facts)
                    refund_info["eligibility"] = {
                        "result": ev["result"], "reason": ev["reason"], "source": "rules",
                    }
                    work_state["eligibility"] = refund_info["eligibility"]
                    if ev["result"] == "supported":
                        refund_info["tier_note"] = ev.get("tier_note", "")
                        refund_info["_refund_status"] = "collect_info"
                        refund_info["_judge_miss_count"] = 0
                        continue  # 直接流转收集环节，不再 need_args 打回
                    elif ev["result"] == "needs_review":
                        result = _blocked(
                            refund_info,
                            review_message(rtype, facts),
                        )
                        break
                    else:
                        # 新口径：rules 兜底判 unsupported → 渲染出口（不建单不转人）
                        refund_info["eligibility"]["reason"] = ev["reason"]
                        refund_info["eligibility"]["policy_refs"] = []
                        refund_info["eligibility"]["reasoning"] = ev.get("reason", "")
                        refund_info["_refund_status"] = "unsupported"
                        result = {
                            "final_response": render_unsupported_template(
                                refund_info, refund_info["eligibility"], facts),
                            "needs_human": False,
                        }
                        break
                # need_args 打回（eligibility 缺失）
                refund_info["_judge_miss_count"] = miss
                result = {
                    "status": "need_args",
                    "ask": "请先调用 get_order_detail 与 search_policy 取证，完成资格判定后将 eligibility 参数传入。",
                }
                break
            # 消费模型判定：写入 eligibility（source=model），清除临时参数
            refund_info["eligibility"] = {
                "verdict": elig["verdict"],
                "evidence": elig.get("evidence", ""),
                "policy_refs": elig.get("policy_refs", []),
                "reasoning": elig.get("reasoning", ""),
                "source": "model",
            }
            work_state["eligibility"] = refund_info["eligibility"]
            refund_info.pop("_eligibility_param", None)
            if elig["verdict"] == "unsupported":
                if refund_info.get("_judge_invalid"):
                    refund_info.pop("_judge_invalid", None)
                    refund_info["_judge_miss_count"] = refund_info.get("_judge_miss_count", 0) + 1
                    result = {
                        "status": "need_args",
                        "ask": "不支持判定必须给出 evidence（订单事实）与至少一条 policy_refs（条款引用），请补齐后重新传入 eligibility。",
                    }
                    break
                refund_info["_refund_status"] = "unsupported"
                # 机器定稿渲染出口（新口径：订单信息+政策支持+理由，不建单不转人）
                result = {
                    "final_response": render_unsupported_template(
                        refund_info, refund_info.get("eligibility"), facts),
                    "needs_human": False,
                }
                break
            # deterministic_guard：硬事实与 supported 判定矛盾（特殊商品/超期）→
            # 渲染不支持答复出口（不建单不转人）
            if facts.get("is_special") or (rtype != "REFUND_ONLY" and (facts.get("days") or 0) > Config.REFUND_WINDOW):
                refund_info["eligibility"]["reasoning"] = "deterministic_guard"
                refund_info["eligibility"]["source"] = "deterministic_guard"
                refund_info["eligibility"]["reason"] = "special_goods" if facts.get("is_special") else "over_15_days"
                refund_info["eligibility"]["policy_refs"] = []
                refund_info["_refund_status"] = "unsupported"
                result = {
                    "final_response": render_unsupported_template(
                        refund_info, refund_info["eligibility"], facts),
                    "needs_human": False,
                }
                break
            # 金额守卫：supported 但金额超阈值 → 转人工审核（不建单）
            _amt = facts.get("amount")
            if _amt is not None and _amt > Config.AMOUNT_THRESHOLD:
                refund_info["eligibility"]["reasoning"] = "amount_over_threshold"
                refund_info["eligibility"]["source"] = "deterministic_guard"
                result = _blocked(refund_info, review_message(rtype, facts))
                break
            # 判定支持 → 进确认链路 collect_info（循环下一轮处理）
            refund_info["_refund_status"] = "collect_info"
            refund_info["_judge_miss_count"] = 0
            continue

        elif status == "collect_info":
            r = collect_info(work_state)
            new_info = r.get("entity_slots", {}).get("refund_info", {})
            refund_info.update({k: v for k, v in new_info.items() if k != "_refund_status"})
            refund_info["_refund_status"] = "preview"

        elif status == "preview":
            r = preview_detail(work_state)
            refund_info["_refund_status"] = "previewing_done"
            result = r
            break

        elif status in ("previewing_done", "previewing"):
            # 类型切换新规：确认环节用户发出不同类型的新申请（如预览退货退款后说
            # "我要换货ORD001"）→ 按换货重新走资格判定+明细预览，不得当作确认建档
            # 政策提问（"退换货政策是什么"含"换货"）不算类型切换（O5/O8 劫持防护）
            msg_rtype = extract_refund_type(msg)
            has_policy_q = any(k in msg for k in _POLICY_WORDS)
            if (msg_rtype and msg_rtype != refund_info.get("request_type")
                    and not has_policy_q
                    and not any(k in msg for k in _CONFIRM_KEYWORDS)):
                refund_info["request_type"] = msg_rtype
                refund_info["_ask_confirm_count"] = 0
                refund_info["_refund_status"] = "collect_info"
                continue
            # 确认环节三分类（模型判断为主、关键词兜底；取消词优先于确认词）
            action = classify_confirm_action(msg, refund_info)
            if action == "cancel":
                # R7：撤消退换货 → 终态确认取消，不再反复追问
                refund_info["_refund_status"] = "canceled"
                refund_info["_ask_confirm_count"] = 0
                # 作废在途记录：恢复/回显统一按取消口径（TR45：不再报 wait_return）
                refund_info["refund_record"] = None
                refund_info["_canceled_at"] = True
                result = {
                    "final_response": "好的，本次售后申请已为您取消。如有需要，可随时重新发起。",
                    "status": "done",
                }
                break
            # R1：建档前必须有明确 request_type（防御分支：正常到确认环节类型已定）
            if not refund_info.get("request_type"):
                rtype = extract_refund_type(msg)
                if rtype:
                    refund_info["request_type"] = rtype
                    refund_info["_ask_type_count"] = 0
                refund_info["_refund_status"] = "previewing"
                if not refund_info.get("request_type"):
                    ask_count = refund_info.get("_ask_type_count", 0) + 1
                    refund_info["_ask_type_count"] = ask_count
                    if ask_count >= Config.ASK_REFUND_TYPE_MAX:
                        result = _blocked(refund_info, "多次未明确售后类型，无法继续办理本次申请。如需帮助请重新发起售后申请。",
                                          needs_human=False)
                        break
                    result = {
                        "final_response": "请告知您需要的售后类型：仅退款/退货退款/换货。",
                        "status": "done",
                    }
                    break
            if action == "confirm":
                r = create_refund_record_node(work_state)
                refund_info["refund_record"] = r["refund_record"]
                refund_info["_refund_status"] = "done"
                result = r
                break
            # other：离题（无关提问）→ 计数不清零；满上限自动取消，否则挂账提醒
            ask_count = refund_info.get("_ask_confirm_count", 0) + 1
            refund_info["_ask_confirm_count"] = ask_count
            if ask_count >= Config.ASK_CONFIRM_MAX:
                refund_info["_ask_confirm_count"] = 0
                refund_info["_refund_status"] = "canceled"
                result = {
                    "final_response": auto_cancel_message(refund_info),
                    "status": "done",
                }
                break
            result = {
                "final_response": confirm_reminder_message(refund_info),
                "status": "done",
            }
            break

        elif status == "blocked":
            result = {
                "final_response": refund_info.get("_block_response", ""),
                "needs_human": refund_info.get("_block_needs_human", False),
            }
            break

        elif status == "done":
            # 已完成：用户问进度 → 回显退款记录；重新发起 → 引导（不转人工）；纯确认/闲聊 → 空
            if any(k in msg for k in _PROGRESS_KEYWORDS):
                result = {"final_response": _format_progress(refund_info)}
            elif has_type_word:
                result = {
                    "final_response": _format_progress(refund_info)
                    + "\n该订单已有完成的售后记录，无法重新发起；如有其他疑问可以随时告诉我。",
                    "needs_human": False,
                }
            else:
                result = {"final_response": ""}
            break

        elif status == "unsupported":
            # unsupported 非新申请的兜底出口（新申请已由 restart 重置）
            result = {
                "final_response": "该订单暂不支持办理售后申请；如需办理，请重新发起售后申请。",
                "needs_human": False,
            }
            break

        else:
            break

    return result


@node_log
def aftersales_agent(state: dict) -> dict:
    """售后 agent：每轮推进售后子流程到下一个用户输入节点。"""
    slots = state.get("entity_slots", {}) or {}
    refund_info = dict(slots.get("refund_info", {}) or {})
    # 内存槽位缺失（重启）→ 从 MySQL 恢复已有退款记录
    refund_info = _try_restore_refund(state, refund_info)
    result = _advance_refund(state, refund_info)
    slots["refund_info"] = refund_info
    return {
        "final_response": result.get("final_response", ""),
        "needs_human": result.get("needs_human", False),
        "entity_slots": slots,
        "refund_record": refund_info.get("refund_record"),
        "eligibility": refund_info.get("eligibility", {}),
    }
