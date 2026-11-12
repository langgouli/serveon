"""系统配置页：飞书凭证、AI模型、表ID配置。

用户在此页填写配置，保存到 .env 文件，调用 reload_settings() 立即生效。
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.config import settings
from src.gui.services.env_service import EnvService


class ConfigPage(QWidget):
    """系统配置页。"""

    def __init__(self) -> None:
        super().__init__()
        self._init_ui()
        self._load_config()

    def _init_ui(self) -> None:
        """初始化 UI。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)

        # 标题
        title = QLabel("系统配置")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #303133;")
        layout.addWidget(title)

        # 飞书配置
        feishu_group = QGroupBox("飞书配置")
        feishu_form = QFormLayout(feishu_group)

        self.app_id_edit = QLineEdit()
        self.app_secret_edit = QLineEdit()
        self.app_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.bitable_token_edit = QLineEdit()
        self.tenant_domain_edit = QLineEdit()

        feishu_form.addRow("App ID:", self.app_id_edit)
        feishu_form.addRow("App Secret:", self.app_secret_edit)
        feishu_form.addRow("多维表格 App Token:", self.bitable_token_edit)
        feishu_form.addRow("租户域名:", self.tenant_domain_edit)

        layout.addWidget(feishu_group)

        # 表ID配置
        table_group = QGroupBox("表ID配置")
        table_form = QFormLayout(table_group)

        self.table_config_edit = QLineEdit()
        self.table_selection_edit = QLineEdit()
        self.table_review_edit = QLineEdit()
        self.table_report_edit = QLineEdit()

        table_form.addRow("采集配置表 ID:", self.table_config_edit)
        table_form.addRow("选品池表 ID:", self.table_selection_edit)
        table_form.addRow("评论库表 ID:", self.table_review_edit)
        table_form.addRow("分析报告表 ID:", self.table_report_edit)

        layout.addWidget(table_group)

        # AI 模型配置
        ai_group = QGroupBox("AI 模型配置")
        ai_form = QFormLayout(ai_group)

        self.openai_key_edit = QLineEdit()
        self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_base_edit = QLineEdit()
        self.anthropic_key_edit = QLineEdit()
        self.anthropic_key_edit.setEchoMode(QLineEdit.EchoMode.Password)

        ai_form.addRow("OpenAI API Key:", self.openai_key_edit)
        ai_form.addRow("OpenAI Base URL:", self.openai_base_edit)
        ai_form.addRow("Anthropic API Key:", self.anthropic_key_edit)

        layout.addWidget(ai_group)

        # 按钮行
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.save_btn = QPushButton("保存配置")
        self.save_btn.setStyleSheet(
            "QPushButton { background-color: #409eff; color: white; "
            "padding: 8px 24px; border-radius: 4px; font-size: 14px; }"
            "QPushButton:hover { background-color: #66b1ff; }"
        )
        self.save_btn.clicked.connect(self._save_config)
        button_layout.addWidget(self.save_btn)

        layout.addLayout(button_layout)
        layout.addStretch()

    def _load_config(self) -> None:
        """从 settings 加载当前配置。"""
        self.app_id_edit.setText(settings.feishu_app_id)
        self.app_secret_edit.setText(settings.feishu_app_secret)
        self.bitable_token_edit.setText(settings.feishu_bitable_app_token)
        self.tenant_domain_edit.setText(settings.feishu_tenant_domain)

        self.table_config_edit.setText(settings.feishu_table_id_collection_config)
        self.table_selection_edit.setText(settings.feishu_table_id_selection)
        self.table_review_edit.setText(settings.feishu_table_id_review)
        self.table_report_edit.setText(settings.feishu_table_id_report)

        self.openai_key_edit.setText(settings.openai_api_key)
        self.openai_base_edit.setText(settings.openai_api_base)
        self.anthropic_key_edit.setText(settings.anthropic_api_key)

    def _save_config(self) -> None:
        """保存配置到 .env 文件。"""
        env_data = {
            "FEISHU_APP_ID": self.app_id_edit.text().strip(),
            "FEISHU_APP_SECRET": self.app_secret_edit.text().strip(),
            "FEISHU_BITABLE_APP_TOKEN": self.bitable_token_edit.text().strip(),
            "FEISHU_TENANT_DOMAIN": self.tenant_domain_edit.text().strip(),

            "FEISHU_TABLE_ID_COLLECTION_CONFIG": self.table_config_edit.text().strip(),
            "FEISHU_TABLE_ID_SELECTION": self.table_selection_edit.text().strip(),
            "FEISHU_TABLE_ID_REVIEW": self.table_review_edit.text().strip(),
            "FEISHU_TABLE_ID_REPORT": self.table_report_edit.text().strip(),

            "OPENAI_API_KEY": self.openai_key_edit.text().strip(),
            "OPENAI_API_BASE": self.openai_base_edit.text().strip(),
            "ANTHROPIC_API_KEY": self.anthropic_key_edit.text().strip(),
        }

        try:
            EnvService.save_env(env_data)

            # 重新加载配置
            from src.config import reload_settings
            reload_settings()

            QMessageBox.information(self, "成功", "配置已保存并生效")

        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存失败: {e}")
