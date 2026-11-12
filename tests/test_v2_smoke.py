"""v2 冒烟：chat_v2 跑一轮「你好」，验证返回结构完整。
离线 mock 也成立——无密钥时 complete_with_tools 返回 error，chat_v2 走转人工兜底，final 非空。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from app.react_v2 import chat_v2  # noqa: E402
from app.react_v2.memory import store  # noqa: E402
from app.services.refund_service import reset_refund_memory  # noqa: E402


@pytest.fixture(autouse=True)
def offline_store(monkeypatch):
    from app.tools import mysql_store
    monkeypatch.setattr(mysql_store.DataStore, "_connect", lambda self: False)


def test_v2_smoke_hello():
    reset_refund_memory()
    store.reset()
    r = asyncio.run(chat_v2("v2-smoke", "你好"))
    assert isinstance(r, dict), r
    fr = r.get("final_response", "")
    assert fr, f"final_response 为空: {r}"
    assert isinstance(r.get("needs_human"), bool), r
    assert "emotion_text" in r, r
    print(f"[v2-smoke] final={fr[:120]!r} needs_human={r['needs_human']}")
