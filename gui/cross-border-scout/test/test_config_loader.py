"""Task 1.7 采集配置加载器测试。

覆盖：正常（解析/默认值/过滤）、边界（空行/空启用）、异常（非法数字/非法平台/无凭证）。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.pipeline.collectors.collection_config import CollectionConfig, ConfigLoader


def test_load_from_rows_parses_full() -> None:
    """正常场景：完整记录解析正确。"""
    loader = ConfigLoader()
    rows = [
        {
            "record_id": "R1",
            "fields": {
                "配置ID": "C001", "行业": "宠物用品",
                "平台": ["亚马逊", "eBay"], "采集数量": 20,
                "评论采集数": 5, "优先级": 2,
                "启用状态": "启用", "采集频率": "daily",
            },
        },
    ]
    configs = loader.load_from_rows(rows)
    assert len(configs) == 1
    c = configs[0]
    assert c.config_id == "C001"
    assert c.industry == "宠物用品"
    assert c.platforms == ["亚马逊", "eBay"]
    assert c.collect_count == 20
    assert c.review_count == 5
    assert c.priority == 2
    assert c.enabled is True
    assert c.frequency == "daily"


def test_load_from_rows_empty() -> None:
    """边界场景：空行列表返回空。"""
    assert ConfigLoader().load_from_rows([]) == []


def test_parse_uses_defaults() -> None:
    """正常场景：缺字段用默认值。"""
    configs = ConfigLoader().load_from_rows([{"fields": {"行业": "宠物用品"}}])
    c = configs[0]
    assert c.industry == "宠物用品"
    assert c.platforms == []
    assert c.collect_count == 20
    assert c.review_count == 0
    assert c.enabled is True
    assert c.frequency == "daily"


def test_parse_invalid_number_raises() -> None:
    """异常场景：采集数量非数字抛 ValueError。"""
    with pytest.raises((ValueError, ValidationError)):
        ConfigLoader().load_from_rows(
            [{"fields": {"行业": "宠物用品", "采集数量": "abc"}}]
        )


def test_negative_collect_count_raises() -> None:
    """异常场景：采集数量为负抛 ValidationError。"""
    with pytest.raises(ValidationError):
        ConfigLoader().load_from_rows(
            [{"fields": {"行业": "宠物用品", "采集数量": -5}}]
        )


def test_get_enabled_filters() -> None:
    """正常场景：过滤出启用的配置。"""
    loader = ConfigLoader()
    rows = [
        {"fields": {"行业": "A", "启用状态": "启用"}},
        {"fields": {"行业": "B", "启用状态": "停用"}},
    ]
    enabled = loader.get_enabled(loader.load_from_rows(rows))
    assert len(enabled) == 1
    assert enabled[0].industry == "A"


def test_get_enabled_empty() -> None:
    """边界场景：空配置返回空。"""
    assert ConfigLoader().get_enabled([]) == []


def test_load_from_feishu_no_bitable() -> None:
    """异常场景：无 bitable 返回空。"""
    assert ConfigLoader().load_from_feishu("table123") == []


def test_load_from_feishu_no_table_id() -> None:
    """异常场景：无 table_id 返回空。"""
    loader = ConfigLoader(bitable=object())
    assert loader.load_from_feishu("") == []


def test_load_from_feishu_with_fake_bitable() -> None:
    """正常场景：从 fake bitable 读取并解析。"""

    class FakeBitable:
        def query_records(self, table_id, filter_condition=None, page_size=100):
            return [
                {"record_id": "R1", "fields": {
                    "配置ID": "C1", "行业": "宠物用品", "平台": ["亚马逊"],
                    "采集数量": 20, "启用状态": "启用",
                }},
                {"record_id": "R2", "fields": {
                    "配置ID": "C2", "行业": "厨房用品", "平台": ["eBay"],
                    "采集数量": 15, "启用状态": "停用",
                }},
            ]

    loader = ConfigLoader(bitable=FakeBitable())
    configs = loader.load_from_feishu("table123")
    assert len(configs) == 2
    assert len(loader.get_enabled(configs)) == 1


def test_default_mock_configs() -> None:
    """正常场景：默认 Mock 配置可解析。"""
    rows = ConfigLoader.default_mock_configs()
    configs = ConfigLoader().load_from_rows(rows)
    assert len(configs) == 1
    assert configs[0].industry == "宠物用品"
    assert configs[0].platforms == ["亚马逊"]


def test_platforms_dict_format() -> None:
    """正常场景：飞书多选 dict 格式解析。"""
    configs = ConfigLoader().load_from_rows(
        [{"fields": {"行业": "A", "平台": [{"name": "亚马逊"}, {"name": "eBay"}]}}]
    )
    assert configs[0].platforms == ["亚马逊", "eBay"]


def test_invalid_platform_raises() -> None:
    """异常场景：非法平台抛 ValidationError。"""
    with pytest.raises(ValidationError):
        ConfigLoader().load_from_rows(
            [{"fields": {"行业": "A", "平台": ["淘宝"]}}]
        )
