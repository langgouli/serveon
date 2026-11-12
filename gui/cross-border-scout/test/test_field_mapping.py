"""Task 2.1 字段映射测试。

覆盖：正常（主键/字段映射/URL/价格/时间戳）、边界（缺字段）、各字段格式提取。
"""

from __future__ import annotations

from src.feishu.field_mapping import (
    REVIEW_PRIMARY_KEYS,
    REPORT_PRIMARY_KEYS,
    SELECTION_FIELDS,
    SELECTION_PRIMARY_KEYS,
    _extract_text,
    extract_primary_values,
    product_to_record,
)
from src.pipeline.collectors.base import ProductData


def make_product(
    pid: str = "P001",
    platform: str = "亚马逊",
    price: float = 29.99,
    rating: float = 4.5,
    name: str = "宠物玩具",
) -> ProductData:
    return ProductData(
        product_id=pid, name=name, industry="宠物用品", platform=platform,
        price=price, rating=rating, review_count=1200, rank=5,
        url=f"https://example.com/{pid}",
    )


def test_primary_keys() -> None:
    """正常场景：三表主键定义正确。"""
    assert SELECTION_PRIMARY_KEYS == ["商品ID", "平台"]
    assert REVIEW_PRIMARY_KEYS == ["评论ID"]
    assert REPORT_PRIMARY_KEYS == ["报告ID"]


def test_product_to_record_fields() -> None:
    """正常场景：字段映射正确。"""
    record = product_to_record(make_product())
    assert record["商品ID"] == "P001"
    assert record["商品名称"] == "宠物玩具"
    assert record["行业"] == "宠物用品"
    assert record["平台"] == "亚马逊"
    assert record["评分"] == 4.5
    assert record["评论数"] == 1200
    assert record["排名"] == 5


def test_product_to_record_price_format() -> None:
    """正常场景：价格区间格式为"X美金"。"""
    record = product_to_record(make_product(price=29.99))
    assert record["价格区间"] == "29.99美金"


def test_product_to_record_url_format() -> None:
    """正常场景：商品链接为超链接结构。"""
    record = product_to_record(make_product())
    assert record["商品链接"] == {
        "link": "https://example.com/P001", "text": "宠物玩具"
    }


def test_product_to_record_timestamp() -> None:
    """正常场景：更新时间为毫秒时间戳。"""
    record = product_to_record(make_product())
    assert isinstance(record["更新时间"], int)
    assert record["更新时间"] > 0


def test_extract_primary_values_text() -> None:
    """正常场景：文本主键提取。"""
    fields = {"商品ID": "P001", "平台": "亚马逊"}
    assert extract_primary_values(fields, SELECTION_PRIMARY_KEYS) == ("P001", "亚马逊")


def test_extract_primary_values_single_select_dict() -> None:
    """正常场景：单选字段 dict 格式提取。"""
    fields = {"商品ID": "P001", "平台": {"name": "亚马逊"}}
    assert extract_primary_values(fields, SELECTION_PRIMARY_KEYS) == ("P001", "亚马逊")


def test_extract_primary_values_multi_select() -> None:
    """正常场景：多选字段 list 格式提取。"""
    fields = {"商品ID": "P001", "平台": [{"name": "亚马逊"}]}
    assert extract_primary_values(fields, SELECTION_PRIMARY_KEYS) == ("P001", "亚马逊")


def test_extract_primary_values_missing_field() -> None:
    """边界场景：缺字段返回空字符串。"""
    fields = {"商品ID": "P001"}
    assert extract_primary_values(fields, SELECTION_PRIMARY_KEYS) == ("P001", "")


def test_extract_text_variants() -> None:
    """正常场景：各字段格式文本提取。"""
    assert _extract_text(None) == ""
    assert _extract_text("text") == "text"
    assert _extract_text(42) == "42"
    assert _extract_text([{"text": "t"}]) == "t"
    assert _extract_text({"name": "n"}) == "n"
    assert _extract_text({"link": "l", "text": "t"}) == "t"


def test_selection_fields_mapping() -> None:
    """正常场景：字段名映射配置正确。"""
    assert SELECTION_FIELDS["product_id"] == "商品ID"
    assert SELECTION_FIELDS["platform"] == "平台"
    assert SELECTION_FIELDS["url"] == "商品链接"
