"""Mock 业务数据：订单、物流、政策库。

数据设计覆盖测试场景：
- ORD001 第一档(3天) / ORD002 第二档(10天) / ORD003 第三档(20天)
- ORD004 运输中未签收(软阻断)
- ORD005 金额超阈值(2500)
- ORD006 他人订单(越权)
- ORD007 定制商品不支持退货(硬阻断)
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

# 订单库
ORDERS: dict[str, dict] = {
    "ORD001": {"order_number": "ORD001", "user_id": 1001, "amount": 299.0, "product": "蓝牙耳机", "category": "electronics", "status": "signed", "signed_at_offset_days": 3, "support_return": True},
    "ORD002": {"order_number": "ORD002", "user_id": 1001, "amount": 159.0, "product": "手机壳", "category": "electronics", "status": "signed", "signed_at_offset_days": 10, "support_return": True},
    "ORD003": {"order_number": "ORD003", "user_id": 1001, "amount": 39.0, "product": "数据线", "category": "electronics", "status": "signed", "signed_at_offset_days": 20, "support_return": True},
    "ORD004": {"order_number": "ORD004", "user_id": 1001, "amount": 89.0, "product": "充电器", "category": "electronics", "status": "transporting", "signed_at_offset_days": None, "support_return": True},
    "ORD005": {"order_number": "ORD005", "user_id": 1001, "amount": 2500.0, "product": "高端耳机", "category": "electronics", "status": "signed", "signed_at_offset_days": 5, "support_return": True},
    "ORD006": {"order_number": "ORD006", "user_id": 2001, "amount": 100.0, "product": "耳机", "category": "electronics", "status": "signed", "signed_at_offset_days": 3, "support_return": True},
    "ORD007": {"order_number": "ORD007", "user_id": 1001, "amount": 50.0, "product": "定制T恤", "category": "custom", "status": "signed", "signed_at_offset_days": 5, "support_return": False},
    # 边界场景订单：签收第15天/第16天（验证 7-15 天窗口与 16 天起硬阻断）、金额恰 2000（验证阈值临界）
    "ORD010": {"order_number": "ORD010", "user_id": 1001, "amount": 2000.0, "product": "无线鼠标", "category": "electronics", "status": "signed", "signed_at_offset_days": 15, "support_return": True},
    "ORD011": {"order_number": "ORD011", "user_id": 1001, "amount": 69.0, "product": "键盘", "category": "electronics", "status": "signed", "signed_at_offset_days": 16, "support_return": True},
    # 未发货订单：验证"仅退款仅支持发货前"规则（id1/3/5/11）
    "ORD012": {"order_number": "ORD012", "user_id": 1001, "amount": 399.0, "product": "智能音箱", "category": "electronics", "status": "pending", "signed_at_offset_days": None, "support_return": True},
}

# 物流库（轨迹按时间倒序）
LOGISTICS: dict[str, dict] = {
    "ORD001": {
        "tracks": [
            {"time": "2026-11-01 10:00", "location": "北京分拣中心", "status": "已签收"},
            {"time": "2026-10-31 15:00", "location": "北京派送站", "status": "派送中"},
            {"time": "2026-10-30 08:00", "location": "上海转运中心", "status": "运输中"},
        ],
        "estimated_delivery": None,
        "abnormal": False,
    },
    "ORD002": {
        "tracks": [
            {"time": "2026-10-25 10:00", "location": "广州分拣中心", "status": "已签收"},
            {"time": "2026-10-24 15:00", "location": "广州派送站", "status": "派送中"},
        ],
        "estimated_delivery": None,
        "abnormal": False,
    },
    "ORD003": {
        "tracks": [
            {"time": "2026-10-15 09:00", "location": "杭州分拣中心", "status": "停滞"},
        ],
        "estimated_delivery": None,
        "abnormal": True,  # 物流异常
    },
    "ORD004": {
        "tracks": [
            {"time": "2026-11-03 09:00", "location": "上海转运中心", "status": "运输中"},
            {"time": "2026-11-02 14:00", "location": "广州分拣中心", "status": "已发出"},
        ],
        "estimated_delivery": "2026-11-05",
        "abnormal": False,
    },
    "ORD005": {
        "tracks": [
            {"time": "2026-10-30 10:00", "location": "深圳分拣中心", "status": "已签收"},
            {"time": "2026-10-29 15:00", "location": "深圳派送站", "status": "派送中"},
        ],
        "estimated_delivery": None,
        "abnormal": False,
    },
    "ORD007": {
        "tracks": [
            {"time": "2026-10-30 10:00", "location": "苏州分拣中心", "status": "已签收"},
        ],
        "estimated_delivery": None,
        "abnormal": False,
    },
    "ORD010": {
        "tracks": [
            {"time": "2026-10-22 10:00", "location": "北京派送站", "status": "已签收"},
        ],
        "estimated_delivery": None,
        "abnormal": False,
    },
    "ORD011": {
        "tracks": [
            {"time": "2026-10-21 10:00", "location": "上海派送站", "status": "已签收"},
        ],
        "estimated_delivery": None,
        "abnormal": False,
    },
}

# 政策库（口径与 testdata 标准答案对齐：7天内可退、满99包邮、偏远+15、
# 大件家具按体积计费、超7个工作日未到账联系支付平台、拆封影响二次销售不支持（质量例外）、
# 生鲜不支持无理由退货（质量例外）、仅退款/部分退款/运输中可改仅退款、定制不支持退换）
POLICIES: list[dict] = [
    {"clause_id": 3, "title": "退换货政策", "category": "return", "content": "签收后7天内支持退货退款，从签收之日起算；签收7-15天内仍可申请退货退款（超7天窗口需补充退货理由，审核通过后寄回商品）；第16天起超期不可申请；已拆封且影响二次销售的商品不支持退货（存在质量问题的除外）。",
     "keywords": ["退货", "退款", "7天", "15天", "退换货", "时效", "签收", "拆封", "二次销售"]},
    {"clause_id": 5, "title": "运费政策", "category": "freight", "content": "订单实付金额满99元即可包邮（刚好99元亦满足）；新疆、西藏、内蒙古等偏远地区额外收取15元运费，偏远地区不参与包邮活动；退货运费由责任方承担（质量问题商家承担、个人原因买家承担）；大件家具按体积和重量计费，具体以商品页公示为准，部分大件需额外支付搬运费。",
     "keywords": ["运费", "邮费", "承担", "包邮", "99", "偏远", "大件", "家具", "搬运"]},
    {"clause_id": 7, "title": "退款到账政策", "category": "refund", "content": "退款到账时间1-3个工作日，原路退回至支付账户；若超过7个工作日仍未到账，请联系支付平台客服并提供退款单号，平台将在48小时内核实并反馈；平台优惠券不退回，店铺优惠券若在有效期内会退回、过期作废。",
     "keywords": ["到账", "退款时间", "到账时间", "原路", "7个工作日", "未到账", "优惠券"]},
    {"clause_id": 9, "title": "保修政策", "category": "warranty", "content": "电子产品保修期1年，保修期内非人为损坏免费维修；过了保修期仍可付费维修，具体维修费用需根据检测结果而定。",
     "keywords": ["保修", "维修", "保期", "过保", "保修外", "付费维修"]},
    {"clause_id": 11, "title": "换货政策", "category": "exchange", "content": "签收7天内支持换货，可换同款或同价位商品；换货申请审核通过后，商家在48小时内发出新商品，物流时效3-5天；超过7天换货窗口不支持换货，可改申请签收后15天内的退货退款；定制类、生鲜等特殊商品不适用本条，超期或有其他异议可联系人工客服核查例外。",
     "keywords": ["换货", "更换", "换货期", "窗口", "超期", "审核", "48小时", "发货", "时效", "15天", "退货退款", "异议", "例外"]},
    {"clause_id": 13, "title": "特殊商品政策", "category": "special", "content": "定制商品签收后不支持退换；生鲜食品因保质期较短不支持无理由退货，存在腐坏、变质等质量问题可申请退款或补发。",
     "keywords": ["定制", "生鲜", "食品", "保质期", "腐坏", "变质", "特殊", "商品", "换货", "退货"]},
    {"clause_id": 15, "title": "退款申请政策", "category": "refund", "content": "未发货订单支持仅退款，创建退款记录后状态为待处理，跳过退货物流环节，无需寄回商品；运输中未签收订单需在签收后办理退货退款，如确需退款可改为仅退款，有异议可联系人工客服确认；支持部分退款（金额需用户明确指定，AI不自行决定，确认后原路退回至支付账户）。",
     "keywords": ["仅退款", "未发货", "发货前", "运输中", "部分退款", "只退", "申请退款", "一部分", "部分金额", "部分退", "还没发货", "没发货"]},
    {"clause_id": 17, "title": "退款审核政策", "category": "refund", "content": "单笔退款金额不超过2000元（刚好2000元亦满足）由系统自动审核办理，无需转人工；超过2000元超出阈值需转人工审核，审核通过后方可处理。",
     "keywords": ["审核", "转人工", "阈值", "超金额", "2000", "超过2000", "人工审核"]},
]


def get_order(order_number: str) -> Optional[dict]:
    """按订单号查询订单，返回含 signed_at(ISO) 的字典。"""
    o = ORDERS.get(order_number)
    if not o:
        return None
    d = dict(o)
    if o["signed_at_offset_days"] is not None:
        d["signed_at"] = (
            datetime.now() - timedelta(days=o["signed_at_offset_days"])
        ).isoformat()
    else:
        d["signed_at"] = None
    d["receiver_phone"] = "138****1234"  # mock 收件人手机号（脱敏演示）
    return d


def get_orders_by_user(user_id: int) -> list[dict]:
    """按 user_id 过滤订单（越权防护：仅返回本人订单）。"""
    return [get_order(no) for no, o in ORDERS.items() if o["user_id"] == user_id]


def get_recent_orders(user_id: int, limit: int = 5) -> list[dict]:
    """最近 N 条订单，供列表选择。"""
    return get_orders_by_user(user_id)[:limit]


def get_logistics(order_number: str) -> Optional[dict]:
    """查询物流信息。"""
    return LOGISTICS.get(order_number)


def search_policies(query: str, top_k: int = 3) -> list[dict]:
    """关键词检索政策库，按命中关键词数排序，取 Top-K。"""
    results: list[tuple[int, dict]] = []
    for p in POLICIES:
        hits = sum(1 for kw in p["keywords"] if kw in query)
        if hits > 0:
            results.append((hits, p))
    results.sort(key=lambda x: -x[0])
    return [p for _, p in results[:top_k]]
