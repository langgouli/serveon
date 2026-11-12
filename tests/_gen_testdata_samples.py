"""把 testdata 两份 JSON（政策40/退款45）样式化为统一评测样例。
expected 直接采用 answer；pass/fail 按 type（normal/异常/边界/转述）分档。
输出 tests/v2_eval_samples_testdata.json
"""
import json

cases = []


def add(case_id, category, qtype, question, answer):
    et = answer if isinstance(answer, str) else str(answer)
    if qtype == "异常":
        pass_c = [f"按标准答案规定的处理方式对「{question}」作出实质处置（口径与标准答案一致）"]
    else:
        pass_c = [f"对「{question}」实质作答，口径与标准答案一致"]
    desc = f"{category}｜{qtype}｜{question}"
    cases.append({
        "id": case_id,
        "type": f"{category}({qtype})",
        "description": desc,
        "input": [question],
        "precondition": ("会话隔离（独立session）；refund内存重置；离线mock数据；"
                         "真实模型LLM_PROVIDER=ark"),
        "expected": f"标准答案：{et}",
        "pass_criteria": pass_c + ["needs_human 与标准答案的处理要求一致"],
        "fail_criteria": [
            "答非所问或直接告知无法回答",
            "口径与标准答案相反或归到错误类目",
            "空泛兜底无实质内容",
            "应转人工的样例未转人工，或不应转人工的样例无故转人工",
        ],
    })


for x in json.load(open("testdata/政策查询.json", encoding="utf-8")):
    add(f"TP{x['id']}", x["category"], x["type"], x["question"], x["answer"])

for x in json.load(open("testdata/退款功能.json", encoding="utf-8")):
    add(f"TR{x['id']}", x["category"], x["type"], x["question"], x["answer"])

out = {
    "meta": {
        "kind": "对话评测样例（testdata 双源）",
        "source": "testdata/政策查询.json(40) + testdata/退款功能.json(45)",
        "total": len(cases),
        "field_schema": ["id", "type", "description", "input", "precondition",
                         "expected", "pass_criteria", "fail_criteria"],
        "judge": "llm_judge",
        "driver": "app.react_v2.chat_v2",
        "generated": "2026-11-08",
    },
    "cases": cases,
}
with open("tests/v2_eval_samples_testdata.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(len(cases))
ids = [c["id"] for c in cases]
print("dups:", [i for i in ids if ids.count(i) > 1])
print("missing:", {k for c in cases for k in ["id","type","description","input","precondition","expected","pass_criteria","fail_criteria"] if k not in c})
