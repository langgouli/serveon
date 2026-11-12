"""实体抽取：从用户消息抽取订单号、退款类型、金额等实体。"""
from __future__ import annotations

import re
from typing import Optional

_ORDER_RE = re.compile(r"ORD\d+", re.IGNORECASE)


def extract_order_number(msg: str) -> Optional[str]:
    """抽取订单号（ORD 后跟数字），统一大写。"""
    m = _ORDER_RE.search(msg)
    return m.group().upper() if m else None


def extract_refund_type(msg: str) -> Optional[str]:
    """识别售后类型：仅退款/退货退款/换货。用户明确选择，不猜测。

    退换货申请类消息（"能退吗/想换个颜色"），"换"→换货，"退"→退货退款；
    仅退款需要"仅退款/直接退款"明确表达。
    """
    if "仅退款" in msg:
        return "REFUND_ONLY"
    # 「退货退款」优先于「换货」：避免「退换货政策」中「换货」子串误判类型
    if "退货退款" in msg or "退货" in msg or "退款" in msg or "能退" in msg or "想退" in msg or "请退" in msg or "退了" in msg or "申请退" in msg:
        return "RETURN_REFUND"
    if "换货" in msg or "更换" in msg or "换个" in msg or "换成" in msg:
        return "EXCHANGE"
    return None


def extract_amount(msg: str) -> Optional[float]:
    """抽取金额，支持 ¥299 / 299元 / 299块。"""
    m = re.search(r"[¥￥]\s*(\d+(?:\.\d+)?)", msg)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*元", msg)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*块", msg)
    if m:
        return float(m.group(1))
    return None
