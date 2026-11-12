"""测试向4张表添加记录。

验证bitable_client.add_record功能。
"""

from src.config import settings
from src.feishu.bitable import bitable_client


def test_add_records():
    """测试向4张表添加记录。"""
    print("=== 添加记录测试 ===\n")

    # 1. 采集配置表
    print("1. 向采集配置表添加记录...")
    try:
        record_id = bitable_client.add_record(
            settings.feishu_table_id_collection_config,
            {
                "配置ID": "test_001",
                "行业": "3C数码",
                "平台": ["亚马逊"],
                "采集数量": 100,
                "评论采集数": 50,
                "优先级": 1,
                "启用状态": "启用",
                "采集频率": "每日",
            },
        )
        print(f"   [OK] 记录添加成功: {record_id}")
    except Exception as e:
        print(f"   [ERROR] 添加失败: {e}")

    # 2. 选品池表
    print("\n2. 向选品池表添加记录...")
    try:
        record_id = bitable_client.add_record(
            settings.feishu_table_id_selection,
            {
                "商品ID": "prod_001",
                "商品名称": "测试商品",
                "行业": "3C数码",
                "平台": "亚马逊",
                "价格区间": "10-50",
                "评分": 4.5,
                "评论数": 200,
                "排名": 10,
                "市场容量": "高",
                "竞争强度": "中等",
                "利润空间": "中",
                "商品链接": {"link": "https://example.com", "text": "示例商品"},
            },
        )
        print(f"   [OK] 记录添加成功: {record_id}")
    except Exception as e:
        print(f"   [ERROR] 添加失败: {e}")

    # 3. 评论库表
    print("\n3. 向评论库表添加记录...")
    try:
        record_id = bitable_client.add_record(
            settings.feishu_table_id_review,
            {
                "评论ID": "review_001",
                "商品ID": "prod_001",
                "评论内容": "这个产品很好用",
                "评分": 5,
                "是否差评": False,
            },
        )
        print(f"   [OK] 记录添加成功: {record_id}")
    except Exception as e:
        print(f"   [ERROR] 添加失败: {e}")

    # 4. 分析报告表
    print("\n4. 向分析报告表添加记录...")
    try:
        record_id = bitable_client.add_record(
            settings.feishu_table_id_report,
            {
                "报告ID": "report_001",
                "行业": "3C数码",
                "平台": "亚马逊",
                "四角度JSON": '{"demand":8,"competition":6,"profit":7,"risk":4}',
                "六维度评分": '{"评分":7.5}',
                "决策": "谨慎推荐",
                "风险等级": "中",
                "top_picks": "商品A,商品B",
                "summary": "市场机会中等",
            },
        )
        print(f"   [OK] 记录添加成功: {record_id}")
    except Exception as e:
        print(f"   [ERROR] 添加失败: {e}")

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    test_add_records()
