"""T1.3 验收：Mock 数据查询与检索。"""
from app.tools.mock_data import (
    get_order,
    get_orders_by_user,
    get_recent_orders,
    get_logistics,
    search_policies,
)


def test_get_order_found():
    o = get_order("ORD001")
    assert o is not None
    assert o["user_id"] == 1001
    assert o["amount"] == 299.0
    assert o["signed_at"] is not None


def test_get_order_not_found():
    assert get_order("NOT_EXIST") is None


def test_get_orders_by_user():
    orders = get_orders_by_user(1001)
    nos = {o["order_number"] for o in orders}
    assert {"ORD001", "ORD002", "ORD003", "ORD004", "ORD005", "ORD007", "ORD010", "ORD011", "ORD012"} == nos  # ORD010/011 边界档、ORD012 发货前
    assert "ORD006" not in nos  # 他人订单


def test_get_orders_by_user_other():
    orders = get_orders_by_user(2001)
    assert len(orders) == 1
    assert orders[0]["order_number"] == "ORD006"


def test_get_recent_orders_limit():
    recent = get_recent_orders(1001, limit=5)
    assert len(recent) == 5


def test_get_logistics_signed():
    lg = get_logistics("ORD001")
    assert lg is not None
    assert lg["tracks"][0]["status"] == "已签收"
    assert lg["abnormal"] is False


def test_get_logistics_unsign():
    lg = get_logistics("ORD004")
    assert lg["estimated_delivery"] is not None
    assert lg["tracks"][0]["status"] == "运输中"


def test_get_logistics_abnormal():
    lg = get_logistics("ORD003")
    assert lg["abnormal"] is True


def test_search_policies_return_policy():
    results = search_policies("7天退换")
    assert len(results) > 0
    assert results[0]["title"] == "退换货政策"
    assert "第" not in results[0]["title"]  # 条款号在 content


def test_search_policies_freight():
    results = search_policies("运费谁承担")
    assert results[0]["title"] == "运费政策"


def test_search_policies_arrival():
    results = search_policies("退款到账时间")
    assert results[0]["title"] == "退款到账政策"


def test_search_policies_no_match():
    assert search_policies("完全无关的冷门话题") == []


def test_search_policies_top_k():
    # "退货退款运费保修" 命中多条
    results = search_policies("退货退款运费保修", top_k=2)
    assert len(results) <= 2
