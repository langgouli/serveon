"""结构化节点日志：记录每个节点的输入/输出/耗时，支持按会话回放整条链路。"""
from __future__ import annotations

import functools
import inspect
import logging
import threading
import time
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

# 当前会话 ID：chat 入口设置，LLM 调用等无 state 的日志自动带会话
_current_session: ContextVar[str] = ContextVar("session_id", default="-")


def set_session(session_id: str) -> None:
    _current_session.set(session_id)


def current_session() -> str:
    return _current_session.get()


_banner_lock = threading.Lock()


def _write_raw(line: str) -> None:
    """以最简格式独立追加一行到 node.log（不依赖 logging handler 内部结构），
    同步输出到控制台。"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full = f"{ts} | {line}"
    with _banner_lock:
        with open(_LOG_DIR / "node.log", "a", encoding="utf-8") as f:
            f.write(full + "\n")
    print(full, flush=True)


def round_banner(session_id: str, text: str) -> None:
    """在日志中画一条明显的一轮对话分隔线（会话 ID + 提问）。"""
    _write_raw(f"[对话回合开始] session={session_id} | {text}")


def round_footer(session_id: str, text: str = "") -> None:
    """回合结束标记（耗时、路由等）。"""
    _write_raw(f"[对话回合结束] session={session_id} | {text}")


class _NodeFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.session = getattr(record, "session", "-")
        record.node = getattr(record, "node", "-")
        record.input = getattr(record, "input", "")
        record.output = getattr(record, "output", "")
        record.elapsed = getattr(record, "elapsed", "")
        return True


_logger = logging.getLogger("serveon.node")
if not _logger.handlers:
    _logger.setLevel(logging.INFO)
    _logger.propagate = False
    _fmt = logging.Formatter(
        "%(asctime)s | %(session)s | %(node)s | in=%(input)s | out=%(output)s | %(elapsed)sms"
    )
    _file_handler = logging.FileHandler(
        _LOG_DIR / "node.log", encoding="utf-8", delay=True
    )
    _file_handler.setFormatter(_fmt)
    _file_handler.addFilter(_NodeFilter())
    _logger.addHandler(_file_handler)
    _console = logging.StreamHandler()
    _console.setFormatter(_fmt)
    _console.addFilter(_NodeFilter())
    _logger.addHandler(_console)


_MAX_PREVIEW = 100  # 日志中字符串预览最大长度


def _brief(value: Any) -> str:
    """摘要截断，避免日志过长。"""
    if value is None:
        return ""
    s = value if isinstance(value, str) else str(value)
    return s if len(s) <= _MAX_PREVIEW else s[:_MAX_PREVIEW] + "..."


def log_event(
    session_id: str,
    node: str,
    input: Any = "",
    output: Any = "",
    elapsed: Any = "",
    level: int = logging.INFO,
) -> None:
    """通用结构化日志（节点执行、LLM 调用、状态推进等）。

    session_id 传 "-" 时自动取当前会话（供 LLM 调用等无 state 的站点使用）。
    """
    _logger.log(
        level,
        "visited",
        extra={
            "session": _brief(session_id if session_id != "-" else current_session()),
            "node": node,
            "input": _brief(input),
            "output": _brief(output),
            "elapsed": elapsed,
        },
    )


def node_log(fn: Callable) -> Callable:
    """图节点装饰器：记录输入/输出/耗时，同步异步通用。

    节点签名约定：fn(state: dict) -> dict。
    输入摘要取 user_message，输出摘要取 final_response，其余字段截断兜底。
    """
    import inspect

    if inspect.iscoroutinefunction(fn):
        @functools.wraps(fn)
        async def async_wrapper(state: dict) -> dict:
            session_id = state.get("session_id", "-") if isinstance(state, dict) else "-"
            t0 = time.perf_counter()
            try:
                result = await fn(state)
            except Exception:
                elapsed = f"{round((time.perf_counter() - t0) * 1000)}"
                log_event(session_id, fn.__name__, input=_brief(state), output="EXCEPTION", elapsed=elapsed, level=logging.ERROR)
                raise
            elapsed = f"{round((time.perf_counter() - t0) * 1000)}"
            result = result or {}
            log_event(
                session_id,
                fn.__name__,
                input=state.get("user_message", _brief(state)),
                output=result.get("final_response", _brief(result)),
                elapsed=elapsed,
            )
            return result
        return async_wrapper

    @functools.wraps(fn)
    def sync_wrapper(state: dict) -> dict:
        session_id = state.get("session_id", "-") if isinstance(state, dict) else "-"
        t0 = time.perf_counter()
        try:
            result = fn(state)
        except Exception:
            elapsed = f"{round((time.perf_counter() - t0) * 1000)}"
            log_event(session_id, fn.__name__, input=_brief(state), output="EXCEPTION", elapsed=elapsed, level=logging.ERROR)
            raise
        elapsed = f"{round((time.perf_counter() - t0) * 1000)}"
        result = result or {}
        log_event(
            session_id,
            fn.__name__,
            input=state.get("user_message", _brief(state)),
            output=result.get("final_response", _brief(result)),
            elapsed=elapsed,
        )
        return result
    return sync_wrapper
