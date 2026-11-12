"""Task 0.2 基础设施模块 import 测试。

验证复制的基础设施模块可正常 import。
覆盖：正常（import 成功）、异常（模块缺失抛 ImportError）。
"""

from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "src.observability.logger",
        "src.observability.llm_monitor",
        "src.observability.metrics_store",
        "src.observability.alert",
        "src.feishu.bitable",
        "src.feishu.auth",
        "src.feishu.application_bot",
        "src.feishu.feishu_bot",
        "src.ai.model_router",
    ],
)
def test_module_imports(module: str) -> None:
    """正常场景：基础设施模块可 import。"""
    mod = importlib.import_module(module)
    assert mod is not None


def test_missing_module_raises() -> None:
    """异常场景：不存在的模块抛 ImportError。"""
    with pytest.raises(ImportError):
        importlib.import_module("src.nonexistent_module")
