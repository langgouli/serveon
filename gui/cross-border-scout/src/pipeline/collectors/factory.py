"""采集器工厂：按平台名分发到对应采集器。"""

from __future__ import annotations

from src.pipeline.collectors.amazon import AmazonCollector
from src.pipeline.collectors.base import BaseCollector
from src.pipeline.collectors.ebay import eBayCollector
from src.pipeline.collectors.walmart import WalmartCollector

# 平台名 -> 采集器类
_COLLECTOR_MAP: dict[str, type[BaseCollector]] = {
    "亚马逊": AmazonCollector,
    "Walmart": WalmartCollector,
    "eBay": eBayCollector,
}


def get_collector(platform: str) -> BaseCollector:
    """根据平台名返回采集器实例。

    Args:
        platform: 平台名（亚马逊/Walmart/eBay）

    Returns:
        采集器实例

    Raises:
        ValueError: 平台不支持时
    """
    cls = _COLLECTOR_MAP.get(platform)
    if cls is None:
        raise ValueError(
            f"不支持的平台: {platform!r}，可选: {list(_COLLECTOR_MAP)}"
        )
    return cls()


def get_all_collectors() -> dict[str, BaseCollector]:
    """返回所有平台采集器实例。"""
    return {name: cls() for name, cls in _COLLECTOR_MAP.items()}
