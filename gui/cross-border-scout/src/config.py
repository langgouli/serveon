"""项目配置中心：统一从环境变量读取配置，避免散落在各模块。"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_env_file() -> str:
    """获取 .env 文件路径。

    打包模式（PyInstaller frozen）：exe 同目录
    开发模式：项目根目录下的 .env
    """
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve().parent / ".env")
    return ".env"


class Settings(BaseSettings):
    """全局配置，从 .env 文件读取。"""

    model_config = SettingsConfigDict(
        env_file=_resolve_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 飞书应用凭证
    feishu_app_id: str = Field(default="", description="飞书应用 App ID")
    feishu_app_secret: str = Field(default="", description="飞书应用 App Secret")

    # 飞书多维表格
    feishu_bitable_app_token: str = Field(default="", description="多维表格 App Token")
    feishu_tenant_domain: str = Field(
        default="",
        description="飞书企业租户域名（如 ocndodd7lmyr.feishu.cn 中的 ocndodd7lmyr），"
        "用于生成在飞书桌面端可直接打开的链接",
    )
    # 本项目 4 张表
    feishu_table_id_collection_config: str = Field(
        default="", description="采集配置表 ID"
    )
    feishu_table_id_selection: str = Field(default="", description="选品池表 ID")
    feishu_table_id_review: str = Field(default="", description="评论库表 ID")
    feishu_table_id_report: str = Field(default="", description="分析报告表 ID")

    # 飞书机器人
    feishu_webhook_url: str = Field(default="", description="Webhook 机器人地址")
    feishu_chat_id: str = Field(
        default="",
        description="飞书群聊 ID（应用机器人发送消息用）",
    )

    # AI 模型
    openai_api_key: str = Field(default="", description="OpenAI API Key")
    # OpenAI 兼容接口的 Base URL
    # 留空走 OpenAI 官方，填国内大模型兼容端点可切换：
    #   DeepSeek:     https://api.deepseek.com/v1
    #   通义千问:      https://dashscope.aliyuncs.com/compatible-mode/v1
    #   智谱 GLM:     https://open.bigmodel.cn/api/paas/v4/
    #   月之暗面 Kimi: https://api.moonshot.cn/v1
    openai_api_base: str = Field(
        default="",
        description="OpenAI 兼容接口的 Base URL，留空走官方，填国内大模型兼容端点可切换",
    )
    anthropic_api_key: str = Field(default="", description="Anthropic API Key")

    # 业务配置
    data_retention_days: int = Field(
        default=3, description="数据保留天数（超过此天数的数据将被自动清理）"
    )

    # 日志
    log_level: str = Field(default="INFO", description="日志级别")


# 全局单例，import 即用
settings = Settings()


def reload_settings() -> Settings:
    """重新加载配置：从 .env 文件重新读取配置并更新全局单例的属性。

    业务用户在 GUI 配置页保存 .env 后调用本函数，
    让 feishu_auth / health_check 等模块立即读到最新配置。

    实现原理：不替换 settings 对象（因为其他模块已 import 旧引用），
    而是用新配置更新现有对象的 __dict__，所有持有引用的模块都能看到新值。
    """
    # 重置 feishu_auth 的 token 缓存，避免用旧 token
    try:
        from src.feishu.auth import feishu_auth
        feishu_auth._token = None
        feishu_auth._expires_at = 0.0
    except Exception:
        pass

    # 重新从 .env 读取配置，更新现有对象的属性（不替换对象本身）
    new_settings = Settings()
    settings.__dict__.update(new_settings.__dict__)
    return settings
