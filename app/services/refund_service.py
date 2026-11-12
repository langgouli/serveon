"""退款业务服务（F4）。"""
from __future__ import annotations

from datetime import datetime

from app.config import Config
from app.services.extract import extract_amount, extract_order_number, extract_refund_type
from app.services.llm import get_llm_client
from app.tools.logistics_tools import query_logistics
from app.tools.order_tools import query_order

_RTYPE_LABEL = {"REFUND_ONLY": "仅退款", "RETURN_REFUND": "退货退款", "EXCHANGE": "换货"}
_AFTERSALES_TYPES = set(_RTYPE_LABEL)


def precheck_eligibility(order_number: str, user_id: int) -> dict:
    """资格预检：规则引擎驱动，确定性判定（D9）。

    判定顺序：订单存在 → 身份归属 → 物流签收 → 签收分档 → 商品政策 → 金额阈值。
    返回 {result, block_type, reason, eligibility_data}。
    - result: passed / blocked / need_human
    - block_type: soft / hard（blocked 时）
    """
    # 查订单
    order = query_order(order_number)
    if not order:
        return {"result": "need_human", "reason": "order_not_found", "block_type": None, "eligibility_data": {}}

    # 身份校验
    if order["user_id"] != user_id:
        return {"result": "need_human", "reason": "not_owner", "block_type": None, "eligibility_data": {}}

    # 查物流
    logistics = query_logistics(order_number)

    # 物流未签收 → 软阻断（时机未到，非错误）
    if order["status"] != "signed":
        return {
            "result": "blocked",
            "block_type": "soft",
            "reason": "logistics_unsign",
            "eligibility_data": {
                "signed_at": None,
                "eta": (logistics or {}).get("estimated_delivery"),
            },
        }

    # 查签收时间
    signed_at = order["signed_at"]
    signed_dt = datetime.fromisoformat(signed_at)
    days = (datetime.now() - signed_dt).days

    # 签收时间分档：第16天起（>15天）硬阻断
    if days > Config.SIGN_DAY_TIER2:
        return {
            "result": "blocked",
            "block_type": "hard",
            "reason": "over_15_days",
            "eligibility_data": {"signed_at": signed_at, "days": days},
        }

    # 商品不支持退货 → 硬阻断
    if not order.get("support_return", True):
        return {
            "result": "blocked",
            "block_type": "hard",
            "reason": "not_support_return",
            "eligibility_data": {"signed_at": signed_at, "days": days},
        }

    # 金额超阈值 → 转人工
    if order["amount"] > Config.AMOUNT_THRESHOLD:
        return {
            "result": "need_human",
            "reason": "amount_over_threshold",
            "block_type": None,
            "eligibility_data": {"signed_at": signed_at, "days": days, "amount": order["amount"]},
        }

    # 资格通过
    return {
        "result": "passed",
        "reason": "",
        "block_type": None,
        "eligibility_data": {"signed_at": signed_at, "days": days, "amount": order["amount"]},
    }


# ---- 退款记录入库与分流（T7.3）----
_REFUND_RECORDS: dict[str, dict] = {}
_REFUND_BY_ORDER: dict[str, list[dict]] = {}  # 订单号 → 记录列表（订单维度查询）
_REFUND_COUNTER = 0


def reset_refund_memory() -> None:
    """清空内存退款记录（测试场景隔离用）。"""
    _REFUND_RECORDS.clear()
    _REFUND_BY_ORDER.clear()


def create_refund_record(order_number, user_id, refund_type, amount, reason) -> dict:
    """创建退款记录入库（不调外部API，D14）。"""
    global _REFUND_COUNTER
    _REFUND_COUNTER += 1
    refund_id = f"RF{_REFUND_COUNTER:06d}"
    record = {
        "refund_id": refund_id,
        "order_number": order_number,
        "user_id": user_id,
        "refund_type": refund_type,
        "amount": amount,
        "reason": reason,
        "status": Config.REFUND_STATUS_PENDING,
        "created_at": datetime.now().isoformat(),
    }
    _REFUND_RECORDS[refund_id] = record
    _REFUND_BY_ORDER.setdefault(order_number, []).append(record)
    return record


def get_refund_by_order(order_number: str, limit: int = 1) -> list[dict]:
    """按订单号查询售后记录（新会话/仅订单号查询口径）。"""
    recs = [dict(r) for r in _REFUND_BY_ORDER.get(order_number, [])]
    recs.reverse()  # 最新在前
    return recs[:limit]


def route_refund_type(refund_type) -> str:
    """退款类型分流：返回入库状态。"""
    if refund_type == "RETURN_REFUND":
        return Config.REFUND_STATUS_WAIT_RETURN
    if refund_type == "EXCHANGE":
        return Config.REFUND_STATUS_WAIT_SEND
    return Config.REFUND_STATUS_PENDING  # 仅退款


def refund_stage(refund_type) -> str:
    """退款阶段标识：驱动 refund_explain 话术分支（P0-R2）。"""
    if refund_type == "RETURN_REFUND":
        return "waiting_return"
    if refund_type == "EXCHANGE":
        return "exchange_reply"
    return "processing"  # 仅退款（含缺省）


def format_refund_detail(order, refund_type, amount, reason) -> str:
    """退款明细预览。"""
    steps = {
        "REFUND_ONLY": "退款方式：仅退款，原路退回至支付账户",
        "RETURN_REFUND": "退款方式：退货退款，寄回商品商家签收后原路退回",
        "EXCHANGE": "方式：换货，寄回原商品商家收到后发出新货",
    }
    head = {
        "EXCHANGE": "换货明细预览：",
        "RETURN_REFUND": "退货退款明细预览：",
        "REFUND_ONLY": "退款明细预览：",
    }.get(refund_type, "退款明细预览：")
    lines = [
        head,
        f"  订单号：{order['order_number']}",
        f"  退款类型：{refund_type}",
        f"  退款金额：¥{float(amount):.2f}",
        f"  退款原因：{reason}",
        steps.get(refund_type, steps["REFUND_ONLY"]),
        "预计1-3个工作日到账",
    ]
    return "\n".join(lines)


def get_refund_records() -> list[dict]:
    return list(_REFUND_RECORDS.values())


# ---- ① 新流程：模型解析 → 订单事实 → 支持性判定 ----
def parse_aftersales(msg: str, history: list | None = None) -> dict:
    """模型解析用户消息为售后申请要素（订单号 + 售后类型 + 金额）。

    LLM 为主，解析失败/字段非法时正则兜底；类型必须属于枚举，不猜测。
    """
    prompt = ""
    if history:
        prompt += "【最近对话】\n" + "\n".join(
            f"{m.get('role', '')}: {m.get('content', '')}" for m in history[-4:]
        ) + "\n"
    prompt += f"【当前消息】{msg}"

    parsed: dict = {"order_number": None, "request_type": None, "amount": None}
    try:
        r = get_llm_client().complete("aftersales_extract", prompt)
        data = r.get("data") if isinstance(r, dict) and isinstance(r.get("data"), dict) else (r if isinstance(r, dict) else {})
        no = str(data.get("order_number") or "").strip().upper()
        if no.startswith("ORD"):
            parsed["order_number"] = no
        rt = str(data.get("request_type") or "").strip().upper()
        if rt in _AFTERSALES_TYPES:
            parsed["request_type"] = rt
        amt = data.get("amount")
        if isinstance(amt, (int, float)) and not isinstance(amt, bool) and amt > 0:
            parsed["amount"] = float(amt)
    except Exception:
        pass  # 模型不可用/输出非法 → 正则兜底
    if not parsed["order_number"]:
        parsed["order_number"] = extract_order_number(msg)
    if not parsed["request_type"]:
        parsed["request_type"] = extract_refund_type(msg)
    if not parsed["amount"]:
        parsed["amount"] = extract_amount(msg)
    return parsed


def order_facts(order_number: str, user_id: int) -> dict:
    """订单事实：签收状态/签收天数/金额/特殊商品/预计送达（查询订单+物流）。"""
    order = query_order(order_number)
    if not order:
        return {"found": False, "reason": "order_not_found"}
    if order.get("user_id") != user_id:
        return {"found": False, "reason": "not_owner"}
    logistics = query_logistics(order_number) or {}
    signed_at = order.get("signed_at")
    days = None
    if signed_at:
        days = (datetime.now() - datetime.fromisoformat(signed_at)).days
    product = str(order.get("product", ""))
    category = str(order.get("category", ""))
    is_special = (
        category == "custom"
        or category == "virtual"
        or "虚拟" in product
        or not order.get("support_return", True)
    )
    return {
        "found": True,
        "order_number": order_number,
        "status": order.get("status"),
        "signed_at": signed_at,
        "days": days,
        "amount": float(order.get("amount", 0.0)),
        "product": product,
        "is_special": is_special,
        "eta": logistics.get("estimated_delivery"),
    }


def _supported(rtype: str, tier_note: str, facts: dict) -> dict:
    """支持：金额超阈值时升级为 needs_review（待人工审核）。"""
    out = {
        "result": "supported",
        "reason": "ok",
        "tier_note": tier_note,
        "evidence": None,
    }
    if facts["amount"] > Config.AMOUNT_THRESHOLD:
        out["result"] = "needs_review"
        out["reason"] = "amount_over_threshold"
    return out


def _unsupported(rtype: str, facts: dict, reason: str, needs_human: bool = True) -> dict:
    return {
        "result": "unsupported",
        "reason": reason,
        "tier_note": "",
        "evidence": None,
        "needs_human": needs_human,
    }


def evaluate_support(rtype: str, facts: dict) -> dict:
    """支持性判定（规则引擎，确定性）：类型 × 订单事实（签收/天数/金额/特殊商品）。

    判定矩阵：
      特殊商品（定制/虚拟）→ 三种类型一律不支持（《特殊商品政策》第13条）
      未签收 → 仅退款支持；退货退款/换货需签收
      签收 ≤15 天 → 退货退款支持（7-15 档需补充理由）；仅退款不支持（签收后仅退发货前）；
          换货 ≤7 天支持，>7 天不支持并引导改退货退款
      签收 >15 天 → 一律不支持
      金额 > 阈值 → supported 但升级 needs_review 转人工
    """
    if facts.get("is_special"):
        return _unsupported(rtype, facts, "special_goods")

    status = facts.get("status")
    if status != "signed":
        if rtype == "REFUND_ONLY" and status == "pending":
            # 发货前仅退款：无需寄回
            return _supported(rtype, "发货前仅退款，无需寄回商品，原路退回至支付账户", facts)
        return _unsupported(rtype, facts, "signed_required", needs_human=False)  # 时机未到，引导不转人工

    days = facts.get("days") or 0
    if days > Config.REFUND_WINDOW:
        return _unsupported(rtype, facts, "over_15_days")

    if rtype == "REFUND_ONLY":
        return _unsupported(rtype, facts, "refund_only_after_signed")

    if rtype == "EXCHANGE":
        if days > Config.EXCHANGE_SIGN_WINDOW:
            return _unsupported(rtype, facts, "exchange_over_7d")
        return _supported(rtype, "签收7天内支持换货，可换同款或同价位商品", facts)

    if rtype == "RETURN_REFUND":
        if days > Config.SIGN_DAY_TIER1:
            note = f"签收已第{days}天，属7-15天窗口，退货退款需补充退货理由"
            if days == Config.SIGN_DAY_TIER2:
                note += f"，第{Config.SIGN_DAY_TIER2 + 1}天起常规不支持退换"
        else:
            note = "签收7天内支持退货退款"
        if facts["amount"] == Config.AMOUNT_THRESHOLD:
            note += f"，金额刚好达到阈值{Config.AMOUNT_THRESHOLD:.0f}元，未超阈值无需人工审核"
        return _supported(rtype, note, facts)

    return _unsupported(rtype, facts, "unknown_type")


def unsupported_message(rtype: str, facts: dict, ev: dict) -> str:
    """不支持：政策引用（证明不能支持）+ 引导替代方式 + 人工入口。"""
    label = _RTYPE_LABEL.get(rtype, "退款")
    reason = ev["reason"]
    days = facts.get("days") or 0
    if reason == "special_goods":
        return (
            f"您的商品（{facts['product']}）属于定制/虚拟类特殊商品。"
            "根据《特殊商品政策》第13条（定制、虚拟商品签收后不支持退换），"
            "暂不提供退换办理。如需确认是否有例外方案，可联系人工客服，已为您转人工处理。"
        )
    if reason == "signed_required":
        eta = facts.get("eta") or ""
        eta_txt = f"，预计 {eta} 送达" if eta else ""
        return (
            f"物流尚未签收{eta_txt}。根据《退换货政策》第3条，退货退款与换货均需在签收后办理；"
            "如商品确实是发货前退款需求，可改为仅退款（仅退款仅支持发货前）。"
            "如有其他问题，可联系人工客服确认。"
        )
    if reason == "over_15_days":
        return (
            f"签收已第{days}天。根据《退换货政策》第3条（第16天起常规不支持退换），"
            f"暂不支持{label}。如需确认是否有例外方案，可联系人工客服，已为您转人工处理。"
        )
    if reason == "refund_only_after_signed":
        return (
            "签收后的售后政策不支持仅退款。根据《退换货政策》第3条，签收后请以退货退款方式申请；"
            "如需办理可改为退货退款，或联系人工客服确认是否有例外方案，已为您转人工处理。"
        )
    if reason == "exchange_over_7d":
        alt = (
            "如在签收15天内，可改申请退货退款"
            if days <= Config.REFUND_WINDOW
            else "退货退款也已超出签收15天窗口"
        )
        return (
            f"签收已第{days}天，超出换货窗口（签收7天内）。"
            "根据《换货政策》第11条（签收7天内支持换货），暂不支持换货；" + alt + "。"
            "如需确认是否有例外方案，可联系人工客服，已为您转人工处理。"
        )
    return (
        f"根据相关政策，您申请的{label}暂不支持办理。"
        "如需确认是否有例外方案，可联系人工客服，已为您转人工处理。"
    )


# 有效售后单判定：进行中/已办列（含处理中/待退货/待寄回/已完成）视为已有售后；取消态/不存在视为无售后（可重新发起）
def _active_statuses() -> set:
    from app.config import Config
    return {Config.REFUND_STATUS_PENDING, Config.REFUND_STATUS_WAIT_RETURN,
            Config.REFUND_STATUS_WAIT_SEND, Config.REFUND_STATUS_DONE}


def is_active_refund(status) -> bool:
    """有效售后单判定（供申请入口查单）：pending/wait_return/wait_send/done 视为有效售后单"""
    try:
        return bool(status) and str(status) in {str(s) for s in _active_statuses()}
    except Exception:
        return False


# 确认环节关键词（与 aftersales.py _CONFIRM_KEYWORDS/_CANCEL_KEYWORDS 同口径，兜底用）
_CONFIRM_KWS = ("确认", "好的", "可以", "同意")
_CANCEL_KWS = ("先不退", "先不换", "不退了", "不换了", "不要了", "不想要了", "取消", "算了", "不用了", "别处理")


def classify_confirm_action(msg: str, refund_info: dict | None = None) -> str:
    """售后单确认环节三分类：confirm（确认建单）/ cancel（取消）/ other（无关提问，交普通意图路由）。

    模型输出优先，解析失败关键词兜底；refund_info 提供订单号/类型/金额供模型参考。
    """
    kwargs = {
        "order_number": (refund_info or {}).get("order_number", ""),
        "request_type": (refund_info or {}).get("request_type", ""),
        "amount": (refund_info or {}).get("amount", ""),
    }
    try:
        r = get_llm_client().complete("confirm_classify", msg, **kwargs)
        action = str(r.get("action") or r.get("text") or "").strip().lower()
        if action in ("confirm", "cancel", "other"):
            return action
    except Exception:
        pass
    # 关键词兜底：取消词优先于确认词
    if any(k in msg for k in _CANCEL_KWS):
        return "cancel"
    if any(k in msg for k in _CONFIRM_KWS):
        return "confirm"
    return "other"


def confirm_reminder_message(refund_info: dict) -> str:
    """明细确认环节挂账提醒（离题后仍待确认时使用）。"""
    order_no = refund_info.get("order_number", "")
    label = {"EXCHANGE": "换货", "RETURN_REFUND": "退货退款",
             "REFUND_ONLY": "仅退款"}.get(refund_info.get("request_type", ""), "售后")
    amt = refund_info.get("amount")
    amt_txt = f"，明细金额¥{float(amt):.2f}" if amt is not None else ""
    return (
        f"另外提醒您：订单{order_no}的{label}售后申请{amt_txt}仍在等待您的确认"
        "——回复「确认」立即创建售后单，或回复「取消」终止本次申请。"
    )


def auto_cancel_message(refund_info: dict) -> str:
    """明细确认环节连续离题达上限 → 自动取消本次售后申请（不转人工）。"""
    order_no = refund_info.get("order_number", "")
    label = {"EXCHANGE": "换货", "RETURN_REFUND": "退货退款",
             "REFUND_ONLY": "仅退款"}.get(refund_info.get("request_type", ""), "售后")
    return (
        f"订单{order_no}的{label}售后申请确认环节已多次收到无关提问，"
        "按规则本次售后申请已为您自动取消。如有需要，可随时重新发起售后申请。"
    )


def unavailable_message(kind: str = "aftersales") -> str:
    """无法办理答复（信息不足/多次缺关键信息/参数多次不合法）：不转人工。"""
    if kind == "query":
        return "未能完成查询，请核对信息后重新提供。"
    return (
        "无法获取办理所需信息，本次售后申请未能办理；"
        "如需帮助请重新发起售后申请。"
    )


def review_message(rtype: str, facts: dict) -> str:
    """金额超阈值：待人工审核，不创建记录。"""
    label = _RTYPE_LABEL.get(rtype, "退款")
    return (
        f"您的{label}金额¥{facts['amount']:.2f}，超过人工审核阈值"
        f"{Config.AMOUNT_THRESHOLD:.0f}元，不能直接处理。已为您转人工审核处理。"
    )


# 规则兜底 unsupported 的 reason → 条款映射（渲染出口用，新口径不转人）
_UNSUPPORTED_POLICY_BY_REASON = {
    "special_goods": "《特殊商品政策》第13条：定制、虚拟商品签收后不支持退换",
    "over_15_days": "《退换货政策》第3条：签收后7天内支持退货退款，第16天起常规不支持退换",
    "exchange_over_7d": "《换货政策》第11条：签收7天内支持换货，超过7天窗口不支持换货",
    "signed_required": "《退换货政策》第3条：退货退款与换货需在签收后办理",
    "refund_only_after_signed": "《退换货政策》第3条：签收后不支持仅退款",
}


def render_unsupported_template(refund_info: dict, eligibility: dict | None = None,
                               facts: dict | None = None) -> str:
    """unsupported 出口机器定稿（新口径）：订单信息 + 政策支持情况 + 理由，不建单不转人。

    政策引用优先取模型 eligibility.policy_refs（dict 列表或字符串列表）；
    缺失时按 rules reason 映射条款。理由取 eligibility.reasoning。
    """
    facts = facts or {}
    order_no = refund_info.get("order_number") or facts.get("order_number", "")
    product = facts.get("product", "")
    amount = facts.get("amount")
    days = facts.get("days") or 0
    is_special = bool(facts.get("is_special"))
    label = {"EXCHANGE": "换货", "RETURN_REFUND": "退货退款",
             "REFUND_ONLY": "仅退款"}.get(refund_info.get("request_type", ""), "售后")
    amt_txt = f"¥{float(amount):.2f}" if amount is not None else ""
    kind_txt = "定制/虚拟类特殊商品" if is_special else "非特殊商品"
    facts_parts = [order_no]
    if product:
        facts_parts.append(product)
    if amt_txt:
        facts_parts.append(f"金额{amt_txt}")
    if facts.get("status") == "signed":
        facts_parts.append(f"已签收第{days}天")
    else:
        facts_parts.append("尚未签收")
    facts_parts.append(kind_txt)
    facts_line = "：".join(facts_parts)

    elig = eligibility or {}
    refs = elig.get("policy_refs") or []
    ref_lines: list[str] = []
    for r in refs:
        if isinstance(r, dict):
            title = r.get("title", "") or ""
            cid = r.get("clause_id", "") or ""
            content = r.get("content", "") or ""
            head = f"《{title}》第{cid}条" if title else (f"第{cid}条" if cid else "")
            if head and content:
                ref_lines.append(f"{head}：「{content}」")
            else:
                ref_lines.append(content or head)
        elif isinstance(r, str) and r:
            ref_lines.append(f"「{r}」")
    policy_block = "\n".join(ref_lines)
    if not policy_block:
        reason = elig.get("reason", "")
        reason_line = _UNSUPPORTED_POLICY_BY_REASON.get(reason)
        if reason_line and reason in ("over_15_days", "exchange_over_7d"):
            reason_line = f"{reason_line}（您已签收第{days}天）"
        policy_block = reason_line or "相关政策条款不支持本次申请"

    reasoning = (elig.get("reasoning") or "").strip()
    extra = f"（{reasoning}）" if reasoning and reasoning != "deterministic_guard" else ""
    reason_line = (
        f"综上，本次{label}申请不符合政策支持条件，未创建售后申请{extra}；"
        "如需办理可重新发起售后申请，或有异议可联系人工客服咨询。"
    )
    return (
        f"**①订单信息** {facts_line}\n"
        f"**②政策支持情况** {policy_block}\n"
        f"**③不支持理由** {reason_line}"
    )
