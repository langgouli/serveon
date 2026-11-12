"""测试完整业务流程：采集→分析→推送。"""

from src.scheduler.tasks import product_collection_task, selection_analysis_task


def test_full_workflow():
    """测试完整业务流程。"""
    print("=== 完整业务流程测试 ===\n")

    # 1. 采集任务
    print("1. 执行采集任务...")
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

    # 2. 分析任务
    print("\n2. 执行分析任务...")
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
    test_full_workflow()
