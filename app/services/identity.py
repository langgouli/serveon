"""身份校验服务（越权防护）。"""
from __future__ import annotations

from app.tools.mysql_store import get_store


def verify_identity(user_id: int, order_number: str) -> dict:
    """校验 user_id 与订单归属一致。

    返回 {ok, reason}：reason 为 order_not_found / not_owner / ""。
    """
    order = get_store().get_order(order_number)
    if not order:
        return {"ok": False, "reason": "order_not_found"}
    if order["user_id"] != user_id:
        return {"ok": False, "reason": "not_owner"}
    return {"ok": True, "reason": ""}
