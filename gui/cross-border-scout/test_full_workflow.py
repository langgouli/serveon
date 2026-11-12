"""添加采集配置并运行完整业务流程测试。"""

from src.config import settings
from src.feishu.bitable import bitable_client


def add_collection_config():
    """添加采集配置。"""
    print("=== 添加采集配置 ===\n")

    record_id = bitable_client.add_record(
        settings.feishu_table_id_collection_config,
        {
            "配置ID": "cfg_001",
            "行业": "3C数码",
            "平台": ["亚马逊"],
            "采集数量": 10,
            "评论采集数": 5,
            "优先级": 1,
            "启用状态": "启用",
            "采集频率": "每日",
        },
    )
    print(f"[OK] 采集配置添加成功: {record_id}")
    return record_id


if __name__ == "__main__":
    add_collection_config()
