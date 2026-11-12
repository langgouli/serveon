"""采集配置数据结构与加载器。

从飞书采集配置表读取配置，解析为 CollectionConfig。
无凭证时返回空，由调用方决定是否用 Mock 默认配置。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.pipeline.collectors.base import PLATFORMS


class CollectionConfig(BaseModel):
    """单条采集配置，对应采集配置表一行。"""

    config_id: str = Field(default="", description="配置 ID")
    industry: str = Field(description="行业关键词")
    platforms: list[str] = Field(default_factory=list, description="采集平台列表")
    collect_count: int = Field(default=20, description="采集数量")
    review_count: int = Field(default=0, description="评论采集数（预留）")
    priority: int = Field(default=1, description="优先级")
    enabled: bool = Field(default=True, description="是否启用")
    frequency: str = Field(default="daily", description="采集频率")

    @field_validator("collect_count", "review_count", "priority")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("采集数量/评论数/优先级不能为负")
        return v

    @field_validator("platforms")
    @classmethod
    def _platforms_valid(cls, v: list[str]) -> list[str]:
        for p in v:
            if p not in PLATFORMS:
                raise ValueError(f"平台必须是 {PLATFORMS} 之一，收到: {p}")
        return v


class ConfigLoader:
    """采集配置加载器。"""

    def __init__(self, bitable: Any | None = None) -> None:
        self._bitable = bitable

    def load_from_rows(self, rows: list[dict]) -> list[CollectionConfig]:
        """从记录列表解析配置。

        Args:
            rows: 记录列表，每项含 record_id/fields 或直接是 fields

        Returns:
            CollectionConfig 列表
        """
        return [self._parse(row) for row in rows]

    def _parse(self, row: dict) -> CollectionConfig:
        """解析单条记录。"""
        fields = row.get("fields", row)
        # 平台字段兼容：飞书多选可能返回 [{"name": "亚马逊"}] 或 ["亚马逊"]
        raw_platforms = fields.get("平台", [])
        platforms = [
            p["name"] if isinstance(p, dict) else str(p) for p in raw_platforms
        ]
        return CollectionConfig(
            config_id=str(fields.get("配置ID", "")),
            industry=str(fields.get("行业", "")),
            platforms=platforms,
            collect_count=int(fields.get("采集数量", 20)),
            review_count=int(fields.get("评论采集数", 0)),
            priority=int(fields.get("优先级", 1)),
            enabled=str(fields.get("启用状态", "启用")) == "启用",
            frequency=str(fields.get("采集频率", "daily")),
        )

    def load_from_feishu(self, table_id: str) -> list[CollectionConfig]:
        """从飞书表读取配置。

        无 bitable 或无 table_id 时返回空列表。
        """
        if self._bitable is None or not table_id:
            return []
        try:
            records = self._bitable.query_records(table_id, page_size=100)
            return self.load_from_rows(records)
        except Exception:
            return []

    def get_enabled(
        self, configs: list[CollectionConfig]
    ) -> list[CollectionConfig]:
        """过滤出启用的配置。"""
        return [c for c in configs if c.enabled]

    @staticmethod
    def default_mock_configs() -> list[dict]:
        """返回默认 Mock 配置行（开发阶段用）。"""
        return [
            {
                "record_id": "R001",
                "fields": {
                    "配置ID": "C001",
                    "行业": "宠物用品",
                    "平台": ["亚马逊"],
                    "采集数量": 20,
                    "评论采集数": 0,
                    "优先级": 1,
                    "启用状态": "启用",
                    "采集频率": "daily",
                },
            }
        ]
