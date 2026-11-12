"""v2 LLM 调用封装：function calling + 文本 action 协议双通道。

现行 XfSparkClient/ArkChatClient 只有纯文本 complete()，不支持 tools，
v2 不修改现有代码，在本模块内自带一个 OpenAI 兼容调用器（同 .env 配置），
优先 function calling；接口不支持时回退到模型回复里的 JSON action。
"""
from __future__ import annotations

import json
import re
from typing import Any

import requests

from app.config import config
from app.utils.logger import log_event


def _credentials() -> tuple[str, str, str]:
    provider = config.LLM_PROVIDER
    if provider == "ark":
        return config.ARK_API_KEY, config.ARK_BASE_URL, config.ARK_CHAT_MODEL
    if provider == "xf_spark":
        return config.SPARK_API_KEY, config.SPARK_BASE_URL, config.SPARK_MODEL
    return "", "", ""


def _endpoint(base_url: str) -> str:
    u = base_url.rstrip("/")
    if not u.endswith("/chat/completions"):
        u = u + "/chat/completions"
    return u


def _post(messages: list[dict], tools: list[dict] | None) -> tuple[Any, str | None]:
    """发一次 chat completion。返回 (response json, error)。

    优先带 tools（function calling）；若服务端不接受 tools 参数（4xx/5xx
    报 tools 相关错误），自动回退不带 tools 的纯文本调用。
    """
    key, url, model = _credentials()
    if not key:
        return None, "未配置 LLM 密钥（LLM_PROVIDER/ARK_API_KEY/SPARK_API_KEY）"
    data = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "stream": False,
    }
    if tools:
        data["tools"] = tools
        data["tool_choice"] = "auto"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    def _do(payload):
        log_event("-", "v2_llm_call", input=json.dumps(payload, ensure_ascii=False)[:400])
        resp = requests.post(_endpoint(url), json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        return resp.json()

    try:
        return _do(data), None
    except Exception as first:
        msg = str(first)
        if tools and re.search(r"tool", msg, re.IGNORECASE):
            try:
                log_event("-", "v2_llm_fallback", input="retry without tools")
                return _do({k: v for k, v in data.items() if k not in ("tools", "tool_choice")}), None
            except Exception as second:
                return None, f"{type(second).__name__}: {second}"
        return None, f"{type(first).__name__}: {msg}"


def _extract_action(text: str) -> dict | None:
    """从模型纯文本解析 action JSON：优先 ```json 块，否则取第一个 {...}。"""
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*\{[\s\S]*?\}\s*```", text)
    if not m:
        m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0).strip().strip("```").strip("json").strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    if obj.get("action") and isinstance(obj.get("arguments"), (dict,)):
        nm = str(obj["action"]).strip()
        if nm:
            return {"name": nm, "arguments": obj["arguments"]}
    # 兼容只有 {"name": ..., "arguments": ...} 的形式
    if obj.get("name") and obj.get("arguments") is not None:
        nm = str(obj["name"]).strip()
        if nm:
            return {"name": nm, "arguments": obj["arguments"] or {}}
    return None


def complete_with_tools(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """调用模型。返回：

    {
      "content": str,                 # 模型输出的正文（无工具调用时=最终答复）
      "tool_calls": [{"name": str, "arguments": dict}],
      "error": str | None             # 调用失败时非空
    }
    """
    resp, err = _post(messages, tools)
    if err:
        log_event("-", "v2_llm_error", input="", output=err)
        return {"content": "", "tool_calls": [], "error": err}
    try:
        choice = resp["choices"][0]
        msg = choice.get("message") or {}
        content = msg.get("content") or ""
        calls: list[dict] = []
        raw_calls = msg.get("tool_calls") or []
        for tc in raw_calls:
            fn = tc.get("function", {}) or {}
            name = fn.get("name", "")
            # 部分模型在输出正文的同时夹带空 name 的空调用（序列化毛刺），
            # 不是"未知工具"，直接过滤，避免上层误判转人工。
            if not isinstance(name, str) or not name.strip():
                log_event("-", "v2_llm_drop_empty_call", input="", output=repr(fn))
                continue
            args_raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
            except json.JSONDecodeError:
                args = {}
            calls.append({"name": name, "arguments": args if isinstance(args, dict) else {}})
        log_event("-", "v2_llm_result", input="", output=f"content={content[:200]!r} calls={len(calls)}")
        if not calls and content:
            action = _extract_action(content)
            if action:
                calls.append(action)
                # 去掉正文里的 action 代码块/JSON，避免回灌给模型造成噪声
                content = re.sub(r"```(?:json)?\s*\{[\s\S]*?\}\s*```", "", content).strip()
                if not content:
                    content = "（工具调用中，等待工具结果）"
        return {"content": content, "tool_calls": calls, "error": None}
    except (KeyError, IndexError, TypeError) as e:
        log_event("-", "v2_llm_error", input="", output=f"parse:{e}")
        return {"content": "", "tool_calls": [], "error": f"parse:{type(e).__name__}:{e}"}
