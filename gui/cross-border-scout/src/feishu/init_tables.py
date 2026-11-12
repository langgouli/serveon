"""多维表格初始化：创建四张业务表（采集配置/选品池/评论库/分析报告）。

用法：
    python -m src.feishu.init_tables

前置条件：
    1. .env 中已配置 FEISHU_BITABLE_APP_TOKEN
    2. 已创建一张空的多维表格
"""

from __future__ import annotations

from typing import Any

from src.feishu.bitable import bitable_client
from src.observability.logger import get_logger

logger = get_logger()


def init_tables(bitable: Any | None = None) -> dict[str, str]:
    """创建四张业务表。

    Args:
        bitable: 飞书客户端（默认用全局 bitable_client）

    Returns:
        表名到 table_id 的映射
    """
    cli = bitable or bitable_client
    result = cli.create_all_tables()
    logger.info(f"建表完成: {list(result.keys())}")
    return result


def main() -> None:
    """命令行入口：创建表并打印 table_id。"""
    print("=" * 60)
    print("开始创建多维表格数据表...")
    print("=" * 60)
    result = init_tables()
    print("\n" + "=" * 60)
    print("✅ 所有数据表创建成功！")
    print("=" * 60)
    env_mapping = {
        "采集配置": "FEISHU_TABLE_ID_COLLECTION_CONFIG",
        "选品池": "FEISHU_TABLE_ID_SELECTION",
        "评论库": "FEISHU_TABLE_ID_REVIEW",
        "分析报告": "FEISHU_TABLE_ID_REPORT",
    }
    for name, tid in result.items():
        print(f"  {name}: {tid}")
        if name in env_mapping:
            print(f"    → .env: {env_mapping[name]}={tid}")


if __name__ == "__main__":
    main()
