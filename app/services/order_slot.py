"""订单号获取三级策略与订单列表选择。"""
from __future__ import annotations

from app.services.extract import extract_order_number
from app.tools.mysql_store import get_store


def get_order_number(msg: str, processing_results: list | None, slots: dict):
    """订单号获取三级策略（设计文档第 4 节）。

    1. 当前消息中有明确订单号 → 直接使用
    2. 前序意图的处理结果 → 复用数据
    3. 槽位 current_order → 跨轮次继承
    4. 无 → need_select（列表让用户选）

    返回 (order_number, status)：
    - status=None：成功获取
    - status="need_select"：需列表选择
    """
    # 1. 当前消息
    order_no = extract_order_number(msg)
    if order_no:
        return order_no, None

    # 2. 前序意图结果
    for r in processing_results or []:
        if r.get("intent") in ("order", "logistics") and r.get("order_number"):
            return r["order_number"], None

    # 3. 槽位 current_order
    current = slots.get("current_order")
    if current:
        return current, None

    # 4. 无
    return None, "need_select"


def generate_order_list(user_id: int, limit: int = 5) -> str:
    """生成最近订单列表让用户选择（设计文档第 4 节格式）。"""
    orders = get_store().get_recent_orders(user_id, limit)
    lines = ["您有以下近期订单，请选择要查询的订单编号："]
    for o in orders:
        lines.append(f"  {o['order_number']}  {o['product']}    ¥{o['amount']}    {o['status']}")
    lines.append("请回复订单编号（如 ORD005）：")
    return "\n".join(lines)
