"""Task 4.1 飞书卡片模板测试。

覆盖：正常（选品策略卡片/采集日报卡片/评论分析卡片）、边界（空数据/无链接）、颜色映射。
"""

from __future__ import annotations

from unittest.mock import patch

from src.feishu.card_templates import (
    DECISION_TEMPLATE_MAP,
    RISK_TEMPLATE_MAP,
    build_collection_report_card,
    build_review_analysis_card,
    build_selection_strategy_card,
    build_table_url,
)


# ============ build_table_url ============

def test_build_table_url_success() -> None:
    """正常场景：生成多维表格链接。"""
    with patch("src.feishu.card_templates.settings") as mock_settings:
        mock_settings.feishu_bitable_app_token = "app_token"
        mock_settings.feishu_tenant_domain = "tenant_domain"
        mock_settings.feishu_table_id_selection = "table_id"
        url = build_table_url()
        assert "https://tenant_domain.feishu.cn/base/app_token" in url
        assert "table=table_id" in url


def test_build_table_url_custom_table() -> None:
    """正常场景：指定表 ID。"""
    with patch("src.feishu.card_templates.settings") as mock_settings:
        mock_settings.feishu_bitable_app_token = "app_token"
        mock_settings.feishu_tenant_domain = "tenant_domain"
        url = build_table_url("custom_table")
        assert "table=custom_table" in url


def test_build_table_url_no_config() -> None:
    """边界场景：未配置返回空字符串。"""
    with patch("src.feishu.card_templates.settings") as mock_settings:
        mock_settings.feishu_bitable_app_token = ""
        mock_settings.feishu_tenant_domain = ""
        mock_settings.feishu_table_id_selection = ""
        assert build_table_url() == ""


# ============ build_selection_strategy_card ============

def test_selection_strategy_card_full() -> None:
    """正常场景：完整选品策略卡片。"""
    analysis = {
        "决策": "强烈推荐",
        "风险等级": "低",
        "综合评分": 85,
        "四角度分析": {
            "市场机会": "市场需求大",
            "竞品定价": "价格合理",
            "用户痛点": "痛点少",
            "利润测算": "利润高",
        },
        "六维度评分": {
            "需求强度": 90,
            "竞争强度": 70,
            "利润率": 85,
            "运营难度": 60,
            "风险等级": 80,
            "机会窗口": 75,
        },
        "top_picks": [
            {"商品ID": "P001", "商品名称": "宠物玩具", "推荐理由": "需求大", "预估利润率": "30%"},
        ],
        "summary": "强烈推荐此品类",
    }
    card = build_selection_strategy_card("宠物用品", "亚马逊", analysis, table_url="http://example.com")
    assert card["header"]["template"] == "green"
    assert card["header"]["title"]["content"] == "🤖 选品策略报告 · 宠物用品"
    assert len(card["elements"]) > 5


def test_selection_strategy_card_decision_colors() -> None:
    """正常场景：不同决策对应不同颜色。"""
    for decision, color in DECISION_TEMPLATE_MAP.items():
        analysis = {"决策": decision, "综合评分": 80, "top_picks": [], "summary": ""}
        card = build_selection_strategy_card("宠物用品", "亚马逊", analysis)
        assert card["header"]["template"] == color


def test_selection_strategy_card_empty_analysis() -> None:
    """边界场景：空分析数据不报错。"""
    card = build_selection_strategy_card("宠物用品", "亚马逊", {})
    assert card["header"]["template"] == "blue"
    assert len(card["elements"]) >= 1


def test_selection_strategy_card_with_top_picks() -> None:
    """正常场景：含 top_picks。"""
    analysis = {
        "决策": "谨慎推荐",
        "top_picks": [
            {"商品ID": "P001", "商品名称": "商品1", "推荐理由": "理由1", "预估利润率": "20%"},
            {"商品ID": "P002", "商品名称": "商品2", "推荐理由": "理由2", "预估利润率": "25%"},
        ],
    }
    card = build_selection_strategy_card("宠物用品", "亚马逊", analysis)
    # 找到 top_picks 区域
    content = str(card["elements"])
    assert "商品1" in content
    assert "商品2" in content


def test_selection_strategy_card_no_table_url() -> None:
    """边界场景：无 table_url 时无按钮。"""
    analysis = {"决策": "强烈推荐", "top_picks": [], "summary": ""}
    with patch("src.feishu.card_templates.settings") as mock_settings:
        mock_settings.feishu_bitable_app_token = ""
        mock_settings.feishu_tenant_domain = ""
        mock_settings.feishu_table_id_report = ""
        card = build_selection_strategy_card("宠物用品", "亚马逊", analysis)
        # 检查是否有按钮
        has_button = any(
            el.get("tag") == "action" for el in card["elements"]
        )
        assert not has_button


# ============ build_collection_report_card ============

def test_collection_report_card_full() -> None:
    """正常场景：完整采集日报卡片。"""
    card = build_collection_report_card(
        "2026-10-30", 10, 20, 5, 3, 2, table_url="http://example.com"
    )
    assert card["header"]["template"] == "blue"
    assert "【采集日报】2026-10-30" in card["header"]["title"]["content"]
    content = str(card["elements"])
    assert "20" in content  # new_count
    assert "5" in content  # update_count
    assert "2" in content  # fail_count


def test_collection_report_card_with_failures() -> None:
    """正常场景：有失败数时显示警告。"""
    card = build_collection_report_card("2026-10-30", 5, 10, 0, 0, 3)
    content = str(card["elements"])
    assert "失败" in content
    assert "3" in content


def test_collection_report_card_no_failures() -> None:
    """正常场景：无失败数时不显示警告。"""
    card = build_collection_report_card("2026-10-30", 5, 10, 5, 0, 0)
    content = str(card["elements"])
    # 失败数为 0，不应有警告
    assert "⚠️" not in content


def test_collection_report_card_total_processed() -> None:
    """正常场景：总处理数计算正确。"""
    card = build_collection_report_card("2026-10-30", 5, 10, 5, 0, 0)
    content = str(card["elements"])
    assert "15" in content  # 10+5


# ============ build_review_analysis_card ============

def test_review_analysis_card_full() -> None:
    """正常场景：完整评论分析卡片。"""
    card = build_review_analysis_card(
        "宠物用品", "亚马逊",
        total_reviews=100,
        negative_count=10,
        avg_rating=4.5,
        key_complaints=["质量差", "物流慢"],
        table_url="http://example.com",
    )
    assert card["header"]["template"] == "blue"  # 差评率 10% < 20%
    assert "📊 评论分析 · 宠物用品" in card["header"]["title"]["content"]
    content = str(card["elements"])
    assert "100" in content
    assert "10" in content
    assert "质量差" in content


def test_review_analysis_card_high_negative_rate() -> None:
    """正常场景：差评率 > 20% 时红色。"""
    card = build_review_analysis_card(
        "宠物用品", "亚马逊",
        total_reviews=100,
        negative_count=30,
        avg_rating=3.0,
        key_complaints=[],
    )
    assert card["header"]["template"] == "red"


def test_review_analysis_card_no_reviews() -> None:
    """边界场景：无评论数据不报错。"""
    card = build_review_analysis_card(
        "宠物用品", "亚马逊",
        total_reviews=0,
        negative_count=0,
        avg_rating=0.0,
        key_complaints=[],
    )
    assert card["header"]["template"] == "blue"
    content = str(card["elements"])
    assert "0" in content


def test_review_analysis_card_no_complaints() -> None:
    """边界场景：无投诉时不显示投诉区域。"""
    card = build_review_analysis_card(
        "宠物用品", "亚马逊",
        total_reviews=50,
        negative_count=5,
        avg_rating=4.0,
        key_complaints=[],
    )
    content = str(card["elements"])
    assert "⚠️ 主要投诉" not in content
