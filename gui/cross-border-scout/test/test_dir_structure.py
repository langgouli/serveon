"""Task 0.1 目录结构测试。

验证项目目录树和 __init__.py 文件齐全。
覆盖：正常（目录存在）、异常（目录/文件缺失）。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 期望存在的目录（相对项目根）
EXPECTED_DIRS = [
    "src",
    "src/feishu",
    "src/ai",
    "src/ai/agents",
    "src/pipeline",
    "src/pipeline/collectors",
    "src/pipeline/cleaners",
    "src/pipeline/writers",
    "src/scheduler",
    "src/observability",
    "src/gui",
    "src/gui/pages",
    "src/gui/services",
    "src/gui/widgets",
    "test",
    "docs",
    "data",
]

# 期望存在的 __init__.py（相对项目根）
EXPECTED_INIT = [
    "src/__init__.py",
    "src/feishu/__init__.py",
    "src/ai/__init__.py",
    "src/ai/agents/__init__.py",
    "src/pipeline/__init__.py",
    "src/pipeline/collectors/__init__.py",
    "src/pipeline/cleaners/__init__.py",
    "src/pipeline/writers/__init__.py",
    "src/scheduler/__init__.py",
    "src/observability/__init__.py",
    "src/gui/__init__.py",
    "src/gui/pages/__init__.py",
    "src/gui/services/__init__.py",
    "src/gui/widgets/__init__.py",
    "test/__init__.py",
]


@pytest.mark.parametrize("rel_dir", EXPECTED_DIRS)
def test_dir_exists(rel_dir: str) -> None:
    """正常场景：每个期望目录都存在且是目录。"""
    path = PROJECT_ROOT / rel_dir
    assert path.is_dir(), f"目录缺失: {rel_dir}"


@pytest.mark.parametrize("rel_init", EXPECTED_INIT)
def test_init_file_exists(rel_init: str) -> None:
    """正常场景：每个 __init__.py 都存在。"""
    path = PROJECT_ROOT / rel_init
    assert path.is_file(), f"__init__.py 缺失: {rel_init}"


def test_src_is_importable_package() -> None:
    """正常场景：src 是可导入的 Python 包。"""
    # 把项目根加入 sys.path 后尝试导入
    import sys

    sys.path.insert(0, str(PROJECT_ROOT))
    try:
        import src  # noqa: F401

        assert hasattr(src, "__path__"), "src 应是包"
    finally:
        sys.path.remove(str(PROJECT_ROOT))


def test_missing_dir_raises(tmp_path: Path) -> None:
    """异常场景：目录不存在时 is_dir 返回 False（验证测试逻辑本身）。"""
    missing = tmp_path / "not_exist"
    assert not missing.is_dir()


def test_missing_init_raises(tmp_path: Path) -> None:
    """异常场景：文件不存在时 is_file 返回 False（验证测试逻辑本身）。"""
    missing = tmp_path / "not_exist.py"
    assert not missing.is_file()
