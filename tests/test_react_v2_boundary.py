"""ReAct v2 边界测试：复用现行 40 用例的消息序列与文本断言，驱动 chat_v2。

- v2 无路由概念：断言聚焦 final_response / needs_human / 文本关键短语；
- 已知缺陷（F6 看词劫持/O5）在 v2 语义下应"修复"：断言其 v2 期望（答非所问消失）；
- 默认跑子集（REACT_V2_SUBSET=1 默认开），REACT_V2_FULL=1 跑全量 40；
- 全部用例调用真实模型（LLM_PROVIDER 由 .env 决定），离线数据（DataStore._connect=False）。
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
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


async def _drive_case(msgs: list[str]) -> list[dict]:
    sid = f"rv2-{uuid.uuid4().hex[:8]}"
    turns = []
    for m in msgs:
        turns.append(await chat_v2(sid, m))
    return turns


def _final(t, i=0):
    return t[i].get("final_response", "") or ""


def _needs(t, i=0):
    return bool(t[i].get("needs_human", False))


# ================= 子集用例断言（v2 语义） =================

def a_p1(t):
    assert "ORD001" in _final(t, 0), _final(t, 0)[:300]


def a_p5(t):
    f = _final(t, 0)
    assert "请选择要查询的订单编号" in f or "ORD001" in f, f[:300]


def a_x3(t):
    assert _needs(t, 0) is False, "越权售后不再转人（不支持答复口径）"
    f = _final(t, 0)
    assert "本人" in f or "归属" in f or "无法办理" in f, f[:300]


def a_x6(t):
    f = _final(t, 0)
    assert "请选择要查询的订单编号" in f or "ORD001" in f or "订单" in f, f[:300]


def a_be3(t):
    f = _final(t, 0)
    # 新口径：第16天超窗口 → 不支持答复（需模型判断），不自动转人
    assert _needs(t, 0) is False, "超期不支持应走不支持答复，不是自动转人"
    assert "不支持" in f or "超过" in f or "16" in f, f[:300]


def a_be7(t):
    f = _final(t, 0)
    # 新口径：定制商品 → 不支持答复，不自动转人
    assert _needs(t, 0) is False, "定制不支持应走答复，不是自动转人"
    assert "定制" in f and "不支持" in f, f[:300]


def a_o3(t):
    # ORD002 签收第10天 → unsupported 终态（非 previewing 离题计数环节）；
    # 第 4 轮接受自动取消文案或实质作答（订单摘要），不空转即通过
    f = _final(t, 3)
    if "自动取消" in f or "取消" in f:
        assert _needs(t, 3) is False, "离题自动取消不应转人工"
        return
    assert _needs(t, 3) is False, "unsupported 后作答不应转人工"
    assert "ORD002" in f and len(f) > 20, f[:300]


def a_o8(t):
    assert ("等待您的确认" in _final(t, 1)) or ("确认" in _final(t, 1)), _final(t, 1)[-200:]
    f2 = _final(t, 2)
    assert "已创建" in f2 or "已为您" in f2, f2[:300]


def a_q7(t):
    assert "退货退款明细预览" in _final(t, 0) or "退货退款" in _final(t, 0), _final(t, 0)[:300]
    f1 = _final(t, 1)
    assert "ORD001" in f1, f1[:300]
    assert "等待您的确认" in f1 or "确认" in f1 or "物流" in f1, f1[-300:]


def a_o6(t):
    # v2 语义：预览环节问政策 → 政策正常作答 + 确认提醒（F6/O5 看词劫持修复）
    f1 = _final(t, 1)
    assert "确认" in f1 or "等待" in f1, f1[-200:]


def a_x2(t):
    assert _needs(t, 0) is True
    f = _final(t, 0)
    assert "转" in f, f[:200]


SUBSET = [
    ("P1", "物流查询-带单号", ["ORD001物流到哪了"], a_p1),
    ("P5", "多意图-物流+政策-无单号列表", ["快递到哪了，保修政策是什么"], a_p5),
    ("X2", "异常-订单不存在-转人工", ["ORD999物流到哪了"], a_x2),
    ("X3", "异常-越权售后-不支持答复", ["我要退货退款ORD006"], a_x3),
    ("X6", "异常-退款缺单号-列表引导", ["我要退货退款"], a_x6),
    ("BE3", "边界-第16天硬阻断", ["我要退货退款ORD011"], a_be3),
    ("BE7", "边界-定制商品硬阻断", ["我要退货退款ORD007"], a_be7),
    ("Q7", "异常-预览环节问物流不丢草稿", ["我要退货退款ORD001", "物流到哪了"], a_q7),
    ("O3", "答非所问-确认环节离题3次自动取消", ["我要退货退款ORD002", "哈哈", "随便看看", "这个多少钱"], a_o3),
    ("O8", "边界-离题后确认正常建单", ["我要退货退款ORD001", "退换货政策是什么", "确认"], a_o8),
    ("O6", "答非所问-preview问政策放行(v2修复)", ["我要退货退款ORD001", "退货政策是什么"], a_o6),
]

# ================= 全量 40（v2 语义断言，路由断言转文本断言） =================

def b_p1(t):
    assert "ORD001" in _final(t, 0)


def b_p2(t):
    assert "ORD001" in _final(t, 1), _final(t, 1)[:300]


def b_p3(t):
    assert "保修" in _final(t, 0)


def b_p4(t):
    f = _final(t, 0)
    assert "ORD001" in f
    assert "签收" in f or "7天" in f or "政策" in f, f[:300]


def b_p6(t):
    f = _final(t, 0)
    assert "ORD002" in f
    assert "明细" in f or "预览" in f, f[:300]
    assert "运费" in f or "承担" in f or "政策" in f, f[:400]


def b_p7(t):
    f = _final(t, 0)
    assert "ORD001" in f or "订单" in f


def b_p8(t):
    f = _final(t, 0)
    assert "ORD001" in f
    assert "到账" in f or "工作日" in f or "物流" in f, f[:400]


def b_q1(t):
    assert "ORD001" in _final(t, 0)
    assert "ORD001" in _final(t, 1) or "订单" in _final(t, 1), _final(t, 1)[:300]


def b_q2(t):
    f = _final(t, 0)
    assert "ORD001" in f
    assert "理赔" in f or "预览" in f or "政策" in f


def b_q3(t):
    f0 = _final(t, 0)
    assert "明细" in f0 or "退款" in f0 or "预览" in f0, f0[:300]
    f1 = _final(t, 1)
    assert "ORD001" in f1


def b_q4(t):
    f = _final(t, 0)
    assert "换货" in f


def b_q5(t):
    f1 = _final(t, 1)
    assert "ORD001" in f1, f1[:300]


def b_q6(t):
    # v2 语义：done 后问「状态」不再被看词劫持，订单查询正常作答
    f2 = _final(t, 2)
    assert "ORD001" in f2, f2[:200]


def b_q7(t):
    f1 = _final(t, 1)
    assert "ORD001" in f1


def b_q8(t):
    f1 = _final(t, 1)
    assert "ORD002" in f1, f1[:300]


def b_x1(t):
    # v2 语义：非职责 → 身份+职责说明+转人工
    f = _final(t, 0)
    assert "职责" in f or "转接" in f or "人工" in f, f[:200]


def b_x8_v2(t):
    # 大小写兼容：ord8404 不存在 → 转人工（与 X2 同路径）
    assert _needs(t, 0) is True, _final(t, 0)[:200]


def b_x4(t):
    f = _final(t, 0)
    assert "ORD001" in f or "订单" in f or "转" in f, f[:200]


def b_x5(t):
    # v2 语义：「售后服务」应能识别为售后并推进（关键词表缺陷修复）
    f = _final(t, 0)
    assert ("明细" in f or "预览" in f or "售后" in f), f[:300]


def b_x7(t):
    assert "取消" in _final(t, 1), _final(t, 1)[:200]
    f2 = _final(t, 2)
    assert "ORD002" in f2 or "明细" in f2 or "预览" in f2, f2[:300]


def b_be1(t):
    f = _final(t, 0)
    assert "换货" in f and ("不支持" in f or "超过" in f or "7天" in f), f[:250]


def b_be2(t):
    assert _needs(t, 0) is False
    f = _final(t, 0)
    assert "明细" in f or "预览" in f, f[:300]


def b_be4(t):
    assert _needs(t, 0) is False
    f = _final(t, 0)
    assert "明细" in f or "预览" in f, f[:300]


def b_be5(t):
    assert _needs(t, 0) is False
    f = _final(t, 0)
    assert "仅退款" in f or "无需寄回" in f or "退款" in f, f[:300]


def b_be6(t):
    f = _final(t, 0)
    assert "未签收" in f or "尚未签收" in f or "预计" in f, f[:200]


def b_be8(t):
    f1 = _final(t, 1)
    assert "取消" in f1 or "已取消" in f1, f1[:200]


def b_o1(t):
    # v2 语义：done 看词劫持消失——订单状态正常查询（F6 修复）
    f2 = _final(t, 2)
    assert "ORD001" in f2, f2[:300]


def b_o2(t):
    f2 = _final(t, 2)
    assert "ORD001" in f2 or "取消" in f2, f2[:300]


def b_o3(t):
    assert _needs(t, 3) is False
    assert "自动取消" in _final(t, 3) or "取消" in _final(t, 3)


def b_o4(t):
    f1 = _final(t, 1)
    assert "ORD001" in f1
    assert "确认" in f1 or "等待" in f1, f1[-200:]


def b_o5(t):
    # v2 语义：done 后问政策不再被看词劫持（O5 修复）→ 政策正常作答
    f2 = _final(t, 2)
    assert "政策" in f2 or "签收" in f2 or "7天" in f2, f2[:300]


def b_o6(t):
    f1 = _final(t, 1)
    assert "确认" in f1 or "等待" in f1, f1[-200:]


def b_o7(t):
    f1 = _final(t, 1)
    assert "确认" in f1 or "等待" in f1, f1[-200:]


def b_o8(t):
    assert "已创建" in _final(t, 2) or "已为您" in _final(t, 2), _final(t, 2)[:300]


FULL = [
    ("P1", "物流查询", ["ORD001物流到哪了"], b_p1),
    ("P2", "指代补单+政策+订单", ["这个订单的退换货政策是什么", "ORD001"], b_p2),
    ("P3", "保修政策", ["保修政策是什么"], b_p3),
    ("P4", "订单+政策", ["ORD001订单状态，退换货政策是什么"], b_p4),
    ("P5", "物流+政策-无单号", ["快递到哪了，保修政策是什么"], a_p5),
    ("P6", "三意图-订单+售后+政策", ["我要退货退款ORD002，运费政策是什么"], b_p6),
    ("P7", "售后+政策-缺单号", ["我要换货，换货政策是什么"], b_p7),
    ("P8", "物流+政策-带单号", ["ORD001物流到哪了，退款到账政策是什么"], b_p8),
    ("Q1", "order→aftersales-槽位继承", ["ORD001物流到哪了", "我要退货退款"], b_q1),
    ("Q2", "售后+政策", ["我要退货退款ORD001，保修政策是什么"], b_q2),
    ("Q3", "退款在途-状态查询", ["我要退款ORD001", "退款到账了吗"], b_q3),
    ("Q4", "换货+政策", ["我要换货ORD001，这个订单运费政策是什么"], b_q4),
    ("Q5", "指代补单后串行", ["这个订单运费政策是什么", "ORD001"], b_q5),
    ("Q6", "done看词-v2语义修复", ["我要退货退款ORD001", "好的", "退款到账了吗", "这个订单退换货政策是什么"], b_q6),
    ("Q7", "预览问物流不丢草稿", ["我要退货退款ORD001", "物流到哪了"], a_q7),
    ("Q8", "在途换订单号重置", ["我要退货退款ORD001", "换个ORD002的货试试"], b_q8),
    ("X1", "无意图-非职责兜底", ["今天天气不错"], b_x1),
    ("X2", "订单不存在", ["ORD999物流到哪了"], a_x2),
    ("X3", "越权售后", ["我要退货退款ORD006"], a_x3),
    ("X4", "乱码不匹配意图", ["AGGC试剂发货了吗"], b_x4),
    ("X5", "售后服务词识别", ["我要申请售后服务ORD001"], b_x5),
    ("X6", "退款缺单号列表", ["我要退货退款"], a_x6),
    ("X7", "取消后重发", ["我要退货退款ORD002", "先不退", "我要退货退款"], b_x7),
    ("X8", "大小写兼容", ["ord8404物流到哪了"], b_x8_v2),
    ("BE1", "换货窗口超限", ["我要换货ORD002"], b_be1),
    ("BE2", "退货退款第15天", ["我要退货退款ORD010"], b_be2),
    ("BE3", "第16天硬阻断", ["我要退货退款ORD011"], a_be3),
    ("BE4", "金额阈值2000", ["我要退货退款ORD010"], b_be4),
    ("BE5", "未签收仅退款", ["我要仅退款ORD012"], b_be5),
    ("BE6", "未签收退货退款软阻断", ["我要退货退款ORD004"], b_be6),
    ("BE7", "定制商品", ["我要退货退款ORD007"], a_be7),
    ("BE8", "确认/取消出口", ["我要退货退款ORD001", "先不退"], b_be8),
    ("O1", "done看词-v2语义修复", ["我要退货退款ORD001", "好的", "ORD001订单状态怎么样"], b_o1),
    ("O2", "canceled看词回显", ["我要退货退款ORD001", "先不退", "退款到账了吗"], b_o2),
    ("O3", "离题3次自动取消", ["我要退货退款ORD002", "哈哈", "随便看看", "这个多少钱"], a_o3),
    ("O4", "preview混换货词", ["我要退货退款ORD001", "我要换货ORD001"], b_o4),
    ("O5", "done后政策看词-v2修复", ["我要退货退款ORD001", "好的", "退换货政策是什么"], b_o5),
    ("O6", "preview问政策放行", ["我要退货退款ORD001", "退货政策是什么"], a_o6),
    ("O7", "preview离题闲聊提醒", ["我要退货退款ORD001", "今天吃什么"], b_o7),
    ("O8", "离题后确认建单", ["我要退货退款ORD001", "退换货政策是什么", "确认"], a_o8),
]


def _pick():
    if os.getenv("REACT_V2_FULL") == "1":
        return FULL
    return SUBSET


def _run_all():
    for cid, name, msgs, chk in _pick():
        reset_refund_memory()
        store.reset()
        try:
            turns = asyncio.run(_drive_case(msgs))
        except Exception as e:
            yield cid, name, False, f"流程异常:{type(e).__name__}:{e}"
            continue
        try:
            chk(turns)
            yield cid, name, True, ""
        except AssertionError as e:
            yield cid, name, False, str(e)


def test_react_v2_boundary():
    report = ["========== ReAct v2 边界测试报告 =========="]
    n_pass = 0
    fails = []
    for cid, name, ok, why in _run_all():
        if ok:
            n_pass += 1
            report.append(f"[PASS] {cid} {name}")
        else:
            fails.append(cid)
            report.append(f"[FAIL] {cid} {name} —— {why}")
    report.append("")
    report.append(f"总 {len(_pick())} 用例：PASS {n_pass}，FAIL {len(fails)}")
    report.append(f"FAIL 清单: {fails}")
    log_dir = ROOT / "logs"
    os.makedirs(log_dir, exist_ok=True)
    (log_dir / "react_v2_report.txt").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    assert n_pass == len(_pick()), f"{len(fails)} 用例未通过：{fails}"


if __name__ == "__main__":
    sys.exit(test_react_v2_boundary() or 0)
