"""Task 2.4 采集→同步完整流程测试。

覆盖：正常（采集+同步/多平台）、边界（空配置/无同步）、同步统计正确。
"""

from __future__ import annotations

from src.feishu.sync_service import SyncResult
from src.pipeline.collection_runner import CollectionRunner, CollectionRunResult
from src.pipeline.collectors.collection_config import CollectionConfig


class FakeSyncService:
    """模拟同步服务。"""

    def __init__(self) -> None:
        self.synced: list = []

    def sync_products(self, products) -> SyncResult:
        self.synced.extend(products)
        r = SyncResult(table_name="选品池")
        r.new_count = len(products)
        return r


def test_run_without_sync() -> None:
    """正常场景：无同步服务时只采集。"""
    result = CollectionRunner().run_with_mock_configs()
    assert len(result.collection_results) == 1
    assert result.sync_result is None


def test_run_with_sync() -> None:
    """正常场景：采集+同步。"""
    fake = FakeSyncService()
    runner = CollectionRunner(sync_service=fake)
    result = runner.run_with_mock_configs()
    assert result.sync_result is not None
    assert result.sync_result.new_count == 20
    assert len(fake.synced) == 20


def test_run_empty_configs() -> None:
    """边界场景：空配置返回空。"""
    result = CollectionRunner().run([])
    assert result.collection_results == []
    assert result.sync_result is None


def test_run_multi_platform_sync() -> None:
    """正常场景：多平台同步统计正确。"""
    fake = FakeSyncService()
    configs = [
        CollectionConfig(
            industry="宠物用品", platforms=["亚马逊", "eBay"], collect_count=3
        )
    ]
    runner = CollectionRunner(sync_service=fake)
    result = runner.run(configs)
    assert len(result.collection_results) == 2
    assert result.sync_result.new_count == 6  # 3+3


def test_run_result_dataclass_defaults() -> None:
    """边界场景：CollectionRunResult 默认值。"""
    r = CollectionRunResult()
    assert r.collection_results == []
    assert r.sync_result is None


def test_run_sync_only_when_service_present() -> None:
    """正常场景：有同步服务时 sync_result 非空。"""
    fake = FakeSyncService()
    runner = CollectionRunner(sync_service=fake)
    result = runner.run_with_mock_configs()
    assert result.sync_result is not None
    assert result.sync_result.table_name == "选品池"
