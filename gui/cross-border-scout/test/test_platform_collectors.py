"""Task 1.2-1.4 三平台 Mock 采集器测试。

参数化验证 Amazon/Walmart/eBay 采集器。
覆盖：正常（字段/平台/URL）、边界（count=0/超上限截断）、可复现性。
"""

from __future__ import annotations

import pytest

from src.pipeline.collectors.amazon import AmazonCollector
from src.pipeline.collectors.ebay import eBayCollector
from src.pipeline.collectors.walmart import WalmartCollector

COLLECTORS = [
    (AmazonCollector, "亚马逊", "amazon.com"),
    (WalmartCollector, "Walmart", "walmart.com"),
    (eBayCollector, "eBay", "ebay.com"),
]


@pytest.mark.parametrize("cls, platform, domain", COLLECTORS)
def test_collect_returns_correct_count(cls, platform, domain) -> None:
    """正常场景：采集数量与请求一致。"""
    products = cls().collect("宠物用品", 10)
    assert len(products) == 10


@pytest.mark.parametrize("cls, platform, domain", COLLECTORS)
def test_platform_field(cls, platform, domain) -> None:
    """正常场景：platform 字段正确。"""
    products = cls().collect("宠物用品", 1)
    assert products[0].platform == platform


@pytest.mark.parametrize("cls, platform, domain", COLLECTORS)
def test_url_domain(cls, platform, domain) -> None:
    """正常场景：URL 包含对应平台域名。"""
    products = cls().collect("宠物用品", 1)
    assert domain in products[0].url


@pytest.mark.parametrize("cls, platform, domain", COLLECTORS)
def test_fields_valid(cls, platform, domain) -> None:
    """正常场景：字段值在合法范围。"""
    products = cls().collect("宠物用品", 5)
    for p in products:
        assert p.price > 0
        assert 0 <= p.rating <= 5
        assert p.review_count >= 0
        assert p.rank >= 1
        assert p.industry == "宠物用品"


@pytest.mark.parametrize("cls, platform, domain", COLLECTORS)
def test_count_zero_returns_empty(cls, platform, domain) -> None:
    """边界场景：count=0 返回空列表。"""
    assert cls().collect("宠物用品", 0) == []


@pytest.mark.parametrize("cls, platform, domain", COLLECTORS)
def test_negative_count_returns_empty(cls, platform, domain) -> None:
    """边界场景：负数 count 返回空列表。"""
    assert cls().collect("宠物用品", -5) == []


@pytest.mark.parametrize("cls, platform, domain", COLLECTORS)
def test_over_max_count_truncated(cls, platform, domain) -> None:
    """边界场景：count 超过上限截断到 MAX_COUNT。"""
    products = cls().collect("宠物用品", cls.MAX_COUNT + 50)
    assert len(products) == cls.MAX_COUNT


@pytest.mark.parametrize("cls, platform, domain", COLLECTORS)
def test_reproducible(cls, platform, domain) -> None:
    """正常场景：相同参数两次采集结果一致（Mock 种子固定）。"""
    first = cls().collect("宠物用品", 5)
    second = cls().collect("宠物用品", 5)
    assert [p.product_id for p in first] == [p.product_id for p in second]


@pytest.mark.parametrize("cls, platform, domain", COLLECTORS)
def test_different_industry_different_data(cls, platform, domain) -> None:
    """正常场景：不同行业生成不同数据（种子含行业）。"""
    a = cls().collect("宠物用品", 3)
    b = cls().collect("厨房用品", 3)
    assert [p.product_id for p in a] != [p.product_id for p in b]


@pytest.mark.parametrize("cls, platform, domain", COLLECTORS)
def test_empty_industry_works(cls, platform, domain) -> None:
    """边界场景：空行业字符串不报错。"""
    products = cls().collect("", 2)
    assert len(products) == 2
    assert products[0].industry == ""
