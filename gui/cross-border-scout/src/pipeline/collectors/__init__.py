"""采集器包：统一数据结构、三平台采集器、工厂、配置、真实接口骨架。"""

from src.pipeline.collectors.amazon import AmazonCollector
from src.pipeline.collectors.base import PLATFORMS, BaseCollector, ProductData
from src.pipeline.collectors.collection_config import CollectionConfig, ConfigLoader
from src.pipeline.collectors.ebay import eBayCollector
from src.pipeline.collectors.factory import get_all_collectors, get_collector
from src.pipeline.collectors.real import RealCollector
from src.pipeline.collectors.walmart import WalmartCollector

__all__ = [
    "PLATFORMS",
    "BaseCollector",
    "ProductData",
    "AmazonCollector",
    "WalmartCollector",
    "eBayCollector",
    "get_collector",
    "get_all_collectors",
    "CollectionConfig",
    "ConfigLoader",
    "RealCollector",
]
