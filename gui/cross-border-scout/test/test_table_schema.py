"""Task 0.4 飞书表结构测试。

验证 4 张表字段完整、类型正确、主键字段存在、选项合法。
覆盖：正常（4表/字段/类型/选项）、边界（主键唯一）、异常（表缺失）。
"""

from __future__ import annotations

import pytest

from src.feishu.table_schema import ALL_TABLES, FieldType


def test_four_tables_exist() -> None:
    """正常场景：4 张表齐全。"""
    assert set(ALL_TABLES.keys()) == {"采集配置", "选品池", "评论库", "分析报告"}


@pytest.mark.parametrize(
    "table_name, required_fields",
    [
        ("采集配置", {"配置ID", "行业", "平台", "采集数量", "启用状态"}),
        ("选品池", {"商品ID", "商品名称", "行业", "平台", "评分", "评论数", "商品链接"}),
        ("评论库", {"评论ID", "商品ID", "评论内容", "评分", "是否差评"}),
        ("分析报告", {"报告ID", "行业", "平台", "分析时间", "决策", "风险等级", "top_picks", "summary"}),
    ],
)
def test_table_required_fields(table_name: str, required_fields: set) -> None:
    """正常场景：每张表含必需字段。"""
    fields = ALL_TABLES[table_name]
    field_names = {f["field_name"] for f in fields}
    for rf in required_fields:
        assert rf in field_names, f"{table_name} 缺少字段: {rf}"


def test_field_types_valid() -> None:
    """正常场景：字段类型在合法枚举内。"""
    valid_types = {
        FieldType.TEXT, FieldType.NUMBER, FieldType.SINGLE_SELECT,
        FieldType.MULTI_SELECT, FieldType.DATETIME, FieldType.CHECKBOX,
        FieldType.URL, FieldType.AUTO_NUMBER,
    }
    for table_name, fields in ALL_TABLES.items():
        for f in fields:
            assert f["type"] in valid_types, f"{table_name} 字段 {f['field_name']} 类型非法"


def test_field_names_unique() -> None:
    """边界场景：每张表字段名不重复。"""
    for table_name, fields in ALL_TABLES.items():
        names = [f["field_name"] for f in fields]
        assert len(names) == len(set(names)), f"{table_name} 字段名重复"


def test_selection_platform_options() -> None:
    """正常场景：选品池平台选项为三平台。"""
    fields = ALL_TABLES["选品池"]
    platform_field = next(f for f in fields if f["field_name"] == "平台")
    options = {o["name"] for o in platform_field["property"]["options"]}
    assert options == {"亚马逊", "Walmart", "eBay"}


def test_report_decision_options() -> None:
    """正常场景：分析报告决策选项为五档。"""
    fields = ALL_TABLES["分析报告"]
    decision_field = next(f for f in fields if f["field_name"] == "决策")
    options = {o["name"] for o in decision_field["property"]["options"]}
    assert options == {"强烈推荐", "谨慎推荐", "值得尝试", "暂不推荐", "建议避开"}


def test_missing_table_raises() -> None:
    """异常场景：不存在的表访问抛 KeyError。"""
    with pytest.raises(KeyError):
        ALL_TABLES["不存在的表"]
