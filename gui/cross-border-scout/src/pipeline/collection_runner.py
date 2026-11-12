"""采集→同步完整流程：采集 → 清洗 → 同步到飞书选品池。

在 Task 1.9 CollectionPipeline 基础上加入 SyncService 同步。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.feishu.sync_service import SyncResult
from src.pipeline.collection_pipeline import CollectionPipeline, CollectionResult
from src.pipeline.collectors.collection_config import CollectionConfig, ConfigLoader


@dataclass
class CollectionRunResult:
    """一次采集运行的完整结果。"""

    collection_results: list[CollectionResult] = field(default_factory=list)
    sync_result: SyncResult | None = None


class CollectionRunner:
    """采集→同步流程编排器。"""

    def __init__(
        self,
        pipeline: CollectionPipeline | None = None,
        sync_service: Any | None = None,
    ) -> None:
        self.pipeline = pipeline or CollectionPipeline()
        self.sync_service = sync_service

    def run(self, configs: list[CollectionConfig]) -> CollectionRunResult:
        """执行采集→同步流程。

        Args:
            configs: 采集配置列表

        Returns:
            采集结果 + 同步统计
        """
        collection_results = self.pipeline.run(configs)
        sync_result: SyncResult | None = None
        if self.sync_service:
            all_products = []
            for r in collection_results:
                all_products.extend(r.products)
            sync_result = self.sync_service.sync_products(all_products)
        return CollectionRunResult(
            collection_results=collection_results, sync_result=sync_result
        )

    def run_with_mock_configs(self) -> CollectionRunResult:
        """使用默认 Mock 配置执行采集→同步。"""
        rows = ConfigLoader.default_mock_configs()
        configs = self.pipeline.config_loader.load_from_rows(rows)
        return self.run(configs)
