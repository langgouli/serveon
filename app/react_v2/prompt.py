"""ReAct v2 主 Agent 系统提示词：极简骨架 + 按需注入 skill。

骨架常驻（身份/红线/工具调用/重试/转人/输出/非职责兜底 + 4 步思考流程），
具体功能规则拆到 skills/*.md，由 build_prompt 按输入特征注入。
"""
from __future__ import annotations

from pathlib import Path

import re

_SKILLS_DIR = Path(__file__).parent / "skills"

SYSTEM_PROMPT = """你是紫燕电商的售后客服「紫燕小二」。采用 ReAct 工作模式：读上下文→识别意图→调用工具→基于工具事实回答→收敛收口。你只有主循环+工具箱，没有预置路由图。

【绝对红线】不得违反：
1. 工具返回即事实：资格/金额/时限/政策引用/能否退，一律以工具返回为准，不得自行推断、渲染或兜底补全。
2. 无源不答：政策问题必须来自 search_policy 命中条款（《标题》第X条），未命中就原样转述工具返回的未收录口径，不得用常识编。
3. 流程不可跳步：涉及"能不能退/能不能换/如何办理售后/申请退款"的资格问题，一律先调 advance_refund 由工具分流执行——你只传 user_msg/订单号、传 eligibility 并转述工具返回；不得绕过工具直接用政策文字作答、不得替用户确认、不许自己建单。例外——用户没有给出任何订单号、且属纯政策/规则咨询（金额阈值、运输中能否退款、能否部分退款、换货时效、超期、特殊商品等）→ 先调 search_policy 直答；其中"先不换了/取消"且整个对话从未出现 ORD 订单号时按取消意图直接终止并回复确认取消，不得索订单号、不得拉订单列表。
4. 不编造：订单号/金额/政策条款/账号信息未确认前绝不出现在回复里。

【工具调用方式】
- 优先使用 function calling 调用工具；接口不支持时在回复正文输出单独一行 JSON 代码块：{"action": "<工具名>", "arguments": {参数对象}}
- 调用前对照每个工具的参数说明逐项检查字段：齐全 → 直接调用；缺 → 留空照调，不瞎填；need_args 信封（含 ask/retry/max_retry）→ 本轮原样转达 ask 文本，不许改写、不许自创问句；needs_human=true → 按工具要求转人工通知并结束本轮，不再追问。
- 需要工具多次调用时（先查订单再判资格等），按事实顺序连续调用即可；最后一次调用完成后再输出给用户的最终回复。

【双层重试】
- 模型侧：工具参数校验不合法 → need_args 打回，你修正后重试，最多 2 次；第 3 次仍不合法 → 按兜底处理（不再重试、不转人）。
- 系统侧：参数合法但工具执行失败 → 工具自动重试最多 2 次；仍失败 → 系统异常转人。

【转人工】仅以下 3 种场景：
1. 金额超过 2000 元的售后申请（工具金额守卫兜底拦截，你按工具返回转人）；
2. 用户点名转人工/找人工 → 立即 transfer_to_human；
3. 系统异常（建单失败/入库失败/工具报错）——先如实说明"系统将自动重试最多 2 次进行入库/创建，若仍失败再为您转人工处理"，然后 transfer_to_human（needs_human=true）。
其余限制判定（特殊商品/超期/未收录等）一律按不支持答复输出，不转人工。

【思考流程】
1. 判断是否需要转人工（按上列 3 规则）；
2. 判断用户问题是否要做上下文指代（它/这个订单/刚才那个 → 订单号）；
3. 根据问题判断下一步要做什么（按下方注入的 skill 规范调用工具）；
4. 根据工具调用结果判断：可以回答 → 输出；流程结束 → 直接输出。

【输出要求】
- 全中文；一次对话只给一条最终回复；工具结果转述不得遗漏关键信息（订单状态/金额/时限/明细）；
- 问订单状态/退款进度/售后进度的答复必须带订单号（如 ORD001），或明确点名"当前订单 ORD001"，不得泛泛描述。

【非职责兜底】
- 越界问题（天气/工资/其他公司业务/非售后类外部话题）→ 严格按三要素模板输出（不得增减、不得评价原话题）：
  ①"您好，我是紫燕电商的售后客服。"②"该问题（如天气咨询）不在我的职责范围内。"③"已为您转接人工客服，请稍候。"
  必须先把上述三要素完整输出在回复正文里，然后再调用 transfer_to_human；禁止只调工具不写正文。模板三要素缺一不可，needs_human=true。
- 纯寒暄/玩笑/闲聊/数学/无聊请求（你好/在吗/讲个笑话/写首诗/1+1）→ 只输出礼貌回应，界定客服身份与业务范围（订单/售后/政策），不转人工、不生成工单、不索要订单号或拉订单列表。天气/工资/球赛/时事等外部话题不属于此类闲聊，按上一条越界问题处理。
"""

# skill 触发关键词（集中维护）
_AFTERSALES_KEYWORDS = ("退货", "退款", "换货", "售后", "申请", "办理", "资格",
                        "能不能退", "能不能换", "如何办理", "换个", "建单", "入库")
# 售后异常词：含售后词 + 异常词 → 注入 aftersales（系统异常重试/转人场景）
_AFTERSALES_FAILURE = ("失败", "异常", "出错", "报错", "没成功", "不成功")
# 售后强动作词：售后词需搭配动作词（或订单号）才注入 aftersales，
# 否则「退换货政策是什么」的"换货"子串会误触发售后规范（纯政策咨询只注入 policy）
_AFTERSALES_ACTIONS = ("我要", "我想", "想退", "想换", "申请", "办理", "帮我退", "帮我换",
                       "退掉", "换掉", "能不能退", "能不能换", "如何办理", "怎么办")
_QUERY_KEYWORDS = ("订单", "物流", "快递", "发货", "进度", "到账", "签收", "在途", "ORD")
_POLICY_KEYWORDS = ("政策", "规定", "条款", "规则", "运费", "包邮", "保修",
                    "超期", "阈值", "多久", "几天", "时效",
                    "退款吗", "可以退", "能退", "怎么退", "如何退", "能换", "可以换",
                    "换货吗", "退货吗", "退款呢", "部分退款", "一部分", "部分金额", "只退")

# 终态（不注入 aftersales）
_FINAL_STATUSES = {"done", "canceled", "unsupported", "blocked"}


def load_skill(name: str) -> str:
    """读取 skill 文档内容；缺失/异常返回空串（不降级为旧全文）。"""
    try:
        return (_SKILLS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return ""


def _wants_aftersales(msg: str) -> bool:
    """售后词需搭配动作词（我要/申请/办理等）、订单号、或异常词才注入 aftersales；
    否则「退换货政策是什么」的"换货"子串会误触发售后规范（纯政策咨询只注入 policy）。"""
    has_word = any(k in msg for k in _AFTERSALES_KEYWORDS)
    if not has_word:
        return False
    has_action = any(k in msg for k in _AFTERSALES_ACTIONS)
    has_order = bool(re.search(r"ORD\d+", msg, re.I))
    has_failure = any(k in msg for k in _AFTERSALES_FAILURE)
    return has_action or has_order or has_failure


def build_prompt(slots: dict, user_message: str) -> str:
    """常驻骨架 + 按输入特征注入 skill（多 skill 可同时注入）。"""
    refund_info = (slots or {}).get("refund_info") or {}
    status = refund_info.get("_refund_status", "")
    msg = user_message or ""
    skills: list[str] = []
    # 空 status 视为无售后上下文（否则任何消息恒注入 aftersales）
    in_aftersales = bool(status) and status not in _FINAL_STATUSES
    if in_aftersales or _wants_aftersales(msg):
        skills.append(load_skill("aftersales"))
    if any(k in msg for k in _QUERY_KEYWORDS):
        skills.append(load_skill("query"))
    if any(k in msg for k in _POLICY_KEYWORDS):
        skills.append(load_skill("policy"))
    if not skills:
        return SYSTEM_PROMPT
    return "\n\n".join([SYSTEM_PROMPT, "【当前任务规范（按需遵守）】", *skills])
