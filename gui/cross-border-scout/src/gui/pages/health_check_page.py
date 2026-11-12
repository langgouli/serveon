"""健康检查页：检查飞书连通性和 AI 模型可用性。

检查项：
1. 飞书应用凭证配置
2. 飞书多维表格连通性
3. AI 模型凭证配置
4. 调度器状态
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


class HealthCheckPage(QWidget):
    """健康检查页。"""

    def __init__(self) -> None:
        super().__init__()
        self._init_ui()

    def _init_ui(self) -> None:
        """初始化 UI。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)

        # 标题
        title = QLabel("健康检查")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #303133;")
        layout.addWidget(title)

        # 检查项
        check_group = QGroupBox("检查项")
        check_layout = QVBoxLayout(check_group)

        # 飞书凭证
        self.feishu_cred_label = QLabel("飞书应用凭证: 检查中...")
        check_layout.addWidget(self.feishu_cred_label)

        # 飞书连通性
        self.feishu_conn_label = QLabel("飞书多维表格连通性: 检查中...")
        check_layout.addWidget(self.feishu_conn_label)

        # AI 模型凭证
        self.ai_cred_label = QLabel("AI 模型凭证: 检查中...")
        check_layout.addWidget(self.ai_cred_label)

        # 表 ID 配置
        self.table_id_label = QLabel("表 ID 配置: 检查中...")
        check_layout.addWidget(self.table_id_label)

        layout.addWidget(check_group)

        # 检查按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.check_btn = QPushButton("🔍 开始检查")
        self.check_btn.clicked.connect(self.run_checks)
        button_layout.addWidget(self.check_btn)
        layout.addLayout(button_layout)

        layout.addStretch()

    def run_checks(self) -> None:
        """执行健康检查。"""
        # 检查飞书凭证
        if settings.feishu_app_id and settings.feishu_app_secret:
            self.feishu_cred_label.setText("✅ 飞书应用凭证: 已配置")
            self.feishu_cred_label.setStyleSheet("color: #67c23a;")
        else:
            self.feishu_cred_label.setText("❌ 飞书应用凭证: 未配置")
            self.feishu_cred_label.setStyleSheet("color: #f56c6c;")

        # 检查 AI 模型凭证
        has_ai = (
            settings.openai_api_key and settings.openai_api_key != "sk-xxxxxxxx"
        ) or (
            settings.anthropic_api_key and settings.anthropic_api_key != "sk-ant-xxxxxxxx"
        )
        if has_ai:
            self.ai_cred_label.setText("✅ AI 模型凭证: 已配置")
            self.ai_cred_label.setStyleSheet("color: #67c23a;")
        else:
            self.ai_cred_label.setText("❌ AI 模型凭证: 未配置")
            self.ai_cred_label.setStyleSheet("color: #f56c6c;")

        # 检查表 ID 配置
        tables = [
            ("采集配置", settings.feishu_table_id_collection_config),
            ("选品池", settings.feishu_table_id_selection),
            ("评论库", settings.feishu_table_id_review),
            ("分析报告", settings.feishu_table_id_report),
        ]
        configured = sum(1 for _, tid in tables if tid)
        if configured == 4:
            self.table_id_label.setText("✅ 表 ID 配置: 全部已配置")
            self.table_id_label.setStyleSheet("color: #67c23a;")
        else:
            missing = [name for name, tid in tables if not tid]
            self.table_id_label.setText(f"⚠️ 表 ID 配置: {len(missing)} 个未配置 ({', '.join(missing)})")
            self.table_id_label.setStyleSheet("color: #e6a23c;")

        # 检查飞书连通性（需要先有凭证和表 ID）
        if settings.feishu_app_id and settings.feishu_table_id_selection:
            try:
                from src.feishu.bitable import bitable_client
                records = bitable_client.query_records(settings.feishu_table_id_selection, page_size=1)
                self.feishu_conn_label.setText("✅ 飞书多维表格连通性: 正常")
                self.feishu_conn_label.setStyleSheet("color: #67c23a;")
            except Exception as e:
                self.feishu_conn_label.setText(f"❌ 飞书多维表格连通性: 失败 ({e})")
                self.feishu_conn_label.setStyleSheet("color: #f56c6c;")
        else:
            self.feishu_conn_label.setText("⚠️ 飞书多维表格连通性: 跳过（凭证或表 ID 未配置）")
            self.feishu_conn_label.setStyleSheet("color: #e6a23c;")
