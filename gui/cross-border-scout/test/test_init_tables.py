"""Task 2.3 建表服务测试。

用 FakeBitable 模拟飞书客户端。
覆盖：正常（建4表/表ID）、边界（空结果）、全局客户端注入。
"""

from __future__ import annotations

from src.feishu import init_tables as init_module
from src.feishu.init_tables import init_tables
from src.feishu.table_schema import ALL_TABLES


class FakeBitable:
    """模拟 bitable 客户端。"""

    def __init__(self, result: dict[str, str] | None = None) -> None:
        self._result = result if result is not None else {
            "采集配置": "t_config",
            "选品池": "t_selection",
            "评论库": "t_review",
            "分析报告": "t_report",
        }

    def create_all_tables(self) -> dict[str, str]:
        return dict(self._result)


def test_init_tables_creates_four() -> None:
    """正常场景：创建四张表。"""
    result = init_tables(bitable=FakeBitable())
    assert set(result.keys()) == {"采集配置", "选品池", "评论库", "分析报告"}


def test_init_tables_empty() -> None:
    """边界场景：空结果返回空字典。"""
    assert init_tables(bitable=FakeBitable(result={})) == {}


def test_init_tables_uses_global_client(monkeypatch) -> None:
    """正常场景：无参数时用全局 bitable_client。"""
    fake = FakeBitable()
    monkeypatch.setattr(init_module, "bitable_client", fake)
    result = init_tables()
    assert len(result) == 4


def test_all_tables_has_four() -> None:
    """正常场景：ALL_TABLES 含四张表。"""
    assert set(ALL_TABLES.keys()) == {"采集配置", "选品池", "评论库", "分析报告"}


def test_init_tables_table_ids_are_strings() -> None:
    """正常场景：表 ID 为字符串。"""
    result = init_tables(bitable=FakeBitable(result={"选品池": "tid123"}))
    assert result["选品池"] == "tid123"
