"""选品分析 Agent：基于 LangGraph create_react_agent 的 ReAct Agent。

设计思想：
- Agent 自主决策调用工具（fetch_products/fetch_reviews/analyze/save_report）
- 采用 ReAct 模式：Thought → Action → Observation → 循环
- 输入行业+平台，Agent 自动抓取数据→分析→生成报告→保存推送
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.ai.agents.selection_tools import SELECTION_TOOLS
from src.ai.model_router import get_model_router
from src.observability.logger import get_logger

logger = get_logger()


# 系统 Prompt：指导 Agent 的工作流程
AGENT_SYSTEM_PROMPT = """你是一个跨境电商选品策略 Agent。你的任务是基于行业和平台，完成选品策略分析并生成报告。

工作流程：
1. 调用 fetch_products 获取商品数据
2. 调用 fetch_reviews 获取评论数据（如有）
3. 调用 analyze 进行四角度分析+六维度评分+决策
4. 调用 save_report 保存报告并推送飞书（只调用一次）

注意事项：
- 如果评论数据为空，仍然继续分析（评论数据可选）
- analyze 返回的 JSON 可能被 ```json 代码块包裹，save_report 会处理
- 如果某个工具调用失败，继续尝试其他工具或给出建议
- save_report 只能调用一次，调用成功后任务即完成
- save_report 必须传入正确的行业和平台参数（与用户输入一致）
"""


def create_selection_agent() -> Any:
    """创建选品分析 ReAct Agent。

    Returns:
        LangGraph Agent 实例

    Raises:
        ValueError: 未配置 AI 模型凭证时抛出
    """
    from langgraph.prebuilt import create_react_agent

    router = get_model_router()
    llm = router.get_llm("complex", temperature=0.3)

    agent = create_react_agent(
        model=llm,
        tools=SELECTION_TOOLS,
        prompt=AGENT_SYSTEM_PROMPT,
    )

    logger.info("选品分析 Agent 创建成功")
    return agent


def run_selection_agent(industry: str, platform: str) -> dict[str, Any]:
    """运行选品分析 Agent。

    Args:
        industry: 行业名称
        platform: 平台名称

    Returns:
        dict 包含：
        - success: 是否成功
        - analysis: 分析结果（解析后的 JSON dict）
        - raw_output: 原始输出文本
        - error: 错误信息（失败时）
    """
    try:
        agent = create_selection_agent()

        user_input = f"请对 {industry} 在 {platform} 平台进行选品策略分析，并生成报告。"

        logger.info(f"运行选品 Agent: {industry}/{platform}")
        result = agent.invoke(
            {"messages": [SystemMessage(content=AGENT_SYSTEM_PROMPT), HumanMessage(content=user_input)]},
            config={"recursion_limit": 10},
        )

        # 提取最后一条 AI 消息
        messages = result.get("messages", [])
        last_ai_message = None
        for msg in reversed(messages):
            if msg.type == "ai":
                last_ai_message = msg
                break

        if not last_ai_message:
            return {
                "success": False,
                "analysis": None,
                "raw_output": "",
                "error": "未找到 AI 消息",
            }

        content = last_ai_message.content
        if isinstance(content, list):
            # LangChain 多模态内容格式
            content = " ".join(
                block.get("text", "") for block in content if isinstance(block, dict)
            )

        # 尝试解析 JSON
        analysis = _extract_json_from_text(content)

        if analysis:
            logger.info("Agent 运行成功，已解析分析结果")
            return {
                "success": True,
                "analysis": analysis,
                "raw_output": content,
                "error": None,
            }
        else:
            logger.info(f"Agent 运行完成，返回 Markdown 格式报告")
            return {
                "success": True,
                "analysis": {"summary": content},
                "raw_output": content,
                "error": None,
            }

    except Exception as e:
        logger.error(f"运行选品 Agent 失败: {e}", exc_info=True)
        return {
            "success": False,
            "analysis": None,
            "raw_output": "",
            "error": str(e),
        }


def _extract_json_from_text(text: str) -> dict[str, Any] | None:
    """从文本中提取 JSON 对象。

    支持两种格式：
    1. ```json ... ``` 代码块包裹
    2. 直接 JSON 文本

    Args:
        text: 可能包含 JSON 的文本

    Returns:
        解析后的 dict，失败返回 None
    """
    # 尝试匹配 ```json ... ``` 代码块
    code_block_match = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if code_block_match:
        json_str = code_block_match.group(1).strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # 尝试匹配 ``` ... ``` 代码块（无语言标识）
    code_block_match = re.search(r"```\s*\n(.*?)\n```", text, re.DOTALL)
    if code_block_match:
        json_str = code_block_match.group(1).strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # 尝试直接解析整个文本
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 尝试提取第一个 { 到最后一个 } 之间的内容
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_str = text[start : end + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    return None
