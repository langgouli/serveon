"""主窗口：侧边栏 + 页面切换。

布局：
    +------+--------------------------+
    | 侧边栏 |                          |
    | 配置  |     当前页面内容          |
    | 任务  |                          |
    | 看板  |                          |
    | 检查  |                          |
    +------+--------------------------+
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.pages.config_page import ConfigPage
from src.gui.pages.dashboard_page import DashboardPage
from src.gui.pages.health_check_page import HealthCheckPage
from src.gui.pages.task_page import TaskPage


class MainWindow(QMainWindow):
    """主窗口：侧边栏导航 + 多页面切换。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("跨境电商选品策略平台 v0.1.0")
        self.resize(1280, 800)
        self._init_ui()

    def _init_ui(self) -> None:
        """初始化 UI 布局。"""
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 侧边栏
        sidebar = self._build_sidebar()
        layout.addWidget(sidebar)

        # 页面堆栈
        self.stack = QStackedWidget()
        self.config_page = ConfigPage()
        self.task_page = TaskPage()
        self.dashboard_page = DashboardPage()
        self.health_check_page = HealthCheckPage()

        # 顺序必须与侧边栏 items 一致
        self.stack.addWidget(self.config_page)
        self.stack.addWidget(self.task_page)
        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.health_check_page)

        layout.addWidget(self.stack, stretch=1)

        self.setCentralWidget(central)

    def _build_sidebar(self) -> QWidget:
        """构建侧边栏。"""
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题
        title = QLabel("选品策略平台")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "background-color: #ffffff; color: #303133; "
            "font-size: 17px; font-weight: 700; padding: 22px 16px; "
            "border-bottom: 1px solid #ebeef5;"
        )
        layout.addWidget(title)

        # 导航菜单
        self.nav = QListWidget()
        self.nav.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        items = [
            "📋  系统配置",
            "⚙️  任务控制",
            "📊  数据看板",
            "🔍  健康检查",
        ]
        for text in items:
            item = QListWidgetItem(text)
            self.nav.addItem(item)
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._on_nav_changed)
        layout.addWidget(self.nav, stretch=1)

        # 状态栏
        self.status_label = QLabel("●  就绪")
        self.status_label.setStyleSheet(
            "background-color: #ffffff; color: #67c23a; "
            "font-size: 12px; padding: 10px; "
            "border-top: 1px solid #ebeef5;"
        )
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        return sidebar

    def _on_nav_changed(self, row: int) -> None:
        """侧边栏切换页面。"""
        self.stack.setCurrentIndex(row)
        # 切换到数据看板时刷新数据
        if row == 2:
            self.dashboard_page.refresh_data()

    def set_status(self, text: str, color: str = "#67c23a") -> None:
        """更新状态栏。"""
        self.status_label.setText(f"●  {text}")
        self.status_label.setStyleSheet(
            f"background-color: #ffffff; color: {color}; "
            "font-size: 12px; padding: 10px; "
            "border-top: 1px solid #ebeef5;"
        )
