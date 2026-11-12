"""v2 样例 LLM-judge 评测：chat_v2 跑样例 → 模型逐条判定通过与否。

流程：
  ① 每条样例调用 app.react_v2.chat_v2（真实模型）跑 input 消息序列；
  ② 把「样例定义（类型/描述/输入/标准答案/通过标准/不通过标准）+
     agent v2 的实际对话记录（每轮客服回复 + needs_human）」交给判定模型；
  ③ 模型仅依据上述规则输出 {passed, reason}，不接触任何参考实现/断言代码；
  ④ 结果合并落盘 logs/v2_eval_results.json，可重复分片运行（env EVAL_IDS）。

运行：LLM_PROVIDER=ark pytest tests/test_v2_eval_llm.py -q
分片：EVAL_IDS=P1,P2 python -m pytest tests/test_v2_eval_llm.py -q
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import uuid
from pathlib import Path

import pytest  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.react_v2 import chat_v2  # noqa: E402
from app.react_v2.llm_tools import complete_with_tools  # noqa: E402
from app.react_v2.memory import store  # noqa: E402
from app.services.refund_service import reset_refund_memory  # noqa: E402


# 样例文件与输出文件可用 env 指定：
#   EVAL_SAMPLES=tests/xxx.json EVAL_OUT=v2_eval_rest  默认 tests/v2_eval_samples.json / v2_eval
SAMPLES = ROOT / os.getenv("EVAL_SAMPLES", "tests/v2_eval_samples.json")
OUT_TAG = os.getenv("EVAL_OUT", "v2_eval")


@pytest.fixture(autouse=True)
def offline_store(monkeypatch):
    from app.tools import mysql_store
    monkeypatch.setattr(mysql_store.DataStore, "_connect", lambda self: False)


def _load_cases() -> list[dict]:
    return json.load(open(SAMPLES, encoding="utf-8"))["cases"]


JUDGE_SYSTEM = (
    "你是资深客服评测裁判。给你一条测试样例的定义和一个客服AI（agent v2）的实际对话记录。"
    "判定尺度：以「口径是否实质正确」为准，不要求与标准答案逐句一致。"
    "判定条件（全部满足才判通过）："
    "a) 未出现与标准答案结论相悖的答复（答案说7天可退而答复说30天可退/说不可退，即为相悖）；"
    "b) 未归到错误类目、未答非所问；c) 对用户问题有实质解答（非空泛、非仅转人工）。"
    "容差：答案原文的细节不必逐条覆盖；答案之外的同向合理细节（等价表述、办理引导如索要订单号）不判不通过。"
    "FAIL 触发：答非所问、以转人工代替作答（样例答案未要求转人时）、"
    "结论与标准答案冲突、归错类目、空泛兜底、应追问/回显时按答案要求未执行。"
    "只输出严格JSON，格式：{\"passed\": true或false, \"reason\": \"一句话判定依据\"}。"
)


async def _drive_case(sid: str, case: dict) -> list[dict]:
    turns = []
    for i, msg in enumerate(case["input"], 1):
        r = await chat_v2(sid, msg)
        turns.append({
            "round": i,
            "user": msg,
            "assistant": r.get("final_response", ""),
            "needs_human": bool(r.get("needs_human", False)),
        })
    return turns


def _try_obj(text: str) -> dict | None:
    for m in (re.findall(r"```(?:json)?\s*([\s\S]*?)```", text), [text]):
        chunks = m if isinstance(m, list) else [m]
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                obj = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and "passed" in obj:
                return obj
    return None


def _parse_judge(text: str) -> dict:
    """从模型回复里抽取 judge JSON（容忍前后缀/代码块/夹带文本）。"""
    text = (text or "").strip()
    obj = _try_obj(text)
    if obj is None:
        m = re.search(r"{[\s\S]*\}", text)
        if m:
            obj = _try_obj(m.group(0))
    if obj is not None:
        return {
            "passed": bool(obj["passed"]),
            "reason": str(obj.get("reason", ""))[:300],
        }
    return {"passed": None, "reason": "judge 输出无法解析"}


def _judge_turns(case: dict, turns: list[dict]) -> dict:
    payload = {
        "样例类型": case.get("type", ""),
        "任务描述": case.get("description", ""),
        "输入消息序列": case.get("input", []),
        "前置条件": case.get("precondition", ""),
        "标准答案（正确行为）": case.get("expected", ""),
        "通过标准": case.get("pass_criteria", []),
        "不通过标准": case.get("fail_criteria", []),
        "agent实际对话记录（每轮客服回复+needs_human标志）": [
            {
                f"第{t['round']}轮 用户": t["user"],
                "客服": t["assistant"],
                "needs_human": t["needs_human"],
            } for t in turns
        ],
    }
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    resp = complete_with_tools(messages, None)
    if resp.get("error"):
        return {"passed": None, "reason": f"judge调用失败:{resp['error']}"}
    return _parse_judge(resp.get("content", ""))


async def _eval_case(case: dict) -> dict:
    sid = f"v2eval-{case['id']}-{uuid.uuid4().hex[:6]}"
    reset_refund_memory()
    store.reset()
    turns = await _drive_case(sid, case)
    judge = _judge_turns(case, turns)
    return {
        "id": case["id"],
        "type": case.get("type", ""),
        "turns": turns,
        "judge": judge,
    }


def _results_path() -> Path:
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    return logs / f"{OUT_TAG}_results.json"


def _ordered_ids() -> list[str]:
    return [c["id"] for c in _load_cases()]


def _merge(results: list[dict]) -> dict:
    path = _results_path()
    old: dict = {}
    if path.exists():
        try:
            old = {r["id"]: r for r in json.load(open(path, encoding="utf-8"))}
        except Exception:
            old = {}
    for r in results:
        old[r["id"]] = r
    order = {cid: i for i, cid in enumerate(_ordered_ids())}
    return dict(sorted(old.items(), key=lambda kv: order.get(kv[0], 999)))


def _report(merged: dict) -> str:
    lines = ["========== v2 样例 LLM-judge 评测报告 =========="]
    ids = _ordered_ids()
    n_pass = n_fail = n_unknown = n_missed = 0
    for cid in ids:
        r = merged.get(cid)
        if r is None:
            n_missed += 1
            lines.append(f"[NOT-RUN] {cid}（未运行）")
            continue
        ok = r["judge"].get("passed")
        if ok is True:
            n_pass += 1
            lines.append(f"[PASS] {cid}（{r.get('type','')}）")
        elif ok is False:
            n_fail += 1
            lines.append(f"[FAIL] {cid}（{r.get('type','')}）—— {r['judge'].get('reason','')}")
        else:
            n_unknown += 1
            lines.append(f"[UNKNOWN] {cid}（{r.get('type','')}）—— {r['judge'].get('reason','')}")
    lines.append("")
    lines.append(f"总计 {len(ids)} 条：PASS {n_pass}，FAIL {n_fail}，"
                 f"UNKNOWN {n_unknown}，未跑 {n_missed}")
    return "\n".join(lines)


def test_v2_eval_llm():
    cases = _load_cases()
    ids_env = os.getenv("EVAL_IDS")
    if ids_env:
        wanted = {x.strip() for x in ids_env.split(",") if x.strip()}
        cases = [c for c in cases if c["id"] in wanted]
    results = [asyncio.run(_eval_case(c)) for c in cases]
    merged = _merge(results)
    json.dump(list(merged.values()), open(_results_path(), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    report = _report(merged)
    (ROOT / "logs" / f"{OUT_TAG}_report.txt").write_text(report, encoding="utf-8")
    print(report)
    # 评测结果不做硬 assert：judge 判定是评测结论，测试本身成功=流程跑通
