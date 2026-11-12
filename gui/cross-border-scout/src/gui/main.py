"""GUI 入口：启动主窗口。

用法：
    python -m src.gui.main
"""

from __future__ import annotations

import sys


def main() -> None:
    """启动 GUI 主窗口。"""
    from PySide6.QtWidgets import QApplication

    from src.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
