"""数据同步服务：增量更新、去重、同步监控。

选品池按 商品ID+平台 去重，评论库按 评论ID，分析报告按 报告ID。
同步结果统一封装为 SyncResult，记录新增/更新/跳过/失败数和耗时。

核心流程：
1. 查询飞书表现有记录，建立 主键 -> record_id 索引
2. 遍历新数据，对比主键判断是新增还是更新
3. 批量新增 + 逐条更新
4. 返回 SyncResult 统计结果
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from src.feishu.bitable import bitable_client
from src.feishu.field_mapping import (
    REVIEW_PRIMARY_KEYS,
    REPORT_PRIMARY_KEYS,
    SELECTION_PRIMARY_KEYS,
    extract_primary_values,
    product_to_record,
)
from src.observability.logger import get_logger
from src.pipeline.collectors.base import ProductData

logger = get_logger()


@dataclass
class SyncResult:
    """同步结果统计。"""

    table_name: str = ""
    new_count: int = 0
    update_count: int = 0
    skip_count: int = 0
    fail_count: int = 0
    duration_ms: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.new_count + self.update_count + self.skip_count + self.fail_count

    def __str__(self) -> str:
        return (
            f"[{self.table_name}] 同步完成: "
            f"新增 {self.new_count} / 更新 {self.update_count} / "
            f"跳过 {self.skip_count} / 失败 {self.fail_count} "
            f"(耗时 {self.duration_ms}ms)"
        )


class SyncService:
    """数据同步服务：飞书多维表格增量更新。

    Usage:
        service = SyncService(table_id="xxx", table_name="选品池")
        result = service.sync_products(products)
    """

    def __init__(
        self,
        table_id: str,
        table_name: str = "",
        bitable: Any | None = None,
    ) -> None:
        self._table_id = table_id
        self._table_name = table_name
        self._bitable = bitable or bitable_client

    # ============================================================
    # 商品同步
    # ============================================================

    def sync_products(self, products: list[ProductData]) -> SyncResult:
        """同步商品数据到选品池表（增量更新）。

        按 商品ID+平台 主键去重：
        - 不存在 -> 新增
        - 已存在 -> 更新
        """
        start = time.time()
        result = SyncResult(table_name=self._table_name or "选品池")

        if not products:
            result.duration_ms = int((time.time() - start) * 1000)
            logger.info(f"{result}（输入为空）")
            return result

        try:
            existing_index = self._build_existing_index(SELECTION_PRIMARY_KEYS)

            to_create: list[dict[str, Any]] = []
            to_update: list[tuple[str, dict[str, Any]]] = []

            for product in products:
                new_fields = product_to_record(product)
                primary_value = self._extract_product_primary(product)
                if primary_value in existing_index:
                    record_id = existing_index[primary_value]
                    to_update.append((record_id, new_fields))
                else:
                    to_create.append(new_fields)

            if to_create:
                created_ids = self._bitable.batch_add_records(
                    self._table_id, to_create
                )
                result.new_count = len(created_ids)

            for record_id, fields in to_update:
                try:
                    self._bitable.update_record(self._table_id, record_id, fields)
                    result.update_count += 1
                except Exception as e:
                    result.fail_count += 1
                    msg = f"更新失败 record_id={record_id}: {e}"
                    result.errors.append(msg)
                    logger.error(msg)

            result.skip_count = max(
                0,
                len(products) - result.new_count - result.update_count - result.fail_count,
            )

        except Exception as e:
            result.fail_count = len(products)
            result.errors.append(f"同步整体失败: {e}")
            logger.error(f"同步失败: {e}", exc_info=True)

        result.duration_ms = int((time.time() - start) * 1000)
        logger.info(str(result))
        return result

    # ============================================================
    # 通用记录同步（评论/报告）
    # ============================================================

    def sync_records(
        self, records: list[dict[str, Any]], primary_keys: list[str]
    ) -> SyncResult:
        """同步通用记录到飞书表（增量更新）。"""
        start = time.time()
        result = SyncResult(table_name=self._table_name)

        if not records:
            result.duration_ms = int((time.time() - start) * 1000)
            logger.info(f"{result}（输入为空）")
            return result

        try:
            existing_index = self._build_existing_index(primary_keys)

            to_create: list[dict[str, Any]] = []
            to_update: list[tuple[str, dict[str, Any]]] = []

            for fields in records:
                primary_value = extract_primary_values(fields, primary_keys)
                if primary_value in existing_index:
                    record_id = existing_index[primary_value]
                    to_update.append((record_id, fields))
                else:
                    to_create.append(fields)

            if to_create:
                created_ids = self._bitable.batch_add_records(
                    self._table_id, to_create
                )
                result.new_count = len(created_ids)

            for record_id, fields in to_update:
                try:
                    self._bitable.update_record(self._table_id, record_id, fields)
                    result.update_count += 1
                except Exception as e:
                    result.fail_count += 1
                    msg = f"更新失败 record_id={record_id}: {e}"
                    result.errors.append(msg)
                    logger.error(msg)

            result.skip_count = max(
                0,
                len(records) - result.new_count - result.update_count - result.fail_count,
            )

        except Exception as e:
            result.fail_count = len(records)
            result.errors.append(f"同步整体失败: {e}")
            logger.error(f"同步失败: {e}", exc_info=True)

        result.duration_ms = int((time.time() - start) * 1000)
        logger.info(str(result))
        return result

    def sync_reviews(self, reviews: list[dict[str, Any]]) -> SyncResult:
        """同步评论数据到评论库表（按 评论ID 去重）。"""
        return self.sync_records(reviews, REVIEW_PRIMARY_KEYS)

    def sync_reports(self, reports: list[dict[str, Any]]) -> SyncResult:
        """同步分析报告到分析报告表（按 报告ID 去重）。"""
        return self.sync_records(reports, REPORT_PRIMARY_KEYS)

    # ============================================================
    # 私有方法
    # ============================================================

    def _build_existing_index(
        self, primary_keys: list[str]
    ) -> dict[tuple[Any, ...], str]:
        """查询现有记录，构建 主键值 -> record_id 的索引。"""
        existing_records = self._bitable.query_records(self._table_id)
        index: dict[tuple[Any, ...], str] = {}

        for record in existing_records:
            record_id = record.get("record_id")
            fields = record.get("fields", {})
            primary_value = extract_primary_values(fields, primary_keys)
            if record_id and primary_value:
                index[primary_value] = record_id

        logger.info(
            f"[{self._table_name}] 现有记录 {len(existing_records)} 条，"
            f"主键索引 {len(index)} 条"
        )
        return index

    @staticmethod
    def _extract_product_primary(product: ProductData) -> tuple[str, str]:
        """从 ProductData 提取主键值元组（商品ID, 平台）。"""
        return (product.product_id, product.platform)


# ============================================================
# 便捷工厂函数
# ============================================================
def create_selection_sync_service() -> SyncService:
    """创建选品池同步服务。"""
    from src.config import settings
    return SyncService(
        table_id=settings.feishu_table_id_selection, table_name="选品池"
    )


def create_review_sync_service() -> SyncService:
    """创建评论库同步服务。"""
    from src.config import settings
    return SyncService(
        table_id=settings.feishu_table_id_review, table_name="评论库"
    )


def create_report_sync_service() -> SyncService:
    """创建分析报告同步服务。"""
    from src.config import settings
    return SyncService(
        table_id=settings.feishu_table_id_report, table_name="分析报告"
    )
