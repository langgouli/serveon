"""清理未知行业/未知平台的测试报告。"""

from src.config import settings
from src.feishu.bitable import bitable_client


def cleanup_unknown_reports():
    """删除未知行业/未知平台的测试报告。"""
    print("=== 清理未知行业/未知平台的测试报告 ===\n")

    table_id = settings.feishu_table_id_report
    records = bitable_client.query_records(table_id)

    deleted_count = 0
    for record in records:
        fields = record.get("fields", {})
        industry = fields.get("行业", "")
        platform = fields.get("平台", "")

        # 检查是否是未知行业/未知平台
        if industry == "未知行业" or platform == "未知平台":
            record_id = record.get("record_id")
            try:
                bitable_client.delete_record(table_id, record_id)
                print(f"[OK] 已删除: {record_id}")
                deleted_count += 1
            except Exception as e:
                print(f"[ERROR] 删除失败 {record_id}: {e}")

    print(f"\n共删除 {deleted_count} 条测试报告")


if __name__ == "__main__":
    cleanup_unknown_reports()
