"""选品分析 Agent 模块。

导出：
- fetch_products: 查选品池表返回商品数据
- fetch_reviews: 查评论库表返回评论数据
- analyze: 调用 LLM 做四角度+六维度评分+决策
- save_report: 保存报告到分析报告表+推送飞书
- SELECTION_TOOLS: 工具列表（供 Agent 注册）
- create_selection_agent: 创建 ReAct Agent
- run_selection_agent: 运行 Agent 并解析结果
"""

from src.ai.agents.selection_tools import (
    analyze,
    fetch_products,
    fetch_reviews,
    save_report,
    SELECTION_TOOLS,
)
from src.ai.agents.selection_agent import (
    create_selection_agent,
    run_selection_agent,
)

__all__ = [
    "fetch_products",
    "fetch_reviews",
    "analyze",
    "save_report",
    "SELECTION_TOOLS",
    "create_selection_agent",
    "run_selection_agent",
]
