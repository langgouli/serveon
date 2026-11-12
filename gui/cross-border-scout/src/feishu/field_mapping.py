"""字段映射配置：集中管理飞书表格字段名，避免硬编码。

本项目 4 张表（采集配置/选品池/评论库/分析报告）的字段映射。
提供 ProductData -> 飞书记录的转换函数，及增量同步主键定义。
"""

from __future__ import annotations

from typing import Any

from src.pipeline.collectors.base import ProductData


# ============================================================
# 主键定义（用于增量同步去重判断）
# ============================================================
# 选品池：按 商品ID+平台 去重
SELECTION_PRIMARY_KEYS = ["商品ID", "平台"]
# 评论库：按 评论ID 去重
REVIEW_PRIMARY_KEYS = ["评论ID"]
# 分析报告：按 报告ID 去重
REPORT_PRIMARY_KEYS = ["报告ID"]


# ============================================================
# 选品池字段名映射
# ============================================================
SELECTION_FIELDS = {
    "name": "商品名称",
    "product_id": "商品ID",
    "industry": "行业",
    "platform": "平台",
    "price": "价格区间",
    "rating": "评分",
    "review_count": "评论数",
    "rank": "排名",
    "url": "商品链接",
}


# ============================================================
# 转换函数
# ============================================================
def product_to_record(product: ProductData) -> dict[str, Any]:
    """将 ProductData 转换为飞书选品池记录。

    Args:
        product: 商品信息对象

    Returns:
        飞书表格字段字典（字段名对应选品池表）
    """
    return {
        "商品ID": product.product_id,
        "商品名称": product.name,
        "行业": product.industry,
        "平台": product.platform,
        "价格区间": f"{product.price}美金",
        "评分": product.rating,
        "评论数": product.review_count,
        "排名": product.rank,
        "商品链接": {"link": product.url, "text": product.name},
        "更新时间": int(product.collected_at.timestamp() * 1000),
    }


def extract_primary_values(
    record_fields: dict[str, Any], primary_keys: list[str]
) -> tuple[Any, ...]:
    """从飞书记录字段中提取主键值。

    飞书多行文本字段返回 [{"text": "..."}] 格式，需要提取纯文本。

    Args:
        record_fields: 飞书记录的 fields 字典
        primary_keys: 主键字段名列表

    Returns:
        主键值元组，可用于字典 key 去重
    """
    values = []
    for key in primary_keys:
        value = record_fields.get(key)
        values.append(_extract_text(value))
    return tuple(values)


def _extract_text(value: Any) -> str:
    """从飞书字段值中提取纯文本。

    飞书字段类型与返回格式对应关系：
    - 多行文本: [{"text": "..."}]
    - 单选: {"name": "..."} 或 直接字符串
    - 数字: 直接数字
    - 超链接: {"link": "...", "text": "..."}
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            if "text" in first:
                return str(first["text"])
            if "name" in first:
                return str(first["name"])
            return ""
        return str(first)
    if isinstance(value, dict):
        if "name" in value:
            return str(value["name"])
        if "text" in value:
            return str(value["text"])
        if "link" in value:
            return str(value["link"])
        if "date" in value:
            return str(value["date"])
    return str(value)
