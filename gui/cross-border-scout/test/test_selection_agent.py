"""Task 3.4-3.5 选品 Agent 测试。

覆盖：正常（JSON解析/Agent创建/Agent运行）、边界（空输出/无AI消息）、异常（LLM失败/Agent异常）。
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from src.ai.agents.selection_agent import (
    _extract_json_from_text,
    create_selection_agent,
    run_selection_agent,
)


# ============ _extract_json_from_text ============

def test_extract_json_from_code_block() -> None:
    """正常场景：解析 ```json 代码块。"""
    text = '```json\n{"综合评分": 85, "决策": "强烈推荐"}\n```'
    result = _extract_json_from_text(text)
    assert result is not None
    assert result["综合评分"] == 85


def test_extract_json_from_plain_code_block() -> None:
    """正常场景：解析 ``` 代码块（无语言标识）。"""
    text = '```\n{"综合评分": 70, "决策": "谨慎推荐"}\n```'
    result = _extract_json_from_text(text)
    assert result is not None
    assert result["综合评分"] == 70


def test_extract_json_from_raw_text() -> None:
    """正常场景：直接解析 JSON 文本。"""
    text = '{"综合评分": 60, "决策": "值得尝试"}'
    result = _extract_json_from_text(text)
    assert result is not None
    assert result["综合评分"] == 60


def test_extract_json_from_text_with_prefix() -> None:
    """正常场景：从带前缀文本中提取 JSON。"""
    text = '分析结果如下：\n{"综合评分": 50, "决策": "建议避开"}\n以上。'
    result = _extract_json_from_text(text)
    assert result is not None
    assert result["综合评分"] == 50


def test_extract_json_invalid() -> None:
    """异常场景：无效 JSON 返回 None。"""
    text = "这不是 JSON"
    assert _extract_json_from_text(text) is None


def test_extract_json_empty() -> None:
    """边界场景：空文本返回 None。"""
    assert _extract_json_from_text("") is None


def test_extract_json_malformed_code_block() -> None:
    """异常场景：格式错误的代码块返回 None。"""
    text = '```json\n{"invalid": json}\n```'
    assert _extract_json_from_text(text) is None


# ============ create_selection_agent ============

def test_create_selection_agent_success() -> None:
    """正常场景：创建 Agent 成功。"""
    fake_llm = MagicMock()
    fake_agent = MagicMock()

    with patch("src.ai.agents.selection_agent.get_model_router") as mock_router, \
         patch("langgraph.prebuilt.create_react_agent") as mock_create:
        mock_router.return_value.get_llm.return_value = fake_llm
        mock_create.return_value = fake_agent

        agent = create_selection_agent()
        assert agent is fake_agent
        mock_create.assert_called_once()


def test_create_selection_agent_no_credentials() -> None:
    """异常场景：未配置凭证抛出异常。"""
    with patch("src.ai.agents.selection_agent.get_model_router") as mock_router:
        mock_router.return_value.get_llm.side_effect = ValueError("未配置 AI 模型凭证")
        try:
            create_selection_agent()
            assert False, "应该抛出异常"
        except ValueError:
            pass


# ============ run_selection_agent ============

def test_run_selection_agent_success() -> None:
    """正常场景：Agent 运行成功并解析 JSON。"""
    analysis_result = {
        "综合评分": 85,
        "决策": "强烈推荐",
        "风险等级": "低",
    }
    ai_message = MagicMock()
    ai_message.type = "ai"
    ai_message.content = f'```json\n{json.dumps(analysis_result, ensure_ascii=False)}\n```'

    agent_result = {"messages": [ai_message]}
    fake_agent = MagicMock()
    fake_agent.invoke.return_value = agent_result

    with patch("src.ai.agents.selection_agent.create_selection_agent", return_value=fake_agent):
        result = run_selection_agent("宠物用品", "亚马逊")
        assert result["success"] is True
        assert result["analysis"]["综合评分"] == 85
        assert result["error"] is None


def test_run_selection_agent_no_ai_message() -> None:
    """边界场景：无 AI 消息返回失败。"""
    agent_result = {"messages": []}
    fake_agent = MagicMock()
    fake_agent.invoke.return_value = agent_result

    with patch("src.ai.agents.selection_agent.create_selection_agent", return_value=fake_agent):
        result = run_selection_agent("宠物用品", "亚马逊")
        assert result["success"] is False
        assert "未找到 AI 消息" in result["error"]


def test_run_selection_agent_invalid_json() -> None:
    """异常场景：AI 输出无法解析为 JSON。"""
    ai_message = MagicMock()
    ai_message.type = "ai"
    ai_message.content = "这不是 JSON 输出"

    agent_result = {"messages": [ai_message]}
    fake_agent = MagicMock()
    fake_agent.invoke.return_value = agent_result

    with patch("src.ai.agents.selection_agent.create_selection_agent", return_value=fake_agent):
        result = run_selection_agent("宠物用品", "亚马逊")
        assert result["success"] is False
        assert "解析" in result["error"]


def test_run_selection_agent_agent_error() -> None:
    """异常场景：Agent 运行异常。"""
    fake_agent = MagicMock()
    fake_agent.invoke.side_effect = RuntimeError("Agent 运行失败")

    with patch("src.ai.agents.selection_agent.create_selection_agent", return_value=fake_agent):
        result = run_selection_agent("宠物用品", "亚马逊")
        assert result["success"] is False
        assert "Agent 运行失败" in result["error"]


def test_run_selection_agent_list_content() -> None:
    """正常场景：AI 消息内容为列表格式。"""
    analysis_result = {"综合评分": 90, "决策": "强烈推荐"}
    ai_message = MagicMock()
    ai_message.type = "ai"
    ai_message.content = [
        {"type": "text", "text": f'```json\n{json.dumps(analysis_result, ensure_ascii=False)}\n```'},
    ]

    agent_result = {"messages": [ai_message]}
    fake_agent = MagicMock()
    fake_agent.invoke.return_value = agent_result

    with patch("src.ai.agents.selection_agent.create_selection_agent", return_value=fake_agent):
        result = run_selection_agent("宠物用品", "亚马逊")
        assert result["success"] is True
        assert result["analysis"]["综合评分"] == 90
