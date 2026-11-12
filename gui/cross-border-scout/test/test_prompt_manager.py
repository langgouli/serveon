"""Task 3.1 Prompt 管理测试。

覆盖：正常（四角度/六维度/权重/决策矩阵/JSON输出）、渲染（替换占位符/保留JSON示例）。
"""

from __future__ import annotations

from src.ai.prompt_manager import SELECTION_STRATEGY_PROMPT, render_selection_prompt


def test_prompt_contains_four_angles() -> None:
    """正常场景：含四角度分析。"""
    for angle in ["市场机会", "竞品定价", "用户痛点", "利润测算"]:
        assert angle in SELECTION_STRATEGY_PROMPT


def test_prompt_contains_six_dimensions() -> None:
    """正常场景：含六维度评分。"""
    for dim in ["需求强度", "竞争强度", "利润率", "运营难度", "风险等级", "机会窗口"]:
        assert dim in SELECTION_STRATEGY_PROMPT


def test_prompt_contains_weights() -> None:
    """正常场景：六维度权重正确。"""
    assert "20%" in SELECTION_STRATEGY_PROMPT
    assert "25%" in SELECTION_STRATEGY_PROMPT
    assert "15%" in SELECTION_STRATEGY_PROMPT
    assert "5%" in SELECTION_STRATEGY_PROMPT


def test_prompt_contains_decision_matrix() -> None:
    """正常场景：含五档决策矩阵。"""
    for decision in ["强烈推荐", "谨慎推荐", "值得尝试", "暂不推荐", "建议避开"]:
        assert decision in SELECTION_STRATEGY_PROMPT


def test_prompt_requires_json_output() -> None:
    """正常场景：要求 JSON 输出，含 top_picks/summary。"""
    assert "json" in SELECTION_STRATEGY_PROMPT.lower()
    assert "top_picks" in SELECTION_STRATEGY_PROMPT
    assert "summary" in SELECTION_STRATEGY_PROMPT


def test_render_selection_prompt() -> None:
    """正常场景：渲染后含输入数据。"""
    prompt = render_selection_prompt("宠物用品", "亚马逊", "[]", "[]")
    assert "宠物用品" in prompt
    assert "亚马逊" in prompt


def test_render_replaces_all_placeholders() -> None:
    """正常场景：渲染后无残留占位符。"""
    prompt = render_selection_prompt("宠物用品", "亚马逊", "[]", "[]")
    for placeholder in ["{industry}", "{platform}", "{products_json}", "{reviews_json}"]:
        assert placeholder not in prompt


def test_render_with_empty_reviews() -> None:
    """边界场景：空评论数据不报错。"""
    prompt = render_selection_prompt("宠物用品", "亚马逊", "[]", "")
    assert "宠物用品" in prompt


def test_render_preserves_json_example() -> None:
    """正常场景：渲染后保留 JSON 示例结构。"""
    prompt = render_selection_prompt("宠物用品", "亚马逊", "[]", "[]")
    assert "四角度分析" in prompt
    assert "六维度评分" in prompt
