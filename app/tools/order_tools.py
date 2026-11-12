"""订单查询工具。"""
from __future__ import annotations

from app.tools.mysql_store import get_store


def query_order(order_number: str) -> dict | None:
    return get_store().get_order(order_number)
