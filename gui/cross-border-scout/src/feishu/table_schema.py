"""多维表格表结构定义。

本项目 4 张核心业务表的字段配置，用于自动创建多维表格数据表。
字段类型参考飞书 Bitable API 文档。

飞书字段类型（field_type）枚举值：
  1 = 多行文本       2 = 数字（含小数）
  3 = 单选           4 = 多选
  5 = 日期时间       7 = 复选框
  15 = 超链接
  1005 = 自动编号
"""

from __future__ import annotations


class FieldType:
    TEXT = 1
    NUMBER = 2
    SINGLE_SELECT = 3
    MULTI_SELECT = 4
    DATETIME = 5
    CHECKBOX = 7
    URL = 15
    AUTO_NUMBER = 1005


# 平台选项（本项目三平台）
_PLATFORM_OPTIONS = [
    {"name": "亚马逊"},
    {"name": "Walmart"},
    {"name": "eBay"},
]


# ============================================================
# 表1：采集配置表
# ============================================================
COLLECTION_CONFIG_TABLE_FIELDS = [
    {"field_name": "配置ID", "type": FieldType.TEXT},
    {"field_name": "行业", "type": FieldType.TEXT},
    {"field_name": "平台", "type": FieldType.MULTI_SELECT, "property": {"options": _PLATFORM_OPTIONS}},
    {"field_name": "采集数量", "type": FieldType.NUMBER, "property": {"formatter": "0"}},
    {"field_name": "评论采集数", "type": FieldType.NUMBER, "property": {"formatter": "0"}},
    {"field_name": "优先级", "type": FieldType.NUMBER, "property": {"formatter": "0"}},
    {"field_name": "启用状态", "type": FieldType.SINGLE_SELECT, "property": {"options": [
        {"name": "启用"}, {"name": "停用"},
    ]}},
    {"field_name": "采集频率", "type": FieldType.TEXT},
    {"field_name": "创建时间", "type": FieldType.DATETIME, "property": {"date_formatter": "yyyy-MM-dd HH:mm"}},
]


# ============================================================
# 表2：选品池表
# ============================================================
SELECTION_TABLE_FIELDS = [
    {"field_name": "商品ID", "type": FieldType.TEXT},
    {"field_name": "商品名称", "type": FieldType.TEXT},
    {"field_name": "行业", "type": FieldType.TEXT},
    {"field_name": "平台", "type": FieldType.SINGLE_SELECT, "property": {"options": _PLATFORM_OPTIONS}},
    {"field_name": "价格区间", "type": FieldType.TEXT},
    {"field_name": "评分", "type": FieldType.NUMBER, "property": {"formatter": "0.0"}},
    {"field_name": "评论数", "type": FieldType.NUMBER, "property": {"formatter": "0"}},
    {"field_name": "排名", "type": FieldType.NUMBER, "property": {"formatter": "0"}},
    {"field_name": "市场容量", "type": FieldType.SINGLE_SELECT, "property": {"options": [
        {"name": "高"}, {"name": "中"}, {"name": "低"},
    ]}},
    {"field_name": "竞争强度", "type": FieldType.SINGLE_SELECT, "property": {"options": [
        {"name": "激烈"}, {"name": "中等"}, {"name": "蓝海"},
    ]}},
    {"field_name": "利润空间", "type": FieldType.SINGLE_SELECT, "property": {"options": [
        {"name": "高"}, {"name": "中"}, {"name": "低"},
    ]}},
    {"field_name": "商品链接", "type": FieldType.URL},
    {"field_name": "更新时间", "type": FieldType.DATETIME, "property": {"date_formatter": "yyyy-MM-dd HH:mm"}},
]


# ============================================================
# 表3：评论库表
# ============================================================
REVIEW_TABLE_FIELDS = [
    {"field_name": "评论ID", "type": FieldType.TEXT},
    {"field_name": "商品ID", "type": FieldType.TEXT},
    {"field_name": "评论内容", "type": FieldType.TEXT},
    {"field_name": "评分", "type": FieldType.NUMBER, "property": {"formatter": "0"}},
    {"field_name": "评论时间", "type": FieldType.DATETIME, "property": {"date_formatter": "yyyy-MM-dd HH:mm"}},
    {"field_name": "是否差评", "type": FieldType.CHECKBOX},
]


# ============================================================
# 表4：分析报告表
# ============================================================
REPORT_TABLE_FIELDS = [
    {"field_name": "报告ID", "type": FieldType.TEXT},
    {"field_name": "行业", "type": FieldType.TEXT},
    {"field_name": "平台", "type": FieldType.SINGLE_SELECT, "property": {"options": _PLATFORM_OPTIONS}},
    {"field_name": "分析时间", "type": FieldType.DATETIME, "property": {"date_formatter": "yyyy-MM-dd HH:mm"}},
    {"field_name": "四角度JSON", "type": FieldType.TEXT},
    {"field_name": "六维度评分", "type": FieldType.TEXT},
    {"field_name": "决策", "type": FieldType.SINGLE_SELECT, "property": {"options": [
        {"name": "强烈推荐"}, {"name": "谨慎推荐"}, {"name": "值得尝试"},
        {"name": "暂不推荐"}, {"name": "建议避开"},
    ]}},
    {"field_name": "风险等级", "type": FieldType.SINGLE_SELECT, "property": {"options": [
        {"name": "低"}, {"name": "中"}, {"name": "高"},
    ]}},
    {"field_name": "top_picks", "type": FieldType.TEXT},
    {"field_name": "summary", "type": FieldType.TEXT},
]


# 所有表的配置汇总，供批量创建使用
ALL_TABLES = {
    "采集配置": COLLECTION_CONFIG_TABLE_FIELDS,
    "选品池": SELECTION_TABLE_FIELDS,
    "评论库": REVIEW_TABLE_FIELDS,
    "分析报告": REPORT_TABLE_FIELDS,
}
