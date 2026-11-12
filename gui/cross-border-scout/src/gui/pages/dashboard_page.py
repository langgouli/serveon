"""数据看板页：展示采集统计和分析结果。

从飞书多维表格读取数据，展示：
1. 采集统计：总商品数、新增数、更新数
2. 分析报告列表：最新分析报告
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.config import settings
from src.feishu.bitable import bitable_client
from src.feishu.field_mapping import _extract_text


class DashboardPage(QWidget):
    """数据看板页。"""

    def __init__(self) -> None:
        super().__init__()
        self._init_ui()

    def _init_ui(self) -> None:
        """初始化 UI。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)

        # 标题
        title = QLabel("数据看板")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #303133;")
        layout.addWidget(title)

        # 统计卡片区
        stats_layout = QHBoxLayout()

        # 选品池统计
        selection_group = QGroupBox("选品池")
        selection_layout = QVBoxLayout(selection_group)
        self.selection_count_label = QLabel("0")
        self.selection_count_label.setStyleSheet("font-size: 28px; font-weight: 700; color: #409eff;")
        selection_layout.addWidget(self.selection_count_label)
        selection_layout.addWidget(QLabel("商品总数"))
        stats_layout.addWidget(selection_group)

        # 评论库统计
        review_group = QGroupBox("评论库")
        review_layout = QVBoxLayout(review_group)
        self.review_count_label = QLabel("0")
        self.review_count_label.setStyleSheet("font-size: 28px; font-weight: 700; color: #67c23a;")
        review_layout.addWidget(self.review_count_label)
        review_layout.addWidget(QLabel("评论总数"))
        stats_layout.addWidget(review_group)

        # 分析报告统计
        report_group = QGroupBox("分析报告")
        report_layout = QVBoxLayout(report_group)
        self.report_count_label = QLabel("0")
        self.report_count_label.setStyleSheet("font-size: 28px; font-weight: 700; color: #e6a23c;")
        report_layout.addWidget(self.report_count_label)
        report_layout.addWidget(QLabel("报告总数"))
        stats_layout.addWidget(report_group)

        layout.addLayout(stats_layout)

        # 刷新按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.refresh_btn = QPushButton("🔄 刷新数据")
        self.refresh_btn.clicked.connect(self.refresh_data)
        button_layout.addWidget(self.refresh_btn)
        layout.addLayout(button_layout)

        layout.addStretch()

    def refresh_data(self) -> None:
        """刷新统计数据。"""
        try:
            # 查询选品池
            selection_count = 0
            if settings.feishu_table_id_selection:
                records = bitable_client.query_records(settings.feishu_table_id_selection)
                selection_count = len(records)
            self.selection_count_label.setText(str(selection_count))

            # 查询评论库
            review_count = 0
            if settings.feishu_table_id_review:
                records = bitable_client.query_records(settings.feishu_table_id_review)
                review_count = len(records)
            self.review_count_label.setText(str(review_count))

            # 查询分析报告
            report_count = 0
            if settings.feishu_table_id_report:
                records = bitable_client.query_records(settings.feishu_table_id_report)
                report_count = len(records)
            self.report_count_label.setText(str(report_count))

        except Exception as e:
            self.selection_count_label.setText("错误")
            self.review_count_label.setText("错误")
            self.report_count_label.setText("错误")
