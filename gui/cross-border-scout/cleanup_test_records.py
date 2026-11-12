"""清理测试数据：删除test_add_records.py添加的4条测试记录。"""

from src.config import settings
from src.feishu.bitable import bitable_client


def cleanup_test_records():
    """删除测试记录。"""
    print("=== 清理测试记录 ===\n")

    # 采集配置表：test_001
    print("1. 删除采集配置表的测试记录...")
    try:
        bitable_client.delete_record(
            settings.feishu_table_id_collection_config,
            "reczz28U3YLAE0L9",
        )
        print("   [OK] 已删除")
    except Exception as e:
        print(f"   [ERROR] 删除失败: {e}")

    # 选品池表：prod_001
    print("\n2. 删除选品池表的测试记录...")
    try:
        bitable_client.delete_record(
            settings.feishu_table_id_selection,
            "reczz28U3YNmyQV3",
        )
        print("   [OK] 已删除")
    except Exception as e:
        print(f"   [ERROR] 删除失败: {e}")

    # 评论库表：review_001
    print("\n3. 删除评论库表的测试记录...")
    try:
        bitable_client.delete_record(
            settings.feishu_table_id_review,
            "reczz28U3YRYpuh1",
        )
        print("   [OK] 已删除")
    except Exception as e:
        print(f"   [ERROR] 删除失败: {e}")

    # 分析报告表：report_001
    print("\n4. 删除分析报告表的测试记录...")
    try:
        bitable_client.delete_record(
            settings.feishu_table_id_report,
            "reczz28U3YUokmnd",
        )
        print("   [OK] 已删除")
    except Exception as e:
        print(f"   [ERROR] 删除失败: {e}")

    print("\n=== 清理完成 ===")


if __name__ == "__main__":
    cleanup_test_records()
