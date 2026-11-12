"""Task 3.2-3.3 选品工具测试。

覆盖：正常（fetch/analyze/save）、边界（空数据/未配置）、异常（查询失败/LLM失败）。
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from src.ai.agents.selection_tools import (
    analyze,
    fetch_products,
    fetch_reviews,
    save_report,
)


class FakeBitable:
    """模拟 bitable_client。"""

    def __init__(self, records: list[dict] | None = None, raise_error: bool = False) -> None:
        self._records = records or []
        self._raise_error = raise_error
        self.created: list[dict] = []

    def query_records(self, table_id: str, filter_condition: dict | None = None, page_size: int = 100) -> list[dict]:
        if self._raise_error:
            raise RuntimeError("查询失败")
        return self._records

    def create_record(self, table_id: str, record: dict) -> str:
        self.created.append(record)
        return "rec_001"


class FakeLLM:
    """模拟 LLM。"""

    def __init__(self, content: str = "", raise_error: bool = False) -> None:
        self._content = content
        self._raise_error = raise_error

    def invoke(self, prompt: str) -> MagicMock:
        if self._raise_error:
            raise RuntimeError("LLM 调用失败")
        response = MagicMock()
        response.content = self._content
        return response


def _make_product_record(pid: str, industry: str, platform: str) -> dict:
    """构造选品池记录。"""
    return {
        "record_id": f"rec_{pid}",
        "fields": {
            "商品ID": [{"text": pid}],
            "商品名称": [{"text": f"商品{pid}"}],
            "行业": [{"text": industry}],
            "平台": [{"name": platform}],
            "价格区间": [{"text": "25美金"}],
            "评分": 4.5,
            "评论数": 100,
            "排名": 10,
        },
    }


def _make_review_record(rid: str, pid: str) -> dict:
    """构造评论库记录。"""
    return {
        "record_id": f"rec_{rid}",
        "fields": {
            "评论ID": [{"text": rid}],
            "商品ID": [{"text": pid}],
            "评论内容": [{"text": "好评"}],
            "评分": 5,
            "是否差评": False,
        },
    }


# ============ fetch_products ============

def test_fetch_products_success() -> None:
    """正常场景：查询选品池返回商品数据。"""
    records = [
        _make_product_record("P001", "宠物用品", "亚马逊"),
        _make_product_record("P002", "宠物用品", "亚马逊"),
    ]
    fake = FakeBitable(records=records)

    with patch("src.ai.agents.selection_tools.bitable_client", fake), \
         patch("src.ai.agents.selection_tools.settings") as mock_settings:
        mock_settings.feishu_table_id_selection = "t_selection"
        result = fetch_products.func(industry="宠物用品", platform="亚马逊")
        data = json.loads(result)
        assert len(data) == 2
        assert data[0]["商品ID"] == "P001"


def test_fetch_products_filter_by_platform() -> None:
    """正常场景：按平台筛选。"""
    records = [
        _make_product_record("P001", "宠物用品", "亚马逊"),
        _make_product_record("P002", "宠物用品", "eBay"),
    ]
    fake = FakeBitable(records=records)

    with patch("src.ai.agents.selection_tools.bitable_client", fake), \
         patch("src.ai.agents.selection_tools.settings") as mock_settings:
        mock_settings.feishu_table_id_selection = "t_selection"
        result = fetch_products.func(industry="宠物用品", platform="亚马逊")
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["平台"] == "亚马逊"


def test_fetch_products_no_table_id() -> None:
    """边界场景：未配置表 ID 返回错误。"""
    with patch("src.ai.agents.selection_tools.settings") as mock_settings:
        mock_settings.feishu_table_id_selection = ""
        result = fetch_products.func(industry="宠物用品", platform="亚马逊")
        data = json.loads(result)
        assert "error" in data


def test_fetch_products_query_error() -> None:
    """异常场景：查询失败返回错误。"""
    fake = FakeBitable(raise_error=True)
    with patch("src.ai.agents.selection_tools.bitable_client", fake), \
         patch("src.ai.agents.selection_tools.settings") as mock_settings:
        mock_settings.feishu_table_id_selection = "t_selection"
        result = fetch_products.func(industry="宠物用品", platform="亚马逊")
        data = json.loads(result)
        assert "error" in data


def test_fetch_products_empty() -> None:
    """边界场景：无匹配商品返回空列表。"""
    fake = FakeBitable(records=[])
    with patch("src.ai.agents.selection_tools.bitable_client", fake), \
         patch("src.ai.agents.selection_tools.settings") as mock_settings:
        mock_settings.feishu_table_id_selection = "t_selection"
        result = fetch_products.func(industry="宠物用品", platform="亚马逊")
        data = json.loads(result)
        assert data == []


# ============ fetch_reviews ============

def test_fetch_reviews_success() -> None:
    """正常场景：查询评论库返回评论数据。"""
    selection_records = [_make_product_record("P001", "宠物用品", "亚马逊")]
    review_records = [
        _make_review_record("R001", "P001"),
        _make_review_record("R002", "P001"),
    ]

    fake_selection = FakeBitable(records=selection_records)
    fake_review = FakeBitable(records=review_records)

    with patch("src.ai.agents.selection_tools.bitable_client") as mock_client, \
         patch("src.ai.agents.selection_tools.settings") as mock_settings:
        mock_settings.feishu_table_id_selection = "t_selection"
        mock_settings.feishu_table_id_review = "t_review"

        def query_side_effect(table_id, filter_condition=None, page_size=100):
            if table_id == "t_selection":
                return fake_selection.query_records(table_id)
            return fake_review.query_records(table_id)

        mock_client.query_records.side_effect = query_side_effect

        result = fetch_reviews.func(industry="宠物用品", platform="亚马逊")
        data = json.loads(result)
        assert len(data) == 2
        assert data[0]["评论ID"] == "R001"


def test_fetch_reviews_no_table_id() -> None:
    """边界场景：未配置表 ID 返回错误。"""
    with patch("src.ai.agents.selection_tools.settings") as mock_settings:
        mock_settings.feishu_table_id_review = ""
        result = fetch_reviews.func(industry="宠物用品", platform="亚马逊")
        data = json.loads(result)
        assert "error" in data


def test_fetch_reviews_no_reviews() -> None:
    """边界场景：无评论数据返回空列表。"""
    selection_records = [_make_product_record("P001", "宠物用品", "亚马逊")]

    with patch("src.ai.agents.selection_tools.bitable_client") as mock_client, \
         patch("src.ai.agents.selection_tools.settings") as mock_settings:
        mock_settings.feishu_table_id_selection = "t_selection"
        mock_settings.feishu_table_id_review = "t_review"

        def query_side_effect(table_id, filter_condition=None, page_size=100):
            if table_id == "t_selection":
                return selection_records
            return []

        mock_client.query_records.side_effect = query_side_effect

        result = fetch_reviews.func(industry="宠物用品", platform="亚马逊")
        data = json.loads(result)
        assert data == []


# ============ analyze ============

def test_analyze_success() -> None:
    """正常场景：LLM 返回 JSON。"""
    llm_response = '```json\n{"综合评分": 85, "决策": "强烈推荐"}\n```'
    fake_llm = FakeLLM(content=llm_response)

    with patch("src.ai.agents.selection_tools.get_model_router") as mock_router:
        mock_router.return_value.get_llm.return_value = fake_llm
        result = analyze.func(
            industry="宠物用品", platform="亚马逊",
            products_json="[]", reviews_json="[]",
        )
        assert "综合评分" in result


def test_analyze_llm_error() -> None:
    """异常场景：LLM 调用失败返回错误。"""
    fake_llm = FakeLLM(raise_error=True)
    with patch("src.ai.agents.selection_tools.get_model_router") as mock_router:
        mock_router.return_value.get_llm.return_value = fake_llm
        result = analyze.func(
            industry="宠物用品", platform="亚马逊",
            products_json="[]", reviews_json="[]",
        )
        data = json.loads(result)
        assert "error" in data


# ============ save_report ============

def test_save_report_success() -> None:
    """正常场景：保存报告到飞书。"""
    analysis_json = json.dumps({
        "行业": "宠物用品", "平台": "亚马逊", "决策": "强烈推荐",
        "风险等级": "低", "top_picks": [], "summary": "推荐",
    }, ensure_ascii=False)

    fake = FakeBitable()
    with patch("src.ai.agents.selection_tools.bitable_client", fake), \
         patch("src.ai.agents.selection_tools.settings") as mock_settings, \
         patch("src.ai.agents.selection_tools.application_bot") as mock_bot:
        mock_settings.feishu_table_id_report = "t_report"
        mock_bot.send_card.return_value = True

        result = save_report.func(analysis_json=analysis_json, push_to_feishu=True)
        data = json.loads(result)
        assert data["saved_to_bitable"] is True
        assert data["pushed_to_feishu"] is True


def test_save_report_with_code_block() -> None:
    """正常场景：LLM 返回带代码块的 JSON。"""
    analysis_json = '```json\n{"行业": "宠物用品", "平台": "亚马逊", "决策": "强烈推荐", "风险等级": "低", "top_picks": [], "summary": "推荐"}\n```'

    fake = FakeBitable()
    with patch("src.ai.agents.selection_tools.bitable_client", fake), \
         patch("src.ai.agents.selection_tools.settings") as mock_settings, \
         patch("src.ai.agents.selection_tools.application_bot") as mock_bot:
        mock_settings.feishu_table_id_report = "t_report"
        mock_bot.send_card.return_value = True

        result = save_report.func(analysis_json=analysis_json, push_to_feishu=False)
        data = json.loads(result)
        assert data["saved_to_bitable"] is True


def test_save_report_no_table_id() -> None:
    """边界场景：未配置表 ID 跳过保存。"""
    analysis_json = json.dumps({
        "行业": "宠物用品", "平台": "亚马逊", "决策": "强烈推荐",
        "风险等级": "低", "top_picks": [], "summary": "推荐",
    }, ensure_ascii=False)

    with patch("src.ai.agents.selection_tools.settings") as mock_settings, \
         patch("src.ai.agents.selection_tools.application_bot") as mock_bot:
        mock_settings.feishu_table_id_report = ""
        mock_bot.send_card.return_value = True

        result = save_report.func(analysis_json=analysis_json, push_to_feishu=False)
        data = json.loads(result)
        assert data["saved_to_bitable"] is False


def test_save_report_invalid_json() -> None:
    """异常场景：无效 JSON 返回错误。"""
    with patch("src.ai.agents.selection_tools.application_bot"):
        result = save_report.func(analysis_json="invalid json", push_to_feishu=False)
        data = json.loads(result)
        assert "error" in data
