"""LLM 客户端抽象。开发期使用 MockLLMClient 返回确定性结构化结果，
后续替换真实 API 时仅需实现 LLMClient 协议并替换工厂返回值。"""
from __future__ import annotations

import json
import re
from typing import Any, Protocol

import requests

from app.config import config
from app.services.extract import extract_amount, extract_order_number, extract_refund_type
from app.utils.logger import log_event

_AFTERSALES_TYPES = {"REFUND_ONLY", "RETURN_REFUND", "EXCHANGE"}


class LLMClient(Protocol):
    """LLM 调用接口。task 标识任务类型，prompt 为输入，kwargs 传额外数据。"""

    def complete(self, task: str, prompt: str, **kwargs: Any) -> dict: ...


_EMOTION_KEYWORDS_ANGRY = ["气死", "太过分", "投诉", "差评", "再也不买", "怎么回事", "等了这么久", "生气", "愤怒", "恶心"]
_EMOTION_KEYWORDS_UPSET = ["糟糕", "不满", "失望", "慢", "烦", "差劲", "无语", "烦躁", "急躁", "没耐心", "急", "烦死", "久了", "久等", "不耐烦"]

_MOCK_SOOTHE = "非常理解您的心情，给您带来不便我们深表歉意。我来帮您核实处理，请您提供订单号，我马上查。"

_POLICY_CATEGORY_KEYWORDS = {
    "退换货政策": ["退货", "退款", "退换", "7天", "15天", "签收", "七天"],
    "运费政策": ["运费", "邮费", "承担"],
    "退款到账政策": ["到账", "退款时间", "退款到账", "原路"],
    "保修政策": ["保修", "维修", "保期"],
    "换货政策": ["换货", "更换"],
    "特殊商品政策": ["定制", "虚拟", "特殊"],
}

_INTENT_KEYWORDS = {
    "aftersales": ["退货退款", "申请换货", "仅退款", "我要退货", "我要退款", "申请退款", "我要换货", "申请过"],
    "order": ["ORD", "订单"],
    "logistics": ["物流", "快递", "到哪", "送达", "运单"],
    "policy": ["政策", "运费", "保修", "到账时间", "退换货规则", "退换货政策"],
    "aftersales_status": ["售后进度", "售后单", "申请过了", "退款进度", "退款状态"],
}

# 售后单确认环节意图分类的 mock 关键词（与 aftersales.py 词表同口径）
_CONFIRM_CLASSIFY_KWS = {
    "confirm": ["确认", "好的", "可以", "同意", "行", "没问题", "ok", "办吧"],
    "cancel": ["先不退", "先不换", "不退了", "不换了", "不要了", "不想要了", "取消", "算了", "不用了", "别处理"],
}

_ORDER_REFERENCES = ["我的订单", "这个订单", "该订单", "这单", "之前那个", "刚才那个"]


class MockLLMClient:
    """确定性 mock：基于关键词返回结构化结果，便于离线测试。"""

    def complete(self, task: str, prompt: str, **kwargs: Any) -> dict:
        result = self._dispatch(task, prompt, kwargs)
        log_event("-", f"llm_result {task} (mock)", input="", output=str(result))
        return result
    def _dispatch(self, task: str, prompt: str, kwargs: dict) -> dict:
        if task == "emotion_assist":
            return self._emotion_assist(prompt)
        if task == "intent":
            return self._intent(prompt)
        if task == "policy_answer":
            return self._policy_answer(prompt, kwargs.get("clauses", []))
        if task == "policy_classify":
            return self._policy_classify(prompt)
        if task == "refund_explain":
            return self._refund_explain(kwargs)
        if task == "aftersales_extract":
            return self._aftersales_extract(prompt)
        if task == "confirm_classify":
            return self._confirm_classify(prompt)
        return {"error": f"unknown task: {task}"}

    # ---- emotion_assist ----
    def _emotion_assist(self, prompt: str) -> dict:
        if any(k in prompt for k in _EMOTION_KEYWORDS_ANGRY):
            return {"emotion": "angry", "intensity": 0.9,
                    "soothe": _MOCK_SOOTHE}
        if any(k in prompt for k in _EMOTION_KEYWORDS_UPSET):
            return {"emotion": "upset", "intensity": 0.75,
                    "soothe": _MOCK_SOOTHE}
        return {"emotion": "calm", "intensity": 0.2, "soothe": ""}

    # ---- intent ----
    def _intent(self, prompt: str) -> dict:
        # 只扫描当前消息部分，避免历史上下文误触发
        current = prompt.split("【当前消息】")[-1] if "【当前消息】" in prompt else prompt
        intents: list[str] = []
        for intent, kws in _INTENT_KEYWORDS.items():
            if any(k in current for k in kws):
                intents.append(intent)
        if not intents:
            return {"intents": [], "confidence": 0.3,
                    "execution": {"mode": "parallel", "order": [], "dependencies": {}}}
        seen: set[str] = set()
        deduped = [i for i in intents if not (i in seen or seen.add(i))]
        return {"intents": deduped, "confidence": 0.9,
                "execution": self._execution_plan(deduped, current)}

    def _execution_plan(self, intents: list, msg: str) -> dict:
        """规则判定执行关系（模拟 LLM 输出）。"""
        has_order = "order" in intents or "logistics" in intents
        msg_refs_order = any(k in msg for k in _ORDER_REFERENCES)
        deps: dict = {}
        if has_order:
            if "aftersales" in intents:
                deps["aftersales"] = "order"
            if "policy" in intents and msg_refs_order:
                deps["policy"] = "order"
        if deps:
            order = [i for i in intents if i in ("order", "logistics")] + \
                    [i for i in intents if i in deps]
            return {"mode": "serial", "order": order, "dependencies": deps}
        return {"mode": "parallel", "order": [], "dependencies": {}}

    # ---- policy_answer ----
    def _policy_answer(self, prompt: str, clauses: list[dict]) -> dict:
        if not clauses:
            return {"answer": "", "has_source": False}
        lines = ["根据您的问题，相关政策如下："]
        for i, c in enumerate(clauses, 1):
            lines.append(f"{i}. {c['content']}（依据《{c['title']}》第{c['clause_id']}条）")
        return {"answer": "\n".join(lines), "has_source": True}

    # ---- policy_classify ----
    def _policy_classify(self, prompt: str) -> dict:
        cats = [
            c for c, kws in _POLICY_CATEGORY_KEYWORDS.items()
            if any(k in prompt for k in kws)
        ]
        return {"categories": cats, "confidence": 0.9 if cats else 0.2}

    # ---- refund_explain ----
    def _refund_explain(self, detail: dict) -> dict:
        order = detail.get("order_number", "")
        amount = detail.get("amount", 0)
        rtype = detail.get("request_type", "")
        stage = detail.get("stage", "processing")
        lead = {
            "waiting_return": "已为您创建退货退款申请",
            "exchange_reply": "已为您创建换货申请",
        }.get(stage, "已为您创建退款申请")
        stage_text = {
            "waiting_return": "，请先寄回商品，退款记录状态为待退货，商家签收后退款完成并更新状态为已完成，预计1-3个工作日到账",
            "exchange_reply": "，请寄回原商品，换货记录状态为待寄回，商家收到后发出新货，换货完成后更新状态为已完成",
        }.get(stage, "，退款处理中，预计1-3个工作日到账")
        tier = detail.get("tier_note", "")
        extra = f"，{tier}" if tier else ""
        return {
            "text": (
                f"{lead}：订单{order}，"
                f"退款类型{rtype}，退款金额¥{amount:.2f}{stage_text}{extra}。"
            )
        }


    # ---- aftersales_extract ----
    def _aftersales_extract(self, prompt: str) -> dict:
        msg = prompt.split("【当前消息】")[-1] if "【当前消息】" in prompt else prompt
        return {
            "order_number": extract_order_number(msg) or "",
            "request_type": extract_refund_type(msg) or "NONE",
            "amount": extract_amount(msg),
        }

    # ---- confirm_classify ----
    def _confirm_classify(self, prompt: str) -> dict:
        """确认环节三分类：confirm=确认建单，cancel=取消，other=与确认无关。
        只扫当前消息，避免上下文干扰。"""
        current = prompt.split("【当前消息】")[-1] if "【当前消息】" in prompt else prompt
        if any(k in current for k in _CONFIRM_CLASSIFY_KWS["cancel"]):
            return {"action": "cancel"}
        if any(k in current for k in _CONFIRM_CLASSIFY_KWS["confirm"]):
            return {"action": "confirm"}
        return {"action": "other"}


class XfSparkClient:
    """讯飞星火 Spark-X2.6 客户端（OpenAI 兼容格式）。

    环境变量：
      SPARK_API_KEY     API 密钥（ak-xxx）
      SPARK_BASE_URL    API endpoint
      SPARK_MODEL       模型名（默认 spark-x2.6，小写；大写会 10404）
    """

    _INTENT_LABELS = "policy / order / logistics / aftersales / aftersales_status"

    _SYSTEM_PROMPTS = {
        "intent": (
            "你是电商客服意图识别器。输入含【最近对话】【当前订单】【历史订单】上下文与【当前消息】"
            "（指代已消解并标注订单号）。\n"
            "任务1：判断【当前消息】属于以下哪种意图（可多选，逐条对号入座）：\n"
            "1. policy=政策咨询：询问退换货/运费/保修/退款到账等规则或适用条件，"
            "不含具体订单的办理。例：\"签收15天能退吗\"\"运费谁承担\"\"退款几天到账\"。\n"
            "2. order=订单查询：查询订单状态/明细/存在于否，以 ORD 订单号为对象。"
            "例：\"ORD001 状态怎么样\"\"我的订单发货了吗\"。\n"
            "3. logistics=物流查询：询问运输/配送/送达/运单轨迹，以商品在途为对象。"
            "例：\"快递到哪了\"\"今天能送达吗\"。\n"
            "4. aftersales=售后申请：用户发起新的售后办理动作"
            "（退货退款/仅退款/换货/申请赔偿等诉求词）。例：\"我要退货退款\"\"帮我申请换货\"\"我要仅退款\"。\n"
            "5. aftersales_status=售后进度查询：售后申请已发起后询问其处理进度/状态/结果，"
            "含\"进度\"\"到账了吗\"\"结果如何\"等。例：\"我的退款进度怎么样\"\"售后申请处理到哪了\"。\n"
            "易混淆边界：aftersales=新发起申请（动作词），aftersales_status=询问已发起的进度（结果词）；"
            "order=订单本身状态，logistics=订单的运输轨迹；policy=规则咨询，不落到具体订单的办理。"
            "若当前消息指代上下文提到的订单/政策，结合上下文识别对应意图（如\"这个政策适合我的订单吗\"=policy+order）。\n"
            "任务2：判断意图间执行关系（数据依赖）："
            "- aftersales 依赖 order（退款预检需订单号）→串行，order在前；"
            "- policy 依赖 order（政策问题引用订单，需订单信息判断适用性）→串行，order在前；"
            "- order与logistics同域共享订单→并行；"
            "- 其余两两无数据依赖→并行。\n"
            "输出JSON：{\"intents\":[\"标签\"],\"confidence\":0.x,"
            "\"execution\":{\"mode\":\"serial\"|\"parallel\",\"order\":[\"执行顺序\"],"
            "\"dependencies\":{\"依赖方\":\"被依赖方\"}}}。"
            "serial时order按执行先后排列；parallel时order为空数组、dependencies为空对象。"
            "无匹配intents时confidence为0.1。不要输出其他内容。"
        ),
        # 情绪识别+安抚合一（单轮单 Agent 完成）：
        # 非 angry/upset 时 soothe 必须为空字符串，不得编造安抚话术
        "emotion_assist": (
            "你是电商客服情绪助手。分析用户消息的情绪并判断是否需要安抚，输出一行JSON。"
            "情绪取值：calm=平静(0.0-0.4)，upset=不满(0.4-0.7)，angry=激动(0.7-1.0)，"
            "intensity 为介于对应区间的小数。"
            "若情绪为 angry 或 upset：soothe 输出安抚话术，只需包含两点——共情理解用户的心情感受、"
            "道歉并承诺马上跟进处理；不要索要订单号、不要提及金额或办理流程，"
            "话术自然亲切，不超过40字。"
            "若情绪为 calm：soothe 输出空字符串，不得编造安抚话术。"
            "输出格式：{\"emotion\":\"calm|upset|angry\",\"intensity\":0.x,\"soothe\":\"安抚话术或空字符串\"}。"
            "不要输出其他内容。"
        ),
        "policy_answer": (
            "你是电商政策顾问。根据用户问题和提供的条款内容回答。要求："
            "1.答案的每一句都必须有上方「可用条款」原文支撑，禁止用常识或条款之外的知识补全；"
            "2.引用条款来源(《标题》第X条)；"
            "3.若没有任何可用条款能回答问题（判定标准：问题涉及的商品类型/场景在所有条款标题和正文中"
            "都未被提及即属无匹配，即使在你自己的知识中是常识也不行），answer必须输出空字符串、"
            "has_source为false，严禁改用通用常识编造作答；"
            "输出前自检：逐句核对是否有条款原文对应，无对应则删除该句；全部删除后输出空字符串。"
            "4.若用户消息中含「先澄清/先询问」类要求，或问题只是泛指政策而没有具体咨询点"
            "（如「查询政策」「看看政策」），answer只输出一句礼貌追问（如「请问您想了解哪类政策"
            "：退换货、运费、保修、退款到账还是换货」），不得给出任何政策内容；"
            "但有具体咨询点的问题（如「运费谁出」「保修期多久」）不适用本条，直接按条款回答；"
            "若问题明确询问所有/全部政策有哪些、包含哪些方面"
            "（如「有哪些政策」「介绍所有售后政策」「售后包含哪些方面」），"
            "也排除在追问规则之外，此时列出所有可用政策类别的名称"
            "（至少退换货、运费、保修、退款到账、换货、特殊商品6类）并简述各类核心规定。"
            "只输出一行JSON：{\"answer\":\"回答\",\"has_source\":true|false}。"
        ),
        "refund_explain": (
            "你是电商售后专员。向用户说明退款/换货申请已创建。"
            "话术必须与申请阶段一致：\n"
            "- processing：仅退款，告知退款处理中，预计1-3个工作日到账；\n"
            "- waiting_return：退货退款，告知退款记录状态为待退货，需先寄回商品，商家签收后退款完成并更新状态为已完成，预计到账1-3个工作日；\n"
            "- exchange_reply：换货，告知换货记录状态为待寄回，需寄回原商品，商家收到并确认后发出新货，换货完成后更新状态为已完成。\n"
            "- 若提供了当前档位说明（tier_note），自然地在话术中说明一句该档位/窗口。\n"
            "开头语必须随申请类型变化：换货→已为您创建换货申请；退货退款→已为您创建退货退款申请；仅退款→已为您创建退款申请。\n"
            "内容包含：订单号、退款金额、类型。只输出话术文本，不要输出其他内容。"
        ),
        "aftersales_extract": (
            "你是售后申请解析器。从【当前消息】（含【最近对话】上下文）解析售后申请要素。"
            "任务：识别订单号（ORD开头，写不出则空字符串）与售后类型 request_type：\n"
            "- REFUND_ONLY：仅退款，不退货，只退钱；\n"
            "- RETURN_REFUND：退货退款，需要寄回商品；\n"
            "- EXCHANGE：换货/更换颜色或型号；\n"
            "规则：1)消息未表达售后意图、或仅是进度咨询（查进度/到账了吗）→ request_type 填 NONE，不得猜测；"
            "2)消息只说「退款」但未明确是否寄回时，视为退货退款 RETURN_REFUND 的语义倾向可填 RETURN_REFUND；"
            "3)order_number 只输出 ORD 开头的单号原文。\n"
            "输出一行JSON：{\"order_number\":\"ORDxxxxxxx\",\"request_type\":\"REFUND_ONLY|RETURN_REFUND|EXCHANGE|NONE\",\"amount\":数字或null}。"
            "amount 仅在消息明确金额时输出。不要输出其他内容。"
        ),
        "policy_classify": (
            "你是政策分类器。用户查询可能涉及以下政策类别（可多选）："
            "退换货政策、运费政策、退款到账政策、保修政策、换货政策、特殊商品政策。"
            "判断用户查询涉及哪些类别，只输出一行JSON："
            "{\"categories\":[\"类别名\"]}。无匹配时categories为空数组。不要输出其他内容。"
        ),
        "confirm_classify": (
            "你是售后单确认意图分类器。用户有一条待确认的售后单（订单号/类型/金额在输入中给出），"
            "判断【当前消息】对这条售后单的意图，只输出一行JSON：{\"action\":\"confirm|cancel|other\"}。\n"
            "- confirm：明确同意/确认创建售后单（确认/好的/可以/办吧等）；\n"
            "- cancel：明确取消（先不办/不退了/取消/算了等）；\n"
            "- other：与售后单确认无关的其他一切内容（追问其他问题、改金额/改类型、闲聊等），不得猜测为确认或取消。\n"
            "取消词与确认词同时出现时，取消优先。不要输出其他内容。"
        ),
    }

    def __init__(self, api_key: str, base_url: str, model: str = "spark-x2.6"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def complete(self, task: str, prompt: str, **kwargs: Any) -> dict:
        system = self._SYSTEM_PROMPTS.get(task, "")
        user = self._build_user(task, prompt, kwargs)
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "stream": False,
        }
        log_event("-", f"llm_call {task}", input=user)
        resp = requests.post(
            self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=data,
            timeout=90,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        parsed = self._parse(task, content)
        log_event("-", f"llm_result {task}", input="", output=str(parsed))
        return parsed

    def _build_user(self, task: str, prompt: str, kwargs: dict) -> str:
        if task == "policy_answer":
            clauses = kwargs.get("clauses", [])
            clause_text = "\n".join(
                f"- {c['title']}第{c['clause_id']}条：{c['content']}" for c in clauses
            )
            return f"用户问题：{prompt}\n可用条款：\n{clause_text}"
        if task == "refund_explain":
            return (
                f"申请阶段：{kwargs.get('stage','processing')}\n"
                f"订单号：{kwargs.get('order_number','')}，"
                f"退款类型：{kwargs.get('request_type','')}，"
                f"退款金额：{kwargs.get('amount',0)}"
            )
        if task == "confirm_classify":
            return (
                f"待确认售后单：订单号={kwargs.get('order_number','')}，"
                f"售后类型={kwargs.get('request_type','')}，"
                f"金额={kwargs.get('amount','')}\n"
                f"【当前消息】{prompt}"
            )
        return prompt

    def _parse(self, task: str, content: str) -> dict:
        text = content.strip()
        if task in ("intent", "emotion_assist", "policy_answer", "policy_classify",
                    "aftersales_extract", "confirm_classify"):
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
            # JSON 解析失败的兜底
            if task == "intent":
                return {"intents": [], "confidence": 0.1}
            if task == "emotion_assist":
                return {"emotion": "calm", "intensity": 0.2, "soothe": ""}
            if task == "policy_classify":
                return {"categories": [], "confidence": 0.2}
            if task == "aftersales_extract":
                return {"order_number": "", "request_type": "NONE", "amount": None}
            if task == "confirm_classify":
                return {"action": "other"}
            return {"answer": "", "has_source": False}
        # refund_explain：纯文本
        return {"text": text}


class ArkChatClient(XfSparkClient):
    """火山方舟 DeepSeek 聊天客户端（OpenAI 兼容格式）。

    继承 XfSparkClient 复用 _SYSTEM_PROMPTS / _build_user / _parse，
    仅 differ 在 base_url：Ark 网关路径 /api/coding/v3 需补全 /chat/completions。

    环境变量：
      ARK_API_KEY   API 密钥（ark-xxx）
      ARK_BASE_URL  API endpoint（默认 .../api/coding/v3）
      ARK_CHAT_MODEL 模型名（默认 deepseek-v4.1-flash）
    """

    def __init__(self, api_key: str, base_url: str, model: str = "deepseek-v4.1-flash"):
        u = base_url.rstrip("/")
        if not u.endswith("/chat/completions"):
            u = u + "/chat/completions"
        super().__init__(api_key, u, model)


def get_llm_client() -> LLMClient:
    """工厂：LLM_PROVIDER=ark 用火山方舟 DeepSeek，xf_spark 用讯飞 Spark，否则用 mock。

    密钥与地址从项目根 .env 读取（模板见 .env.example），此处不再硬编码。
    """
    if config.LLM_PROVIDER == "ark":
        return ArkChatClient(
            api_key=config.ARK_API_KEY,
            base_url=config.ARK_BASE_URL,
            model=config.ARK_CHAT_MODEL,
        )
    if config.LLM_PROVIDER == "xf_spark":
        return XfSparkClient(
            api_key=config.SPARK_API_KEY,
            base_url=config.SPARK_BASE_URL,
            model=config.SPARK_MODEL,
        )
    return MockLLMClient()
