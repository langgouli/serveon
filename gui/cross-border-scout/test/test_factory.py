"""Task 1.5 采集器工厂测试。

覆盖：正常（三平台分发/类型/全平台）、异常（未知平台/带空格）。
"""

from __future__ import annotations

import pytest

from src.pipeline.collectors.amazon import AmazonCollector
from src.pipeline.collectors.base import BaseCollector
from src.pipeline.collectors.ebay import eBayCollector
from src.pipeline.collectors.factory import get_all_collectors, get_collector
from src.pipeline.collectors.walmart import WalmartCollector


@pytest.mark.parametrize(
    "platform, expected_cls",
    [
        ("亚马逊", AmazonCollector),
        ("Walmart", WalmartCollector),
        ("eBay", eBayCollector),
    ],
)
def test_get_collector_returns_correct_type(platform: str, expected_cls) -> None:
    """正常场景：按平台返回对应采集器类型。"""
    collector = get_collector(platform)
    assert isinstance(collector, expected_cls)
    assert isinstance(collector, BaseCollector)


def test_get_collector_unknown_raises() -> None:
    """异常场景：未知平台抛 ValueError。"""
    with pytest.raises(ValueError):
        get_collector("淘宝")


def test_get_collector_whitespace_raises() -> None:
    """异常场景：平台名带空格不匹配（严格匹配）。"""
    with pytest.raises(ValueError):
        get_collector("亚马逊 ")


def test_get_collector_case_sensitive() -> None:
    """异常场景：Walmart 大小写敏感，小写不匹配。"""
    with pytest.raises(ValueError):
        get_collector("walmart")


def test_get_all_collectors_returns_three() -> None:
    """正常场景：返回全部三平台采集器。"""
    collectors = get_all_collectors()
    assert set(collectors.keys()) == {"亚马逊", "Walmart", "eBay"}
    for c in collectors.values():
        assert isinstance(c, BaseCollector)


def test_get_collector_is_new_instance_each_call() -> None:
    """正常场景：每次调用返回新实例。"""
    a = get_collector("亚马逊")
    b = get_collector("亚马逊")
    assert a is not b
