"""选品 Agent 工具集：抓取、分析、报告。

设计思想：
- 每个工具是一个独立函数，用 LangChain @tool 装饰器封装
- 工具复用已有的 bitable_client 和 LLM，不重复造轮子
- 工具输入输出都用 JSON 序列化，便于 LLM 理解

四个工具：
1. fetch_products：查选品池表返回商品数据 JSON
2. fetch_reviews：查评论库表返回评论数据 JSON
3. analyze：调用 LLM 做四角度+六维度评分+决策，返回结构化 JSON
4. save_report：将分析结果写入分析报告表 + 推送卡片到飞书群
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.ai.model_router import get_model_router
from src.ai.prompt_manager import render_selection_prompt
from src.config import settings
from src.feishu.application_bot import application_bot
from src.feishu.bitable import bitable_client
from src.feishu.field_mapping import _extract_text
from src.observability.logger import get_logger

logger = get_logger()


# ============ 工具 1：抓取商品数据 ============

class FetchProductsArgs(BaseModel):
    """抓取商品工具的参数 schema。"""

    industry: str = Field(description="行业名称，如 '宠物用品'、'厨房用品'")
    platform: str = Field(description="平台名称，如 '亚马逊'、'Walmart'、'eBay'")


@tool(args_schema=FetchProductsArgs)
def fetch_products(industry: str, platform: str) -> str:
    """查询选品池表，返回指定行业+平台的商品数据 JSON。

    返回 JSON 格式的商品列表，包含商品ID、名称、价格、评分、评论数、排名等。
    """
    logger.info(f"工具调用: fetch_products(industry={industry}, platform={platform})")

    try:
        table_id = settings.feishu_table_id_selection
        if not table_id:
            return json.dumps({"error": "未配置选品池表 ID"}, ensure_ascii=False)

        # 查询选品池表
        records = bitable_client.query_records(table_id)

        # 筛选指定行业+平台
        products = []
        for record in records:
            fields = record.get("fields", {})
            record_industry = _extract_text(fields.get("行业", ""))
            record_platform = _extract_text(fields.get("平台", ""))

            if record_industry == industry and record_platform == platform:
                products.append(
                    {
                        "商品ID": _extract_text(fields.get("商品ID", "")),
                        "商品名称": _extract_text(fields.get("商品名称", "")),
                        "行业": record_industry,
                        "平台": record_platform,
                        "价格区间": _extract_text(fields.get("价格区间", "")),
                        "评分": _extract_text(fields.get("评分", "")),
                        "评论数": _extract_text(fields.get("评论数", "")),
                        "排名": _extract_text(fields.get("排名", "")),
                    }
                )

        logger.info(f"查询成功：{len(products)} 个商品")
        return json.dumps(products, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"fetch_products 失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============ 工具 2：抓取评论数据 ============

class FetchReviewsArgs(BaseModel):
    """抓取评论工具的参数 schema。"""

    industry: str = Field(description="行业名称")
    platform: str = Field(description="平台名称")


@tool(args_schema=FetchReviewsArgs)
def fetch_reviews(industry: str, platform: str) -> str:
    """查询评论库表，返回指定行业+平台关联商品的评论数据 JSON。

    返回 JSON 格式的评论列表，包含评论ID、商品ID、评论内容、评分、是否差评等。
    """
    logger.info(f"工具调用: fetch_reviews(industry={industry}, platform={platform})")

    try:
        table_id = settings.feishu_table_id_review
        if not table_id:
            return json.dumps({"error": "未配置评论库表 ID"}, ensure_ascii=False)

        # 查询评论库表
        records = bitable_client.query_records(table_id)

        # 先查选品池获取该行业+平台的商品ID列表
        selection_table_id = settings.feishu_table_id_selection
        product_ids = set()
        if selection_table_id:
            selection_records = bitable_client.query_records(selection_table_id)
            for record in selection_records:
                fields = record.get("fields", {})
                if (
                    _extract_text(fields.get("行业", "")) == industry
                    and _extract_text(fields.get("平台", "")) == platform
                ):
                    pid = _extract_text(fields.get("商品ID", ""))
                    if pid:
                        product_ids.add(pid)

        # 筛选评论：评论的商品ID在选品池中
        reviews = []
        for record in records:
            fields = record.get("fields", {})
            review_product_id = _extract_text(fields.get("商品ID", ""))
            if review_product_id in product_ids:
                reviews.append(
                    {
                        "评论ID": _extract_text(fields.get("评论ID", "")),
                        "商品ID": review_product_id,
                        "评论内容": _extract_text(fields.get("评论内容", "")),
                        "评分": _extract_text(fields.get("评分", "")),
                        "是否差评": fields.get("是否差评", False),
                    }
                )

        logger.info(f"查询成功：{len(reviews)} 条评论")
        return json.dumps(reviews, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"fetch_reviews 失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============ 工具 3：分析选品数据 ============

class AnalyzeArgs(BaseModel):
    """分析工具的参数 schema。"""

    industry: str = Field(description="行业名称")
    platform: str = Field(description="平台名称")
    products_json: str = Field(
        description="商品数据 JSON 字符串（由 fetch_products 工具返回）"
    )
    reviews_json: str = Field(
        description="评论数据 JSON 字符串（由 fetch_reviews 工具返回）"
    )


@tool(args_schema=AnalyzeArgs)
def analyze(industry: str, platform: str, products_json: str, reviews_json: str) -> str:
    """调用 LLM 分析选品数据，从四角度分析+六维度评分+决策矩阵给出选品建议。

    返回结构化 JSON，包含四角度分析、六维度评分、综合评分、决策、top_picks、summary。
    """
    logger.info(f"工具调用: analyze(industry={industry}, platform={platform})")

    try:
        # 获取 LLM
        router = get_model_router()
        llm = router.get_llm("complex", temperature=0.3)

        # 渲染 Prompt
        prompt = render_selection_prompt(industry, platform, products_json, reviews_json)

        logger.info(f"调用 LLM 分析 {industry}/{platform} 选品数据...")
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        logger.info("LLM 分析完成")
        return content

    except Exception as e:
        logger.error(f"analyze 失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============ 工具 4：保存报告 ============

class SaveReportArgs(BaseModel):
    """保存报告工具的参数 schema。"""

    analysis_json: str = Field(
        description="分析结果 JSON 字符串（由 analyze 工具返回）"
    )
    push_to_feishu: bool = Field(
        default=True,
        description="是否推送报告到飞书群，默认 True",
    )


@tool(args_schema=SaveReportArgs)
def save_report(analysis_json: str, push_to_feishu: bool = True) -> str:
    """将选品分析结果写入飞书多维表格（分析报告表）并推送卡片到飞书群。

    成功返回保存的记录信息和推送状态。
    """
    logger.info(f"工具调用: save_report(push_to_feishu={push_to_feishu})")

    try:
        # 解析 LLM 返回的 JSON（可能被 ```json 代码块包裹）
        analysis_text = analysis_json.strip()
        if analysis_text.startswith("```"):
            # 去除 ```json 和 ``` 包裹
            lines = analysis_text.split("\n")
            analysis_text = "\n".join(lines[1:-1])

        analysis = json.loads(analysis_text)
        industry = analysis.get("行业", "未知行业")
        platform = analysis.get("平台", "未知平台")
        decision = analysis.get("决策", "")
        risk_level = analysis.get("风险等级", "")
        top_picks = analysis.get("top_picks", [])
        summary = analysis.get("summary", "")

        # 生成报告ID
        report_id = f"report_{int(__import__("datetime").datetime.now().timestamp() * 1000)}"

        # 1. 写入飞书多维表格（分析报告表）
        table_id = settings.feishu_table_id_report
        saved = False

        if table_id:
            record = {
                "报告ID": report_id,
                "行业": industry,
                "平台": platform,
                "分析时间": int(__import__("datetime").datetime.now().timestamp() * 1000),
                "四角度JSON": json.dumps(
                    analysis.get("四角度分析", {}), ensure_ascii=False
                ),
                "六维度评分": json.dumps(
                    analysis.get("六维度评分", {}), ensure_ascii=False
                ),
                "决策": decision,
                "风险等级": risk_level,
                "top_picks": json.dumps(top_picks, ensure_ascii=False),
                "summary": summary,
            }
            bitable_client.add_record(table_id, record)
            saved = True
            logger.info(f"分析报告已写入飞书多维表格: {report_id}")
        else:
            logger.warning("未配置分析报告表 ID，跳过多维表格写入")

        # 2. 推送 AI 分析报告卡片到飞书群
        pushed = False
        if push_to_feishu:
            try:
                card = {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "title": {"tag": "plain_text", "content": f"📊 选品策略报告 - {industry}"},
                        "template": "blue",
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "text": {"tag": "lark_md", "content": f"**平台**: {platform}\n**决策**: {decision}\n**风险等级**: {risk_level}"},
                        },
                        {
                            "tag": "div",
                            "text": {"tag": "lark_md", "content": f"**总结**: {summary[:200]}"},
                        },
                    ],
                }
                # 优先使用 Webhook 机器人，失败则回退到应用机器人
                from src.feishu.feishu_bot import feishu_bot
                pushed = False
                if feishu_bot.is_configured:
                    pushed = feishu_bot.send_card(card)
                    if pushed:
                        logger.info("Webhook机器人推送成功")
                if not pushed:
                    pushed = application_bot.send_card(card)
                    if pushed:
                        logger.info("应用机器人推送成功")
                if pushed:
                    logger.info("AI 分析报告卡片已推送到飞书群")
            except Exception as e:
                logger.error(f"推送飞书群失败: {e}")

        result = {
            "saved_to_bitable": saved,
            "pushed_to_feishu": pushed,
            "message": f"分析报告{'已保存' if saved else '未保存'}到多维表格，"
                       f"飞书群推送{'成功' if pushed else '失败'}",
        }
        logger.info(f"save_report 完成: {result}")
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        logger.error(f"save_report 失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# 导出所有工具列表（供 Agent 注册使用）
SELECTION_TOOLS = [fetch_products, fetch_reviews, analyze, save_report]
