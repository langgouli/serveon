"""Task 1.1 采集基类与数据结构测试。

验证 ProductData 校验规则、BaseCollector 抽象约束、_make_product 自动填充。
覆盖：正常（构造/子类实现）、边界（rating 0/5、count=0）、异常（缺字段/非法值/抽象类实例化）。
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.pipeline.collectors.base import PLATFORMS, BaseCollector, ProductData


def test_product_data_valid() -> None:
    """正常场景：合法字段构造成功。"""
    p = ProductData(
        product_id="P001", name="宠物玩具", industry="宠物用品",
        platform="亚马逊", price=29.99, rating=4.5, review_count=1200,
        rank=5, url="https://example.com/p001",
    )
    assert p.product_id == "P001"
    assert p.platform == "亚马逊"


@pytest.mark.parametrize("platform", list(PLATFORMS))
def test_platform_all_valid(platform: str) -> None:
    """正常场景：三平台均合法。"""
    p = ProductData(
        product_id="P1", name="n", industry="i", platform=platform,
        price=10.0, rating=4.0, review_count=1, rank=1, url="u",
    )
    assert p.platform == platform


def test_rating_boundary_zero() -> None:
    """边界场景：rating=0 合法。"""
    p = ProductData(
        product_id="P1", name="n", industry="i", platform="亚马逊",
        price=10.0, rating=0, review_count=0, rank=0, url="u",
    )
    assert p.rating == 0


def test_rating_boundary_five() -> None:
    """边界场景：rating=5 合法。"""
    p = ProductData(
        product_id="P1", name="n", industry="i", platform="亚马逊",
        price=10.0, rating=5, review_count=1, rank=1, url="u",
    )
    assert p.rating == 5


def test_missing_field_raises() -> None:
    """异常场景：缺字段抛 ValidationError。"""
    with pytest.raises(ValidationError):
        ProductData(  # type: ignore[call-arg]
            product_id="P1", name="n", industry="i", platform="亚马逊",
            price=10.0, rating=4.0, review_count=1, url="u",
        )


def test_invalid_platform_raises() -> None:
    """异常场景：平台非法抛 ValidationError。"""
    with pytest.raises(ValidationError):
        ProductData(
            product_id="P1", name="n", industry="i", platform="淘宝",
            price=10.0, rating=4.0, review_count=1, rank=1, url="u",
        )


def test_rating_out_of_range_raises() -> None:
    """异常场景：rating>5 抛 ValidationError。"""
    with pytest.raises(ValidationError):
        ProductData(
            product_id="P1", name="n", industry="i", platform="亚马逊",
            price=10.0, rating=5.5, review_count=1, rank=1, url="u",
        )


def test_negative_price_raises() -> None:
    """异常场景：价格<=0 抛 ValidationError。"""
    with pytest.raises(ValidationError):
        ProductData(
            product_id="P1", name="n", industry="i", platform="亚马逊",
            price=0, rating=4.0, review_count=1, rank=1, url="u",
        )


def test_negative_review_count_raises() -> None:
    """异常场景：评论数为负抛 ValidationError。"""
    with pytest.raises(ValidationError):
        ProductData(
            product_id="P1", name="n", industry="i", platform="亚马逊",
            price=10.0, rating=4.0, review_count=-1, rank=1, url="u",
        )


def test_abstract_class_cannot_instantiate() -> None:
    """异常场景：抽象基类不能直接实例化。"""
    with pytest.raises(TypeError):
        BaseCollector()  # type: ignore[abstract]


def test_subclass_without_collect_cannot_instantiate() -> None:
    """异常场景：子类未实现 collect 不能实例化。"""
    class BadCollector(BaseCollector):
        platform = "亚马逊"

    with pytest.raises(TypeError):
        BadCollector()  # type: ignore[abstract]


def test_concrete_collector_implements_collect() -> None:
    """正常场景：子类实现 collect 可实例化并调用。"""

    class MockCollector(BaseCollector):
        platform = "亚马逊"

        def collect(self, industry: str, count: int) -> list[ProductData]:
            if count == 0:
                return []
            return [
                self._make_product(
                    product_id=f"P{i}", name=f"商品{i}", industry=industry,
                    price=10.0 + i, rating=4.0, review_count=i, rank=i,
                    url=f"https://example.com/p{i}",
                )
                for i in range(count)
            ]

    collector = MockCollector()
    products = collector.collect("宠物用品", 3)
    assert len(products) == 3
    assert products[0].platform == "亚马逊"
    assert products[0].industry == "宠物用品"
    # _make_product 自动填 collected_at
    assert isinstance(products[0].collected_at, datetime)


def test_make_product_auto_fills_platform() -> None:
    """正常场景：_make_product 自动填 platform。"""

    class AmazonCollector(BaseCollector):
        platform = "亚马逊"

        def collect(self, industry: str, count: int) -> list[ProductData]:
            return []

    collector = AmazonCollector()
    p = collector._make_product(
        product_id="P1", name="n", industry="i", price=10.0,
        rating=4.0, review_count=1, rank=1, url="u",
    )
    assert p.platform == "亚马逊"
