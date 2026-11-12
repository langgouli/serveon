"""v2 独立会话存储（不触碰旧 store）：history + entity slots + 计数。

slots 字段与现行 entity_slots 语义对齐：current_order / orders /
refund_info / _soothe_count / _ask_state。
"""
from __future__ import annotations

MAX_HISTORY = 10  # 保留最近 5 轮（user+assistant 各 5 条）


class V2Store:
    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}

    def _session(self, session_id: str) -> dict:
        if session_id not in self._sessions:
            self._sessions[session_id] = {"history": [], "slots": {}}
        return self._sessions[session_id]

    # ---- 读 ----
    def get_history(self, session_id: str) -> list[dict]:
        return list(self._session(session_id)["history"])

    def get_slots(self, session_id: str) -> dict:
        """返回 slots 副本（退款状态机可原地 mutate 后整体写回）。"""
        return dict(self._session(session_id)["slots"])

    # ---- 写 ----
    def append(self, session_id: str, role: str, content: str) -> None:
        s = self._session(session_id)
        s["history"].append({"role": role, "content": content})
        if len(s["history"]) > MAX_HISTORY:
            s["history"] = s["history"][-MAX_HISTORY:]

    def save_slots(self, session_id: str, slots: dict) -> None:
        self._session(session_id)["slots"] = slots

    def reset(self) -> None:
        self._sessions.clear()


store = V2Store()
