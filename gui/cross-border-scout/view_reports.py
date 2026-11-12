"""查看分析报告表数据。"""

import json
from src.config import settings
from src.feishu.bitable import bitable_client


def view_reports():
    """查看分析报告表数据。"""
    print("=== 分析报告表数据 ===\n")

    table_id = settings.feishu_table_id_report
    records = bitable_client.query_records(table_id)

    print(f"总记录数: {len(records)}\n")

    for i, record in enumerate(records, 1):
        print(f"--- 报告 {i} ---")
        print(f"record_id: {record.get('record_id')}")
        fields = record.get("fields", {})
        print(f"行业: {fields.get('行业')}")
        print(f"平台: {fields.get('平台')}")
        print(f"决策: {fields.get('决策')}")
        print(f"风险等级: {fields.get('风险等级')}")

        # 查看top_picks
        top_picks_raw = fields.get('top_picks', '')
        print(f"top_picks原始值: {top_picks_raw[:200] if top_picks_raw else '空'}")
        if isinstance(top_picks_raw, str):
            try:
                top_picks = json.loads(top_picks_raw)
                print(f"top_picks数量: {len(top_picks)}")
                if top_picks:
                    print(f"第一个商品ID: {top_picks[0].get('商品ID')}")
            except json.JSONDecodeError:
                print(f"top_picks解析失败")

        # 查看summary
        summary = fields.get('summary', '')
        print(f"summary: {summary[:100] if summary else '空'}")
        print()


if __name__ == "__main__":
    view_reports()
