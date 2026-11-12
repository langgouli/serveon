"""测试完整业务流程（只采集1条数据）。"""

from src.config import settings
from src.feishu.bitable import bitable_client
from src.scheduler.tasks import product_collection_task, selection_analysis_task


def test_minimal_workflow():
    """测试最小化业务流程。"""
    print("=== 最小化业务流程测试（只采集1条数据）===\n")

    # 1. 更新采集配置为只采集1条数据
    print("1. 更新采集配置为只采集1条数据...")
    try:
        # 查询现有的采集配置
        records = bitable_client.query_records(settings.feishu_table_id_collection_config)
        if not records:
            print("   [ERROR] 没有采集配置")
            return

        # 更新第一个配置的采集数量为1
        first_record = records[0]
        record_id = first_record.get("record_id")
        fields = first_record.get("fields", {})

        # 更新采集数量为1
        bitable_client.update_record(
            settings.feishu_table_id_collection_config,
            record_id,
            {"采集数量": 1, "评论采集数": 0}
        )
        print(f"   [OK] 已更新配置 {record_id}: 采集数量=1")
    except Exception as e:
        print(f"   [ERROR] 更新配置失败: {e}")
        return

    # 2. 采集任务
    print("\n2. 执行采集任务...")
    try:
        result = product_collection_task()
        print(f"   状态: {result.get('status')}")
        if result.get("status") == "success":
            print(f"   采集商品数: {result.get('total_products')}")
            print(f"   新增数: {result.get('new_count')}")
        elif result.get("status") == "skipped":
            print(f"   跳过原因: {result.get('reason')}")
        else:
            print(f"   错误: {result.get('error')}")
    except Exception as e:
        print(f"   [ERROR] 采集任务异常: {e}")

    # 3. 恢复采集配置
    print("\n3. 恢复采集配置...")
    try:
        bitable_client.update_record(
            settings.feishu_table_id_collection_config,
            record_id,
            {"采集数量": 10, "评论采集数": 5}
        )
        print(f"   [OK] 已恢复配置: 采集数量=10")
    except Exception as e:
        print(f"   [ERROR] 恢复配置失败: {e}")

    # 4. 分析任务
    print("\n4. 执行分析任务...")
    try:
        result = selection_analysis_task()
        print(f"   状态: {result.get('status')}")
        if result.get("status") == "success":
            print(f"   分析总数: {result.get('total')}")
            print(f"   成功数: {result.get('success_count')}")
        elif result.get("status") == "skipped":
            print(f"   跳过原因: {result.get('reason')}")
        else:
            print(f"   错误: {result.get('error')}")
    except Exception as e:
        print(f"   [ERROR] 分析任务异常: {e}")

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    test_minimal_workflow()
