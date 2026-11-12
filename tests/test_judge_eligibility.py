"""M2 判定链路单测：eligibility 分流/兜底/安全网（离线确定性，monkeypatch 数据面）。

覆盖：supported→确认链路；unsupported→模板终态；缺参→need_args→规则兜底；
无效负结论→打回；硬事实矛盾→deterministic_guard 渲染不支持答复。
"""
from __future__ import annotations

import pytest

from app.react_v2.tools_box import tl_advance_refund

FACTS = {
    "found": True, "order_number": "ORD001", "status": "signed",
    "signed_at": "2026-11-07T00:00:00", "days": 9, "amount": 299.0,
    "product": "耳机", "is_special": False, "eta": None,
}
ELIG_SUPP = {"verdict": "supported", "evidence": "签收9天",
             "policy_refs": ["《退换货政策》第3条"], "reasoning": "窗口内"}
ELIG_UNSUPP = {"verdict": "unsupported", "evidence": "签收9天超期",
               "policy_refs": ["《换货政策》第11条"], "reasoning": "超7天换货窗口"}


def _run(args: dict, slots: dict, monkeypatch: pytest.MonkeyPatch,
         facts: dict = FACTS, record=None) -> dict:
    from app.graph.nodes import aftersales as af
    monkeypatch.setattr(af, "verify_identity_node", lambda st: {"user_id": 1001})
    monkeypatch.setattr(af, "_find_order_record",
                        lambda sid, no: _record_view(record) if record else None)
    monkeypatch.setattr(af, "_status_query_guard", lambda *a, **k: None)
    monkeypatch.setattr(af, "order_facts", lambda *a, **k: facts)
    monkeypatch.setattr(af, "collect_info", lambda st: {"entity_slots": {}})
    monkeypatch.setattr(af, "preview_detail", lambda st: {"final_response": ""})
    monkeypatch.setattr(af, "review_message", lambda *a, **k: "转人工复核")
    monkeypatch.setattr(af, "unsupported_message", lambda *a, **k: "规则不支持")
    return tl_advance_refund(args, slots, "tj")


def _record_view(rec: dict) -> dict:
    return {"order_number": rec["order_number"], "refund_record": rec,
            "status": rec.get("status", "pending")}


def test_supported_sets_collect_info(monkeypatch):
    slots = {}
    args = {"user_msg": "我要退货退款ORD001", "order_no": "ORD001",
            "request_type": "RETURN_REFUND", "eligibility": ELIG_SUPP}
    env = _run(args, slots, monkeypatch)
    info = env["slots"]["refund_info"]
    elig = info.get("eligibility") or {}
    assert elig["verdict"] == "supported" and elig["source"] == "model"
    # supported 消费后状态机自动流转 collect_info→preview→previewing_done
    assert info["_refund_status"] in ("collect_info", "preview", "previewing_done")
    assert env["data"]["status"] == info["_refund_status"]
    assert env["data"].get("unsupported_template") is None


def test_unsupported_template_envelope(monkeypatch):
    args = {"user_msg": "我要换货ORD001", "order_no": "ORD001",
            "request_type": "EXCHANGE", "eligibility": ELIG_UNSUPP}
    slots = {}
    env = _run(args, slots, monkeypatch)
    data = env["data"]
    assert data["status"] == "unsupported"
    assert "unsupported_template" in data and "不支持答复结构" in data["unsupported_template"]
    assert "不建单" in data["hint"]
    info = env["slots"]["refund_info"]
    assert info["_refund_status"] == "unsupported" and env.get("needs_human") is False
    assert info["eligibility"]["verdict"] == "unsupported"
    assert info.get("_judge_param") is None or "_eligibility_param" not in info


def test_missing_judge_need_args_then_fallback(monkeypatch):
    args = {"user_msg": "我要退货退款ORD001", "order_no": "ORD001",
            "request_type": "RETURN_REFUND"}  # 无 eligibility
    slots = {}
    env1 = _run(args, slots, monkeypatch)
    assert env1["status"] == "need_args"
    assert "eligibility" in env1["missing_fields"]
    slots2 = env1["slots"]
    env2 = _run(args, slots2, monkeypatch)  # 第 2 次缺参 → 兜底规则判据
    info = env2["slots"]["refund_info"]
    assert info.get("eligibility", {}).get("source") == "rules"
    # 兜底判 supported → 自动流转 collect_info→preview→previewing_done
    assert info["_refund_status"] in ("collect_info", "preview", "previewing_done")
    assert env2["data"]["status"] == info["_refund_status"]


def test_invalid_negative_verdict_kicked(monkeypatch):
    slots = {}
    args = {"user_msg": "我要退货退款ORD001", "order_no": "ORD001",
            "request_type": "RETURN_REFUND",
            "eligibility": {"verdict": "unsupported", "evidence": "", "policy_refs": []}}
    env = _run(args, slots, monkeypatch)
    info = env["slots"]["refund_info"]
    assert env["status"] == "need_args"
    assert "_eligibility_param" not in info       # 已被机器消费
    assert "_judge_invalid" not in info           # 无效标记被消费（打回轮）
    assert info["eligibility"]["source"] == "model"  # 机器已留档判定
    assert info["_judge_miss_count"] == 1         # 打回计数 +1


def test_deterministic_guard_blocks_wrong_supported(monkeypatch):
    # 定制商品却判 supported → 安全网渲染不支持答复（不建单不转人）
    custom_facts = dict(FACTS, is_special=True)
    slots = {}
    args = {"user_msg": "我要退货退款ORD001", "order_no": "ORD001",
            "request_type": "RETURN_REFUND", "eligibility": ELIG_SUPP}
    env = _run(args, slots, monkeypatch, facts=custom_facts)
    info = env["slots"]["refund_info"]
    assert info["eligibility"]["source"] == "deterministic_guard"
    assert env["needs_human"] is False
    assert info["_refund_status"] == "unsupported"
    resp = (env["data"] or {}).get("final_response", "")
    assert "不符合政策支持条件" in resp


def test_existing_active_refund_blocked_first(monkeypatch):
    # 已有在途单：先于判定被拒办（needs_human=False 口径）
    rec = {"order_number": "ORD001", "refund_record": {"status": "waiting_return"},
           "request_type": "RETURN_REFUND", "amount": 299.0, "_refund_status": "waiting_return"}
    slots = {}
    args = {"user_msg": "我要退货退款ORD001", "order_no": "ORD001",
            "request_type": "RETURN_REFUND", "eligibility": ELIG_SUPP}
    env = _run(args, slots, monkeypatch, record=rec)
    resp = (env["data"] or {}).get("final_response", "")
    assert "无法再发起新的售后" in resp
    assert env["needs_human"] is False
