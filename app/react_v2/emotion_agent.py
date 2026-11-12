"""v2 情绪识别回复 Agent：与主循环并行，超时降级、异常隔离（§2.3）。

v2 改造：情绪识别与安抚话术由单 prompt、单 Agent（emotion_assist，见
emotion_service.emotion_assist）一次完成，不再拆两次 LLM 调用。
规则不变：
- emotion ∈ {angry, upset} 且会话安抚次数 < SOOTHE_MAX_PER_SESSION=2 → 生成安抚话术
- 情绪平稳 → 空；异常 → ("", False)（绝不连累业务）
"""
from __future__ import annotations

import asyncio

from app.config import Config
from app.services.emotion_service import emotion_assist
from app.utils.logger import log_event


def detect_and_soothe(user_message: str, slots: dict) -> tuple[str, bool]:
    """返回 (安抚话术, 是否应计入安抚计数)。异常 → ("", False)。"""
    try:
        result = emotion_assist(user_message)
        should = result.get("emotion") in ("angry", "upset")
    except Exception as e:
        log_event("-", "v2_emotion_error", input="", output=f"{type(e).__name__}:{e}")
        return "", False
    if not should:
        return "", False
    if int(slots.get("_soothe_count", 0) or 0) >= Config.SOOTHE_MAX_PER_SESSION:
        return "", False
    text = result.get("soothe") or ""
    return text, bool(text)


async def emotion_branch(user_message: str, slots: dict) -> tuple[str, bool]:
    """并发分支入口：同步网络调用放到线程执行，主循环 await 时带硬超时。"""
    return await asyncio.to_thread(detect_and_soothe, user_message, slots)
