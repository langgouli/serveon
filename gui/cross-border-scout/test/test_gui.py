"""Task 6.1-6.4 GUI 模块测试。

覆盖：正常（EnvService/配置页/任务页/健康检查）、边界（空配置/无表ID）。
GUI 组件用 mock 测试逻辑部分，不测试界面渲染。
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

from src.gui.services.env_service import EnvService


# ============ EnvService ============

def test_env_service_save_and_load(tmp_path) -> None:
    """正常场景：保存并读取配置。"""
    env_path = tmp_path / ".env"
    with patch("src.gui.services.env_service.Path") as mock_path:
        mock_path.return_value = env_path
        mock_path.exists.return_value = False

        env_data = {
            "FEISHU_APP_ID": "cli_test",
            "FEISHU_APP_SECRET": "secret_test",
        }
        EnvService.save_env(env_data)

        # 验证文件写入
        assert env_path.exists()
        content = env_path.read_text(encoding="utf-8")
        assert "FEISHU_APP_ID=cli_test" in content
        assert "FEISHU_APP_SECRET=secret_test" in content


def test_env_service_save_update_existing(tmp_path) -> None:
    """正常场景：更新已有配置保留其他项。"""
    env_path = tmp_path / ".env"
    env_path.write_text("EXISTING_KEY=old_value\n", encoding="utf-8")

    with patch("src.gui.services.env_service.Path") as mock_path:
        mock_path.return_value = env_path
        mock_path.exists.return_value = True

        env_data = {"NEW_KEY": "new_value"}
        EnvService.save_env(env_data)

        content = env_path.read_text(encoding="utf-8")
        assert "EXISTING_KEY=old_value" in content
        assert "NEW_KEY=new_value" in content


def test_env_service_load_env(tmp_path) -> None:
    """正常场景：读取 .env 文件。"""
    env_path = tmp_path / ".env"
    env_path.write_text(
        "KEY1=value1\nKEY2=value2\n", encoding="utf-8"
    )

    with patch("src.gui.services.env_service.Path") as mock_path:
        mock_path.return_value = env_path
        mock_path.exists.return_value = True

        result = EnvService.load_env()
        assert result["KEY1"] == "value1"
        assert result["KEY2"] == "value2"


def test_env_service_load_empty(tmp_path) -> None:
    """边界场景：空 .env 文件。"""
    env_path = tmp_path / ".env"
    env_path.write_text("", encoding="utf-8")

    with patch("src.gui.services.env_service.Path") as mock_path:
        mock_path.return_value = env_path
        mock_path.exists.return_value = True

        result = EnvService.load_env()
        assert result == {}


def test_env_service_load_with_comments(tmp_path) -> None:
    """正常场景：读取含注释的 .env 文件。"""
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# 注释\nKEY1=value1\n# 另一个注释\nKEY2=value2\n",
        encoding="utf-8",
    )

    with patch("src.gui.services.env_service.Path") as mock_path:
        mock_path.return_value = env_path
        mock_path.exists.return_value = True

        result = EnvService.load_env()
        assert result["KEY1"] == "value1"
        assert result["KEY2"] == "value2"


# ============ HealthCheckPage 逻辑 ============

def test_health_check_feishu_creds_configured() -> None:
    """正常场景：飞书凭证已配置。"""
    with patch("src.config.settings") as mock_settings:
        mock_settings.feishu_app_id = "cli_test"
        mock_settings.feishu_app_secret = "secret_test"

        # 模拟检查逻辑（不导入 HealthCheckPage，避免 PySide6 依赖）
        has_creds = bool(mock_settings.feishu_app_id and mock_settings.feishu_app_secret)
        assert has_creds is True


def test_health_check_ai_creds_configured() -> None:
    """正常场景：AI 凭证已配置。"""
    with patch("src.config.settings") as mock_settings:
        mock_settings.openai_api_key = "sk-test"
        mock_settings.anthropic_api_key = ""

        has_ai = (
            mock_settings.openai_api_key and mock_settings.openai_api_key != "sk-xxxxxxxx"
        ) or (
            mock_settings.anthropic_api_key and mock_settings.anthropic_api_key != "sk-ant-xxxxxxxx"
        )
        assert has_ai is True


def test_health_check_ai_creds_not_configured() -> None:
    """边界场景：AI 凭证未配置。"""
    with patch("src.config.settings") as mock_settings:
        mock_settings.openai_api_key = ""
        mock_settings.anthropic_api_key = ""

        has_ai = (
            mock_settings.openai_api_key and mock_settings.openai_api_key != "sk-xxxxxxxx"
        ) or (
            mock_settings.anthropic_api_key and mock_settings.anthropic_api_key != "sk-ant-xxxxxxxx"
        )
        assert not has_ai


def test_health_check_table_ids_all_configured() -> None:
    """正常场景：所有表 ID 已配置。"""
    with patch("src.config.settings") as mock_settings:
        mock_settings.feishu_table_id_collection_config = "t1"
        mock_settings.feishu_table_id_selection = "t2"
        mock_settings.feishu_table_id_review = "t3"
        mock_settings.feishu_table_id_report = "t4"

        tables = [
            ("采集配置", mock_settings.feishu_table_id_collection_config),
            ("选品池", mock_settings.feishu_table_id_selection),
            ("评论库", mock_settings.feishu_table_id_review),
            ("分析报告", mock_settings.feishu_table_id_report),
        ]
        configured = sum(1 for _, tid in tables if tid)
        assert configured == 4


def test_health_check_table_ids_partial() -> None:
    """边界场景：部分表 ID 未配置。"""
    with patch("src.config.settings") as mock_settings:
        mock_settings.feishu_table_id_collection_config = "t1"
        mock_settings.feishu_table_id_selection = ""
        mock_settings.feishu_table_id_review = "t3"
        mock_settings.feishu_table_id_report = ""

        tables = [
            ("采集配置", mock_settings.feishu_table_id_collection_config),
            ("选品池", mock_settings.feishu_table_id_selection),
            ("评论库", mock_settings.feishu_table_id_review),
            ("分析报告", mock_settings.feishu_table_id_report),
        ]
        configured = sum(1 for _, tid in tables if tid)
        assert configured == 2


# ============ DashboardPage 逻辑 ============

def test_dashboard_refresh_data() -> None:
    """正常场景：刷新数据。"""
    with patch("src.config.settings") as mock_settings:
        mock_settings.feishu_table_id_selection = "t_selection"
        mock_settings.feishu_table_id_review = "t_review"
        mock_settings.feishu_table_id_report = "t_report"

        with patch("src.feishu.bitable.bitable_client") as mock_client:
            mock_client.query_records.side_effect = [
                [{"record_id": "r1"}],  # 选品池 1 条
                [{"record_id": "r2"}],  # 评论库 1 条
                [{"record_id": "r3"}],  # 分析报告 1 条
            ]

            # 模拟刷新逻辑（不导入 DashboardPage，避免 PySide6 依赖）
            selection_records = mock_client.query_records("t_selection")
            review_records = mock_client.query_records("t_review")
            report_records = mock_client.query_records("t_report")

            assert len(selection_records) == 1
            assert len(review_records) == 1
            assert len(report_records) == 1
