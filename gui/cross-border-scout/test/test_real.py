"""Task 1.6 真实采集器骨架测试。

覆盖：正常（继承关系/解析/截断）、异常（未实现/缺字段）、边界（count=0 不触发抓取）。
"""

from __future__ import annotations

import pytest

from src.pipeline.collectors.base import BaseCollector
from src.pipeline.collectors.real import RealCollector


def test_real_is_base_subclass() -> None:
    """正常场景：RealCollector 继承 BaseCollector。"""
    assert issubclass(RealCollector, BaseCollector)


def test_use_real_flag() -> None:
    """正常场景：RealCollector 标记 use_real=True。"""
    assert RealCollector.use_real is True


def test_fetch_raw_not_implemented_raises() -> None:
    """异常场景：未实现 _fetch_raw 时 collect 抛 NotImplementedError。"""
    with pytest.raises(NotImplementedError):
        RealCollector().collect("宠物用品", 5)


def test_collect_parses_raw_data() -> None:
    """正常场景：_fetch_raw 返回原始数据，collect 解析为 ProductData。"""

    class FakeReal(RealCollector):
        platform = "亚马逊"

        def _fetch_raw(self, industry: str, count: int) -> list[dict]:
            return [
                {
                    "product_id": f"P{i}", "name": f"商品{i}",
                    "price": 10.0 + i, "rating": 4.0, "review_count": i,
                    "rank": i + 1, "url": f"https://example.com/{i}",
                }
                for i in range(count)
            ]

    products = FakeReal().collect("宠物用品", 3)
    assert len(products) == 3
    assert products[0].platform == "亚马逊"
    assert products[0].price == 10.0
    assert products[0].industry == "宠物用品"


def test_count_zero_skips_fetch() -> None:
    """边界场景：count=0 不调用 _fetch_raw，直接返回空。"""

    class FakeReal(RealCollector):
        platform = "亚马逊"

        def _fetch_raw(self, industry: str, count: int) -> list[dict]:
            raise AssertionError("count=0 时不应调用 _fetch_raw")

    assert FakeReal().collect("宠物用品", 0) == []


def test_raw_data_truncated_to_count() -> None:
    """边界场景：原始数据多于 count 时截断。"""

    class FakeReal(RealCollector):
        platform = "亚马逊"

        def _fetch_raw(self, industry: str, count: int) -> list[dict]:
            return [
                {
                    "product_id": f"P{i}", "name": "n", "price": 1.0,
                    "rating": 4.0, "review_count": 0, "rank": i + 1, "url": "u",
                }
                for i in range(10)
            ]

    products = FakeReal().collect("宠物用品", 3)
    assert len(products) == 3


def test_raw_missing_field_raises() -> None:
    """异常场景：原始数据缺字段抛 KeyError。"""

    class FakeReal(RealCollector):
        platform = "亚马逊"

        def _fetch_raw(self, industry: str, count: int) -> list[dict]:
            return [{"product_id": "P1"}]  # 缺其他字段

    with pytest.raises(KeyError):
        FakeReal().collect("宠物用品", 1)


def test_raw_invalid_price_raises() -> None:
    """异常场景：原始数据 price 非法时 ProductData 校验失败抛 ValidationError。"""
    from pydantic import ValidationError

    class FakeReal(RealCollector):
        platform = "亚马逊"

        def _fetch_raw(self, industry: str, count: int) -> list[dict]:
            return [
                {
                    "product_id": "P1", "name": "n", "price": -5.0,
                    "rating": 4.0, "review_count": 0, "rank": 1, "url": "u",
                }
            ]

    with pytest.raises(ValidationError):
        FakeReal().collect("宠物用品", 1)
