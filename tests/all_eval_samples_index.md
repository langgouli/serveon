# 评测样例总索引（2026-11-08 盘点）

口径：仅收**对话评测样例**（多轮/多意图/带预期话术或转人工动作）；部件级单元测试（extract/entity/intent 等）不收。
判定方式分两类：**代码断言**（Python 断言）/ **模型 judge**（LLM 判定实际输出）。

## 一、总览（248 条，9 个来源）

| # | 来源 | 条数 | 形态 | 驱动目标 | 判定方式 |
|---|------|------|------|---------|---------|
| 1 | [testdata/政策查询.json](../testdata/政策查询.json) | 40 | JSON 资产（id/category/type/question/answer） | 政策问答（v1 分类+LLM） | **模型 judge**（判 category） |
| 2 | [testdata/退款功能.json](../testdata/退款功能.json) | 45 | JSON 资产（同上字段） | 售后全流程/换货/进度（refund 子图+chat） | **模型 judge**（实际输出体现口径） |
| 3 | [tests/test_multi_intent_full.py](test_multi_intent_full.py) | 47 | Python CASES（A1–K1 多意图组合） | v1 主图 chat | 代码断言 |
| 4 | [tests/test_multi_intent_boundary.py](test_multi_intent_boundary.py) | 40 | Python CASES（P/Q/X/BE/O 边界） | v1 主图 chat | 代码断言 |
| 5 | [tests/test_react_v2_boundary.py](test_react_v2_boundary.py) | 40 | Python CASES（同 40 输入，v2 语义） | **v2 chat_v2** | 代码断言（v2 语义改写） |
| 6 | [tests/test_cases_design.py](test_cases_design.py) | 33 | pytest 用例（simple/multi/multiturn） | v1 主图 chat | 代码断言 |
| 7 | [tests/test_e2e_chat.py](test_e2e_chat.py) | 6 | pytest 功能（F1–F5+工单） | v1 主图 chat | 代码断言 |
| 8 | [tests/test_multi_turn.py](test_multi_turn.py) | 4 | pytest 多轮 | v1 主图 chat | 代码断言 |
| 9 | [tests/test_multi_intent.py](test_multi_intent.py) | 3 | pytest 多意图 | v1 主图 chat | 代码断言 |

> test_smoke.py 为包结构冒烟，无对话样例，不入册。

## 二、来源明细

### 1-2. testdata 两份 JSON（已有字段：id/category/type/question/answer）
- **政策查询 40 条**：9 类（退货/保修/运费/到账/换货/特殊商品/未知/…），type 含 normal/异常/边界；judge 打"回答属于指定政策类别"（不逐字对齐）。
- **退款功能 45 条**：40 base + 换货专项 10（id21–30：正常/7天/10天窗口/16天/定制/离题/否认/类型模糊/超阈值/进度回显）+ 售后进度专项 15；judge 判"实际输出是否体现样例口径"。
- 两者均由 tests/test_policy_llm.py / test_refund_llm.py 驱动 —— **项目内已有"样例JSON+模型judge"现行名词**。

### 3. test_multi_intent_full.py 47 例
多意图/组合/缺陷探针：A1–A10（两意图）、B1–B3（三/四意图）、C1–C7（订单边界矩阵）、D1–D7（确认环节离题/看词）、E1–E5（done/canceled 后看词探针）、F1–F3（情绪科目）、G1–G3（转人工覆盖）、H1–H4（闲聊不卡状态）、I1–I3（售后单号/回显）、K1（类型抽取优先级探针）。
→ 与 boundary 40 互补（full 是多意图组合切片；boundary 是单一维度边界切片）。

### 4. test_multi_intent_boundary.py 40 例（P/Q/X/BE/O）
P1–P8 基线场景、Q1–Q8 流程串行/槽位、X1–X8 异常（非职责/不存在/越权/乱码/服务词/缺单号/取消后重发/大小写）、BE1–BE8 边界（窗口/天数/金额/签收/定制/确认出口）、O1–O8 答非所问（done/canceled 看词劫持、离题计数、mixed 换货词、preview 放行/提醒）。

### 5. test_react_v2_boundary.py 40 例
**input 与第 4 组完全同源**（40 条消息序列一致），断言按 v2 语义重写（看词劫持类期望"被修复"：如 O5/Q6/O1 政策/订单正常作答；X8 大小写走不存在→转人工）。SUBSET 11 为全量子集。

### 6-9. test_cases_design.py 33 + e2e/multi_turn/multi_intent 13
cases_design：simple×10（policy×5/order/logistics/aftersales×3）+ negative×1、multi×7、multiturn×12（全额退款/订单→售后/政策续问/退款确认/政策后转人工/换货确认/阻断/软阻断/指代消解）；e2e：安抚+订单/政策/退款/转人工/工单核验；multi_turn≥4；multi_intent 3。
→ 与第 3/4 组存在场景重复（不同粒度、不同断言），整理时保留各来源、标注重复场景。

## 三、覆盖/缺口关系（供 v2 评测选材）

- **v2 已验证**：第 5 组 40 例（chat_v2 全量 40/40）。
- **v2 未验证**：政策查询 40 + 退款功能 45 尚未对 chat_v2 跑过（v2 有 search_policy/advance_refund 工具，但问答口径未系统验证）；full 47 / cases_design 33 / e2e 13 亦未跑 v2。
- 判定方式统一建议：JSON 资产的 question/answer → 模型 judge；对话序列 → 代码断言 + 可选 judge 双倍。

## 四、下一步字段化方案（与用户约定）

统一 JSON 每条：
```json
{
  "id": "P1", "type": "物流查询", "description": "...",
  "input": ["ORD001物流到哪了"], "precondition": "会话隔离; refund重置; 离线mock",
  "expected": "正确行为描述",
  "pass_criteria": ["可核对的通过标准条目"],
  "fail_criteria": ["可核对的不通过标准条目"]
}
```
- 第 5 组 40 例直接字段化（expected/pass/fail 据 v2 断言意图撰写）。
- 第 1/2 组已有字段，只需 `expected` 由 answer 展开 + pass/fail 补判据。
- 第 3/4/6/7/8/9 组需人工整理（单测断言语义→自然语言标准）。
