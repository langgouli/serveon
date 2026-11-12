"""情绪识别 + 安抚一体化服务（F1）：单 prompt、单 Agent 完成情绪判定与安抚话术。

v2 改造：原 analyze_emotion + generate_soothe 两次调用合并为单次 LLM 调用
（task="emotion_assist"，见 llm.py 模板），一次返回 emotion/intensity/soothe，
避免情绪调用慢于业务收口导致安抚丢失。Mock 模式同样走合并后的 task。
"""
from __future__ import annotations

from typing import Any

from app.config import Config
from app.services.llm import get_llm_client


def emotion_assist(msg: str, history=None) -> dict:
    """情绪识别 + 安抚话术（一次调用完成）。

    返回 {emotion, intensity, level, source, needs_clarify, soothe}：
    - emotion ∈ calm/upset/angry
    - soothe：angry/upset 时为安抚话术（共情+道歉+订单号引导），calm 时恒为空串
    - level：intensity ≥ 阈值时按情绪取「激动/不满」，否则「平静」

    异常向上抛给调用方（emotion_agent 做异常隔离，绝不连累业务）。
    """
    llm = get_llm_client()
    result = llm.complete("emotion_assist", msg)
    if not isinstance(result, dict):
        result = {}

    emotion = result.get("emotion", "calm")
    try:
        intensity = float(result.get("intensity", 0.2))
    except (TypeError, ValueError):
        intensity = 0.2
    if emotion not in ("calm", "upset", "angry"):
        emotion = "calm"
    soothe = result.get("soothe") or ""
    if not isinstance(soothe, str):
        soothe = ""

    needs_clarify = 0.4 <= intensity < Config.EMOTION_INTENSITY_THRESHOLD
    level = "激动" if (intensity >= Config.EMOTION_INTENSITY_THRESHOLD and emotion == "angry") \
        else ("不满" if intensity >= Config.EMOTION_INTENSITY_THRESHOLD else "平静")

    return {
        "emotion": emotion,
        "intensity": intensity,
        "level": level,
        "source": type(llm).__name__,
        "needs_clarify": needs_clarify,
        "soothe": soothe,
    }
