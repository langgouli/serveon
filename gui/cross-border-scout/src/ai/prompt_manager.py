"""选品策略 Prompt 管理：四角度分析 + 六维度评分 + 决策矩阵。

Prompt 要求 LLM 输出结构化 JSON（四角度+六维度评分+决策+top_picks+summary），
用 ```json 代码块包裹。
"""

from __future__ import annotations

SELECTION_STRATEGY_PROMPT = """你是一个跨境电商选品策略分析师。基于商品数据和评论数据，从四个角度分析选品机会，进行六维度评分，给出决策建议。

## 四角度分析
1. 市场机会：市场需求规模、增长趋势、季节性
2. 竞品定价：竞品价格分布、定价策略、价格带机会
3. 用户痛点：评论中的不满、未满足的需求
4. 利润测算：售价-平台佣金-FBA物流-广告-退货-采购成本=毛利，测算利润空间

## 六维度评分（每维度0-100分）
- 需求强度（权重20%）
- 竞争强度（权重20%）
- 利润率（权重25%）
- 运营难度（权重15%）
- 风险等级（权重15%）
- 机会窗口（权重5%）
综合评分 = 六维度加权求和

## 决策矩阵
- 综合评分80-100 且 风险低 → 强烈推荐
- 综合评分80-100 且 风险中 → 谨慎推荐
- 综合评分60-79 且 风险低 → 值得尝试
- 综合评分60-79 且 风险中高 → 暂不推荐
- 综合评分<60 → 建议避开

## 输出格式
用 json 代码块输出，严格遵循以下结构：
```json
{
  "行业": "{industry}",
  "平台": "{platform}",
  "四角度分析": {
    "市场机会": "...",
    "竞品定价": "...",
    "用户痛点": "...",
    "利润测算": "..."
  },
  "六维度评分": {
    "需求强度": 85,
    "竞争强度": 70,
    "利润率": 80,
    "运营难度": 60,
    "风险等级": 75,
    "机会窗口": 70
  },
  "综合评分": 78,
  "决策": "谨慎推荐",
  "风险等级": "中",
  "top_picks": [
    {"商品ID": "...", "商品名称": "...", "推荐理由": "...", "预估利润率": "..."}
  ],
  "summary": "..."
}
```

## 输入数据
行业：{industry}
平台：{platform}

商品数据：
{products_json}

评论数据：
{reviews_json}
"""


def render_selection_prompt(
    industry: str, platform: str, products_json: str, reviews_json: str
) -> str:
    """渲染选品策略 Prompt。

    Args:
        industry: 行业关键词
        platform: 平台名
        products_json: 商品数据 JSON 字符串
        reviews_json: 评论数据 JSON 字符串

    Returns:
        渲染后的完整 Prompt
    """
    return (
        SELECTION_STRATEGY_PROMPT
        .replace("{industry}", industry)
        .replace("{platform}", platform)
        .replace("{products_json}", products_json)
        .replace("{reviews_json}", reviews_json)
    )
