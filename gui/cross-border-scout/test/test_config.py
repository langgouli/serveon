"""Task 0.3 配置测试。

验证 config.py 字段齐全、.env 加载、类型校验。
覆盖：正常（默认值/字段存在/env 加载）、边界（空.env）、异常（非法类型）。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.config import Settings


def test_default_settings(tmp_path) -> None:
    """正常场景：默认配置加载，关键字段有默认值。"""
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    s = Settings(_env_file=str(env_file))
    assert s.feishu_app_id == ""
    assert s.data_retention_days == 3
    assert s.log_level == "INFO"


def test_project_specific_fields() -> None:
    """正常场景：本项目 4 张表 ID 字段齐全。"""
    s = Settings()
    assert hasattr(s, "feishu_table_id_collection_config")
    assert hasattr(s, "feishu_table_id_selection")
    assert hasattr(s, "feishu_table_id_review")
    assert hasattr(s, "feishu_table_id_report")


def test_env_loading(tmp_path) -> None:
    """正常场景：.env 文件正确加载为配置值。"""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "FEISHU_APP_ID=test_app\n"
        "FEISHU_TABLE_ID_REVIEW=tbl_review\n"
        "DATA_RETENTION_DAYS=7\n",
        encoding="utf-8",
    )
    s = Settings(_env_file=str(env_file))
    assert s.feishu_app_id == "test_app"
    assert s.feishu_table_id_review == "tbl_review"
    assert s.data_retention_days == 7


def test_empty_env_uses_defaults(tmp_path) -> None:
    """边界场景：空 .env 走默认值。"""
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    s = Settings(_env_file=str(env_file))
    assert s.feishu_app_id == ""
    assert s.data_retention_days == 3


def test_invalid_type_raises(tmp_path) -> None:
    """异常场景：非整数值赋给 int 字段抛 ValidationError。"""
    env_file = tmp_path / ".env"
    env_file.write_text("DATA_RETENTION_DAYS=abc\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        Settings(_env_file=str(env_file))
