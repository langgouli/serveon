"""统一启动入口：启动 GUI + 调度器。

用法：
    python -m src.main              # 启动 GUI + 后台调度器
    python -m src.main --scheduler  # 仅启动调度器（命令行模式）
    python -m src.main --gui        # 仅启动 GUI
"""

from __future__ import annotations

import sys


def main() -> None:
    """统一启动入口。"""
    mode = sys.argv[1] if len(sys.argv) > 1 else "--gui"

    if mode == "--scheduler":
        # 仅启动调度器
        from src.scheduler.scheduler import SchedulerManager

        manager = SchedulerManager(blocking=True)
        manager.start()

    elif mode == "--gui":
        # 启动 GUI（同时启动后台调度器）
        from PySide6.QtWidgets import QApplication

        from src.gui.main_window import MainWindow

        # 启动后台调度器
        try:
            from src.scheduler.scheduler import SchedulerManager

            scheduler = SchedulerManager(blocking=False)
            scheduler.register_all_tasks()
            scheduler.start()
        except Exception as e:
            print(f"调度器启动失败（不影响 GUI）: {e}")

        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())

    else:
        print("用法：")
        print("  python -m src.main              # 启动 GUI + 后台调度器")
        print("  python -m src.main --scheduler  # 仅启动调度器")
        print("  python -m src.main --gui        # 仅启动 GUI")


if __name__ == "__main__":
    main()
