"""Task 1.9 采集完整流程测试。

覆盖：正常（mock配置/多平台/清洗/config附带）、边界（空配置/空平台/单平台）、
异常（采集失败被捕获，不中断其他平台）。
"""

from __future__ import annotations

from src.pipeline.collection_pipeline import CollectionPipeline, CollectionResult
from src.pipeline.collectors.collection_config import CollectionConfig


def test_run_with_mock_configs() -> None:
    """正常场景：使用默认 Mock 配置执行采集。"""
    results = CollectionPipeline().run_with_mock_configs()
    assert len(results) == 1
    assert results[0].industry == "宠物用品"
    assert results[0].platform == "亚马逊"
    assert len(results[0].products) == 20


def test_run_multi_platform() -> None:
    """正常场景：单配置多平台采集。"""
    configs = [
        CollectionConfig(industry="宠物用品", platforms=["亚马逊", "eBay"], collect_count=5)
    ]
    results = CollectionPipeline().run(configs)
    assert len(results) == 2
    assert {r.platform for r in results} == {"亚马逊", "eBay"}


def test_run_skips_disabled() -> None:
    """正常场景：停用的配置被跳过。"""
    configs = [
        CollectionConfig(industry="A", platforms=["亚马逊"], enabled=True),
        CollectionConfig(industry="B", platforms=["亚马逊"], enabled=False),
    ]
    results = CollectionPipeline().run(configs)
    assert len(results) == 1
    assert results[0].industry == "A"


def test_run_empty_configs() -> None:
    """边界场景：空配置返回空。"""
    assert CollectionPipeline().run([]) == []


def test_run_empty_platforms_skipped() -> None:
    """边界场景：platforms 为空跳过该配置。"""
    configs = [CollectionConfig(industry="A", platforms=[], enabled=True)]
    assert CollectionPipeline().run(configs) == []


def test_run_products_cleaned() -> None:
    """正常场景：采集结果已清洗（rank 升序、product_id 唯一）。"""
    configs = [
        CollectionConfig(industry="宠物用品", platforms=["亚马逊"], collect_count=10)
    ]
    products = CollectionPipeline().run(configs)[0].products
    assert len(products) == 10
    ranks = [p.rank for p in products]
    assert ranks == sorted(ranks)
    ids = [p.product_id for p in products]
    assert len(ids) == len(set(ids))


def test_run_collect_failure_continues(monkeypatch) -> None:
    """异常场景：某平台采集失败，不中断其他平台。"""

    class BadCollector:
        platform = "亚马逊"

        def collect(self, industry: str, count: int):
            raise RuntimeError("采集失败")

    def boom(platform: str):
        if platform == "亚马逊":
            return BadCollector()
        from src.pipeline.collectors.factory import get_collector
        return get_collector(platform)

    monkeypatch.setattr("src.pipeline.collection_pipeline.get_collector", boom)
    configs = [
        CollectionConfig(industry="A", platforms=["亚马逊", "eBay"], collect_count=3)
    ]
    results = CollectionPipeline().run(configs)
    assert len(results) == 1
    assert results[0].platform == "eBay"


def test_run_config_attached() -> None:
    """正常场景：结果附带 config 引用。"""
    config = CollectionConfig(
        industry="宠物用品", platforms=["亚马逊"], collect_count=3
    )
    results = CollectionPipeline().run([config])
    assert results[0].config is config


def test_result_dataclass_defaults() -> None:
    """边界场景：CollectionResult 默认值。"""
    r = CollectionResult(industry="A", platform="亚马逊")
    assert r.products == []
    assert r.config is None
