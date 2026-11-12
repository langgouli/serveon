"""集中配置：所有阈值可配置，默认值与需求文档一致。"""
from __future__ import annotations

import os
from pathlib import Path


def _load_env_file(path: Path) -> None:
    """轻量 .env 加载：KEY=VALUE 逐行解析，不覆盖已有环境变量。"""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file(Path(__file__).resolve().parent.parent / ".env")


class Config:
    """全局配置。实例化可覆盖默认值，便于测试与后续接入真实环境。"""

    # --- 签收时间分档（D2）---
    SIGN_DAY_TIER1: int = 7      # 第一档：签收后 7 天内
    SIGN_DAY_TIER2: int = 15     # 第二档：7-15 天；>15 天不常规支持
    EXCHANGE_SIGN_WINDOW: int = 7    # 换货窗口：签收 7 天内
    REFUND_WINDOW: int = 15          # 退货退款窗口：签收 15 天内（16 天起不支持）

    # --- 金额转人工阈值（D4）---
    AMOUNT_THRESHOLD: float = 2000.0

    # --- 情绪识别（3.1.2）---
    EMOTION_INTENSITY_THRESHOLD: float = 0.7  # 置信度阈值

    # --- 各追问环节最大轮次（3.3/3.4/设计文档第9节）---
    ASK_ORDER_MAX: int = 2
    ASK_IDENTITY_MAX: int = 2
    ASK_CONFIRM_MAX: int = 3       # 确认环节离题自动取消上限
    ASK_REFUND_TYPE_MAX: int = 2   # 退款类型未明确时的追问上限，超限转人工
    WRITE_REFUND_RETRY: int = 2
    JUDGE_MISS_MAX: int = 1        # 模型缺判 eligibility 打回次数，第 2 次起回退规则判据兜底

    # --- 多轮对话（D13）---
    CONTEXT_WINDOW: int = 5        # 保留最近 5 轮（=10条消息）
    SESSION_TIMEOUT: int = 1800    # 会话超时 30 分钟（秒）

    # --- 订单槽位（A5）---
    MAX_ORDERS: int = 5            # 最多维护 5 条，FIFO 淘汰

    # --- 安抚次数（D6）---
    SOOTHE_MAX_PER_SESSION: int = 2

    # --- 退款状态 ---
    REFUND_STATUS_PENDING: str = "pending"
    REFUND_STATUS_WAIT_RETURN: str = "wait_return"
    REFUND_STATUS_WAIT_SEND: str = "wait_send"
    REFUND_STATUS_DONE: str = "done"
    REFUND_STATUS_CANCELED: str = "canceled"

    # --- LLM / Embedding（密钥与地址从 .env 读取，见项目根 .env.example） ---
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "")       # ark | xf_spark；空走 mock
    EMBED_PROVIDER: str = os.getenv("EMBED_PROVIDER", "")   # ark；空走 mock

    # 火山方舟
    ARK_API_KEY: str = os.getenv("ARK_API_KEY", "")
    ARK_BASE_URL: str = os.getenv(
        "ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding/v3"
    )
    ARK_CHAT_MODEL: str = os.getenv("ARK_CHAT_MODEL", "deepseek-v4.1-flash")
    ARK_EMBED_MODEL: str = os.getenv("ARK_EMBED_MODEL", "doubao-embedding-vision")

    # 讯飞星火
    SPARK_API_KEY: str = os.getenv("SPARK_API_KEY", "")
    SPARK_BASE_URL: str = os.getenv(
        "SPARK_BASE_URL", "https://maas-api.cn-huabei-1.xf-yun.com/v2/chat/completions"
    )
    SPARK_MODEL: str = os.getenv("SPARK_MODEL", "spark-x2.6")


# 默认实例
config = Config()
