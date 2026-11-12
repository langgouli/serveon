"""测试分析任务。"""

from src.scheduler.tasks import selection_analysis_task


def test_analysis():
    """测试分析任务。"""
    print("=== 分析任务测试 ===\n")

    result = selection_analysis_task()
    print(f"\n状态: {result.get('status')}")
    if result.get("status") == "success":
        print(f"分析总数: {result.get('total')}")
        print(f"成功数: {result.get('success_count')}")
    else:
        print(f"错误: {result.get('error')}")


if __name__ == "__main__":
    test_analysis()
