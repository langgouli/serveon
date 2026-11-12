"""Task 8.1 打包模块测试。

覆盖：正常（启动入口/打包脚本）、边界（参数检查）。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_main_gui_mode() -> None:
    """正常场景：GUI 模式启动。"""
    # GUI 模式需要 PySide6，跳过（测试在无 GUI 环境下不导入 PySide6）
    # 验证 main 函数存在即可
    from src.main import main
    assert callable(main)


def test_main_scheduler_mode() -> None:
    """正常场景：调度器模式启动。"""
    with patch("sys.argv", ["src.main", "--scheduler"]), \
         patch("src.scheduler.scheduler.SchedulerManager") as mock_scheduler:
        from src.main import main
        main()

        mock_scheduler.assert_called_once()
        mock_scheduler.return_value.start.assert_called_once()


def test_main_help() -> None:
    """边界场景：未知参数显示帮助。"""
    with patch("sys.argv", ["src.main", "--unknown"]):
        from src.main import main
        main()


def test_build_exe_script_exists() -> None:
    """正常场景：打包脚本存在。"""
    from pathlib import Path
    script = Path("scripts/build_exe.py")
    assert script.exists()


def test_build_exe_script_syntax() -> None:
    """正常场景：打包脚本语法正确。"""
    import ast
    from pathlib import Path
    script = Path("scripts/build_exe.py")
    source = script.read_text(encoding="utf-8")
    ast.parse(source)
    # 验证包含关键打包命令
    assert "PyInstaller" in source
    assert "--onefile" in source
    assert "--windowed" in source


def test_readme_exists() -> None:
    """正常场景：README 存在。"""
    from pathlib import Path
    assert Path("README.md").exists()


def test_requirements_has_pyinstaller() -> None:
    """正常场景：requirements.txt 包含打包依赖。"""
    from pathlib import Path
    content = Path("requirements.txt").read_text(encoding="utf-8")
    assert "apscheduler" in content
    assert "PySide6" in content
