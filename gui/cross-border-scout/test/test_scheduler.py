"""Task 5.1-5.3 调度模块测试。

覆盖：正常（触发器配置/任务执行/调度器注册）、边界（空配置/无表ID）、异常（任务失败）。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.scheduler.triggers import (
    ALL_TRIGGERS,
    COLLECTION_TRIGGER,
    DATA_CLEANUP_TRIGGER,
    SELECTION_ANALYSIS_TRIGGER,
)
from src.scheduler.tasks import (
    _extract_field_value,
    _load_collection_configs,
    data_cleanup_task,
    product_collection_task,
    selection_analysis_task,
)


# ============ triggers ============

def test_all_triggers_has_three() -> None:
    """正常场景：ALL_TRIGGERS 含三个触发器。"""
    assert len(ALL_TRIGGERS) == 3
    ids = [t["id"] for t in ALL_TRIGGERS]
    assert "product_collection" in ids
    assert "selection_analysis" in ids
    assert "data_cleanup" in ids


def test_collection_trigger_config() -> None:
    """正常场景：采集触发器配置正确。"""
    assert COLLECTION_TRIGGER["hour"] == 9
    assert COLLECTION_TRIGGER["minute"] == 0


def test_selection_analysis_trigger_config() -> None:
    """正常场景：分析触发器配置正确（18:00）。"""
    assert SELECTION_ANALYSIS_TRIGGER["hour"] == 18
    assert SELECTION_ANALYSIS_TRIGGER["minute"] == 0


def test_data_cleanup_trigger_config() -> None:
    """正常场景：清理触发器配置正确。"""
    assert DATA_CLEANUP_TRIGGER["day"] == "*/3"
    assert DATA_CLEANUP_TRIGGER["hour"] == 2


# ============ _extract_field_value ============

def test_extract_field_value_text() -> None:
    """正常场景：文本字段。"""
    assert _extract_field_value([{"text": "宠物用品"}]) == "宠物用品"


def test_extract_field_value_single_select() -> None:
    """正常场景：单选字段。"""
    assert _extract_field_value([{"name": "亚马逊"}]) == "亚马逊"


def test_extract_field_value_string() -> None:
    """正常场景：字符串字段。"""
    assert _extract_field_value("宠物用品") == "宠物用品"


def test_extract_field_value_none() -> None:
    """边界场景：None 返回默认值。"""
    assert _extract_field_value(None, "默认") == "默认"


def test_extract_field_value_empty_list() -> None:
    """边界场景：空列表返回默认值。"""
    assert _extract_field_value([], "默认") == "默认"


# ============ _load_collection_configs ============

def test_load_collection_configs_success() -> None:
    """正常场景：加载启用配置。"""
    records = [
        {
            "record_id": "rec1",
            "fields": {
                "行业": [{"text": "宠物用品"}],
                "平台": [{"name": "亚马逊"}, {"name": "eBay"}],
                "采集数量": 20,
                "评论采集数": 5,
                "启用状态": [{"name": "启用"}],
            },
        }
    ]
    fake_client = MagicMock()
    fake_client.query_records.return_value = records

    with patch("src.scheduler.tasks.bitable_client", fake_client), \
         patch("src.scheduler.tasks.settings") as mock_settings:
        mock_settings.feishu_table_id_collection_config = "t_config"
        configs = _load_collection_configs()
        assert len(configs) == 1
        assert configs[0]["industry"] == "宠物用品"
        assert configs[0]["platforms"] == ["亚马逊", "eBay"]


def test_load_collection_configs_no_table_id() -> None:
    """边界场景：未配置表 ID 返回空。"""
    with patch("src.scheduler.tasks.settings") as mock_settings:
        mock_settings.feishu_table_id_collection_config = ""
        assert _load_collection_configs() == []


def test_load_collection_configs_disabled() -> None:
    """正常场景：停用状态被过滤。"""
    records = [
        {
            "record_id": "rec1",
            "fields": {
                "行业": [{"text": "宠物用品"}],
                "平台": [{"name": "亚马逊"}],
                "启用状态": [{"name": "停用"}],
            },
        }
    ]
    fake_client = MagicMock()
    fake_client.query_records.return_value = records

    with patch("src.scheduler.tasks.bitable_client", fake_client), \
         patch("src.scheduler.tasks.settings") as mock_settings:
        mock_settings.feishu_table_id_collection_config = "t_config"
        assert _load_collection_configs() == []


# ============ product_collection_task ============

def test_product_collection_task_no_configs() -> None:
    """边界场景：无启用配置返回跳过。"""
    with patch("src.scheduler.tasks._load_collection_configs", return_value=[]):
        result = product_collection_task()
        assert result["status"] == "skipped"


def test_product_collection_task_success() -> None:
    """正常场景：采集成功。"""
    configs = [{"industry": "宠物用品", "platforms": ["亚马逊"], "collect_count": 5}]

    with patch("src.scheduler.tasks._load_collection_configs", return_value=configs), \
         patch("src.pipeline.collectors.collection_config.CollectionConfig"), \
         patch("src.pipeline.collection_runner.CollectionRunner") as mock_runner_class, \
         patch("src.feishu.application_bot.application_bot") as mock_bot, \
         patch("src.feishu.card_templates.build_collection_report_card") as mock_card:
        # 模拟采集结果
        mock_result = MagicMock()
        mock_result.collection_results = [MagicMock(products=[MagicMock(), MagicMock()])]
        mock_result.sync_result = MagicMock(new_count=2, update_count=0, skip_count=0, fail_count=0)
        mock_runner_class.return_value.run.return_value = mock_result

        result = product_collection_task()
        assert result["status"] == "success"
        assert result["total_products"] == 2


def test_product_collection_task_error() -> None:
    """异常场景：采集异常返回错误。"""
    configs = [{"industry": "宠物用品", "platforms": ["亚马逊"], "collect_count": 5}]
    with patch("src.scheduler.tasks._load_collection_configs", return_value=configs), \
         patch("src.pipeline.collectors.collection_config.CollectionConfig"), \
         patch("src.pipeline.collection_runner.CollectionRunner") as mock_runner_class:
        mock_runner_class.return_value.run.side_effect = RuntimeError("采集失败")
        result = product_collection_task()
        assert result["status"] == "error"


# ============ selection_analysis_task ============

def test_selection_analysis_task_no_configs() -> None:
    """边界场景：无启用配置返回跳过。"""
    with patch("src.scheduler.tasks._load_collection_configs", return_value=[]):
        result = selection_analysis_task()
        assert result["status"] == "skipped"


def test_selection_analysis_task_success() -> None:
    """正常场景：分析成功。"""
    configs = [{"industry": "宠物用品", "platforms": ["亚马逊"], "collect_count": 5}]

    with patch("src.scheduler.tasks._load_collection_configs", return_value=configs), \
         patch("src.ai.agents.selection_agent.run_selection_agent") as mock_agent, \
         patch("src.feishu.application_bot.application_bot") as mock_bot, \
         patch("src.feishu.card_templates.build_selection_strategy_card") as mock_card:
        mock_agent.return_value = {
            "success": True,
            "analysis": {"决策": "强烈推荐", "综合评分": 85},
            "error": None,
        }

        result = selection_analysis_task()
        assert result["status"] == "success"
        assert result["success_count"] == 1


def test_selection_analysis_task_partial_failure() -> None:
    """正常场景：部分平台分析失败。"""
    configs = [{"industry": "宠物用品", "platforms": ["亚马逊", "eBay"], "collect_count": 5}]

    with patch("src.scheduler.tasks._load_collection_configs", return_value=configs), \
         patch("src.ai.agents.selection_agent.run_selection_agent") as mock_agent, \
         patch("src.feishu.application_bot.application_bot") as mock_bot, \
         patch("src.feishu.card_templates.build_selection_strategy_card") as mock_card:
        # 第一个平台成功，第二个失败
        mock_agent.side_effect = [
            {"success": True, "analysis": {"决策": "强烈推荐"}, "error": None},
            {"success": False, "analysis": None, "error": "LLM 超时"},
        ]

        result = selection_analysis_task()
        assert result["status"] == "success"
        assert result["total"] == 2
        assert result["success_count"] == 1


def test_selection_analysis_task_agent_exception() -> None:
    """异常场景：Agent 运行异常被捕获。"""
    configs = [{"industry": "宠物用品", "platforms": ["亚马逊"], "collect_count": 5}]

    with patch("src.scheduler.tasks._load_collection_configs", return_value=configs), \
         patch("src.ai.agents.selection_agent.run_selection_agent") as mock_agent, \
         patch("src.feishu.application_bot.application_bot") as mock_bot, \
         patch("src.feishu.card_templates.build_selection_strategy_card") as mock_card:
        mock_agent.side_effect = RuntimeError("Agent 初始化失败")

        result = selection_analysis_task()
        assert result["status"] == "success"
        assert result["success_count"] == 0


# ============ data_cleanup_task ============

def test_data_cleanup_task_success() -> None:
    """正常场景：数据清理成功。"""
    records = [
        {
            "record_id": "rec1",
            "fields": {"更新时间": 1000},  # 老数据
        },
        {
            "record_id": "rec2",
            "fields": {"更新时间": 9999999999999},  # 新数据
        },
    ]
    fake_client = MagicMock()
    fake_client.query_records.return_value = records

    with patch("src.scheduler.tasks.bitable_client", fake_client), \
         patch("src.scheduler.tasks.settings") as mock_settings:
        mock_settings.data_retention_days = 3
        mock_settings.feishu_table_id_selection = "t_selection"
        mock_settings.feishu_table_id_review = ""

        result = data_cleanup_task()
        assert result["status"] == "success"
        # 应该删除 1 条老数据
        assert fake_client.delete_record.call_count == 1


def test_data_cleanup_task_no_tables() -> None:
    """边界场景：无表 ID 跳过清理。"""
    with patch("src.scheduler.tasks.settings") as mock_settings:
        mock_settings.data_retention_days = 3
        mock_settings.feishu_table_id_selection = ""
        mock_settings.feishu_table_id_review = ""
        result = data_cleanup_task()
        assert result["status"] == "success"


def test_data_cleanup_task_error() -> None:
    """异常场景：清理异常返回错误。"""
    with patch("src.scheduler.tasks.settings") as mock_settings:
        mock_settings.data_retention_days = 3
        mock_settings.feishu_table_id_selection = "t_selection"
        mock_settings.feishu_table_id_review = ""

        with patch("src.scheduler.tasks.bitable_client") as mock_client:
            mock_client.query_records.side_effect = RuntimeError("查询失败")
            result = data_cleanup_task()
            assert result["status"] == "error"
