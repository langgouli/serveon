"""采集完整流程：加载配置 -> 多平台采集 -> 数据清洗。

串联 Task 1.1-1.8 各组件，输出每个平台每个行业的清洗后商品数据。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.observability.logger import logger
from src.pipeline.cleaners.cleaner import DataCleaner
from src.pipeline.collectors.base import ProductData
from src.pipeline.collectors.collection_config import CollectionConfig, ConfigLoader
from src.pipeline.collectors.factory import get_collector


@dataclass
class CollectionResult:
    """单次采集结果：某行业在某平台的数据。"""

    industry: str
    platform: str
    products: list[ProductData] = field(default_factory=list)
    config: CollectionConfig | None = None


class CollectionPipeline:
    """采集流程编排器。"""

    def __init__(
        self,
        config_loader: ConfigLoader | None = None,
        cleaner: DataCleaner | None = None,
    ) -> None:
        self.config_loader = config_loader or ConfigLoader()
        self.cleaner = cleaner or DataCleaner()

    def run(self, configs: list[CollectionConfig]) -> list[CollectionResult]:
        """执行采集流程。

        Args:
            configs: 采集配置列表

        Returns:
            每个启用配置、每个平台的采集结果
        """
        enabled = self.config_loader.get_enabled(configs)
        results: list[CollectionResult] = []
        for config in enabled:
            for platform in config.platforms:
                try:
                    collector = get_collector(platform)
                    products = collector.collect(config.industry, config.collect_count)
                    cleaned = self.cleaner.clean(products)
                except Exception as e:
                    logger.warning(
                        f"采集失败: 平台={platform} 行业={config.industry} 原因={e}"
                    )
                    continue
                results.append(
                    CollectionResult(
                        industry=config.industry,
                        platform=platform,
                        products=cleaned,
                        config=config,
                    )
                )
        return results

    def run_with_mock_configs(self) -> list[CollectionResult]:
        """使用默认 Mock 配置执行采集（开发阶段用）。"""
        rows = ConfigLoader.default_mock_configs()
        configs = self.config_loader.load_from_rows(rows)
        return self.run(configs)
