"""飞书交互卡片模板库。

集中管理各类业务卡片的 JSON 模板，避免在业务代码中硬编码卡片结构。

卡片模板设计原则：
1. 标题颜色按严重程度区分（red=紧急/orange=预警/yellow=关注/green=正常/blue=普通通知）
2. 正文用 lark_md 格式，支持加粗、链接
3. 底部统一放"查看详情"按钮，跳转飞书多维表格
4. 每个模板函数返回纯 dict，便于测试和复用
"""

from __future__ import annotations

from typing import Any

from src.config import settings


# 决策 → 卡片标题颜色映射
DECISION_TEMPLATE_MAP = {
    "强烈推荐": "green",
    "谨慎推荐": "blue",
    "值得尝试": "yellow",
    "暂不推荐": "orange",
    "建议避开": "red",
}


# 风险等级 → 颜色映射
RISK_TEMPLATE_MAP = {
    "低": "green",
    "中": "blue",
    "高": "red",
}


def build_table_url(table_id: str = "") -> str:
    """构建飞书多维表格 URL（在飞书桌面端可直接打开，不跳浏览器）。

    Args:
        table_id: 表格 ID，留空则用选品池表 ID

    Returns:
        多维表格 URL，若未配置租户域名或 app_token 则返回空字符串
    """
    app_token = settings.feishu_bitable_app_token
    tenant_domain = settings.feishu_tenant_domain
    target_table_id = table_id or settings.feishu_table_id_selection
    if not app_token or not tenant_domain or not target_table_id:
        return ""
    return (
        f"https://{tenant_domain}.feishu.cn/base/{app_token}"
        f"?table={target_table_id}"
    )


# ============================================================
# 选品策略报告卡片
# ============================================================


def build_selection_strategy_card(
    industry: str,
    platform: str,
    analysis: dict[str, Any],
    table_url: str = "",
) -> dict[str, Any]:
    """构建选品策略报告卡片。

    展示四角度分析、六维度评分、决策、top_picks、summary。

    Args:
        industry: 行业名称
        platform: 平台名称
        analysis: 分析结果 dict（含四角度分析/六维度评分/综合评分/决策/风险等级/top_picks/summary）
        table_url: 分析报告表链接

    Returns:
        飞书卡片 JSON 对象
    """
    decision = analysis.get("决策", "")
    risk_level = analysis.get("风险等级", "")
    total_score = analysis.get("综合评分", 0)
    top_picks = analysis.get("top_picks", [])
    summary = analysis.get("summary", "")
    four_angles = analysis.get("四角度分析", {})
    six_dimensions = analysis.get("六维度评分", {})

    # 标题颜色：决策决定
    template_color = DECISION_TEMPLATE_MAP.get(decision, "blue")

    elements: list[dict[str, Any]] = [
        # 顶部：行业+平台+综合评分
        {
            "tag": "div",
            "fields": [
                {
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**行业**\n{industry}",
                    },
                },
                {
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**平台**\n{platform}",
                    },
                },
                {
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**综合评分**\n**{total_score}**",
                    },
                },
                {
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**风险等级**\n{risk_level}",
                    },
                },
            ],
        },
        {"tag": "hr"},
    ]

    # 决策标签
    if decision:
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**决策建议**：{decision}",
            },
        })
        elements.append({"tag": "hr"})

    # 四角度分析
    if four_angles:
        angles_lines = []
        for angle_name, angle_desc in four_angles.items():
            if angle_desc:
                angles_lines.append(f"**{angle_name}**：{angle_desc}")
        if angles_lines:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**📊 四角度分析**\n\n" + "\n\n".join(angles_lines[:4]),
                },
            })
            elements.append({"tag": "hr"})

    # 六维度评分
    if six_dimensions:
        dim_lines = []
        for dim_name, dim_score in six_dimensions.items():
            if dim_score is not None:
                dim_lines.append(f"{dim_name}：{dim_score}")
        if dim_lines:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**📈 六维度评分**\n" + "\n".join(dim_lines),
                },
            })
            elements.append({"tag": "hr"})

    # Top 推荐商品
    if top_picks:
        picks_lines = []
        for i, pick in enumerate(top_picks[:3], start=1):
            name = pick.get("商品名称", "未知商品")
            pid = pick.get("商品ID", "")
            reason = pick.get("推荐理由", "")
            margin = pick.get("预估利润率", "")
            picks_lines.append(
                f"**{i}. {name}**\n"
                f"商品ID: {pid} | 预估利润率: {margin}\n"
                f"推荐理由: {reason}"
            )
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": "**🏆 Top 推荐**\n\n" + "\n\n".join(picks_lines),
            },
        })
        elements.append({"tag": "hr"})

    # AI 总结
    if summary:
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**📋 总结**\n{summary[:300]}",
            },
        })

    # "查看分析报告"按钮
    table_url = table_url or build_table_url(settings.feishu_table_id_report)
    if table_url:
        elements.append({
            "tag": "action",
            "actions": [{
                "tag": "button",
                "text": {"tag": "plain_text", "content": "📊 查看分析报告"},
                "url": table_url,
                "type": "primary",
            }],
        })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"🤖 选品策略报告 · {industry}",
            },
            "template": template_color,
        },
        "elements": elements,
    }


# ============================================================
# 采集日报卡片
# ============================================================


def build_collection_report_card(
    date: str,
    total_configs: int,
    new_count: int,
    update_count: int,
    skip_count: int,
    fail_count: int,
    table_url: str = "",
) -> dict[str, Any]:
    """构建采集日报卡片。

    展示采集统计：新增/更新/跳过/失败。

    Args:
        date: 采集日期
        total_configs: 总配置数
        new_count: 新增商品数
        update_count: 更新商品数
        skip_count: 跳过数
        fail_count: 失败数
        table_url: 选品池表链接

    Returns:
        飞书卡片 JSON 对象
    """
    total_processed = new_count + update_count

    elements: list[dict[str, Any]] = [
        {
            "tag": "div",
            "fields": [
                {
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**采集日期**\n{date}",
                    },
                },
                {
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**配置数**\n{total_configs} 条",
                    },
                },
                {
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**新增商品**\n**{new_count}** 个",
                    },
                },
                {
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**更新商品**\n{update_count} 个",
                    },
                },
                {
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**跳过**\n{skip_count} 个",
                    },
                },
                {
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**失败**\n{fail_count} 个",
                    },
                },
            ],
        },
        {"tag": "hr"},
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**总处理商品数**：**{total_processed}** 个",
            },
        },
    ]

    # 失败数大于 0 时增加警告
    if fail_count > 0:
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"⚠️ 有 {fail_count} 条配置采集失败，请查看日志排查原因",
            },
        })

    # "查看选品池"按钮
    table_url = table_url or build_table_url(settings.feishu_table_id_selection)
    if table_url:
        elements.append({
            "tag": "action",
            "actions": [{
                "tag": "button",
                "text": {"tag": "plain_text", "content": "查看选品池"},
                "url": table_url,
                "type": "primary",
            }],
        })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"【采集日报】{date}",
            },
            "template": "blue",
        },
        "elements": elements,
    }


# ============================================================
# 评论分析卡片
# ============================================================


def build_review_analysis_card(
    industry: str,
    platform: str,
    total_reviews: int,
    negative_count: int,
    avg_rating: float,
    key_complaints: list[str],
    table_url: str = "",
) -> dict[str, Any]:
    """构建评论分析卡片。

    展示评论分析统计：评论数、差评数、平均评分、主要投诉。

    Args:
        industry: 行业名称
        platform: 平台名称
        total_reviews: 评论总数
        negative_count: 差评数
        avg_rating: 平均评分
        key_complaints: 主要投诉列表
        table_url: 评论库表链接

    Returns:
        飞书卡片 JSON 对象
    """
    # 差评率
    negative_rate = (negative_count / total_reviews * 100) if total_reviews > 0 else 0
    header_color = "red" if negative_rate > 20 else "blue"

    elements: list[dict[str, Any]] = [
        {
            "tag": "div",
            "fields": [
                {
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**行业**\n{industry}",
                    },
                },
                {
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**平台**\n{platform}",
                    },
                },
                {
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**评论总数**\n{total_reviews}",
                    },
                },
                {
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**差评数**\n{negative_count}",
                    },
                },
                {
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**平均评分**\n{avg_rating}",
                    },
                },
                {
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**差评率**\n{negative_rate:.1f}%",
                    },
                },
            ],
        },
        {"tag": "hr"},
    ]

    # 主要投诉
    if key_complaints:
        complaints_text = "\n".join(f"• {c}" for c in key_complaints[:5])
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**⚠️ 主要投诉**\n{complaints_text}",
            },
        })
        elements.append({"tag": "hr"})

    # "查看评论库"按钮
    table_url = table_url or build_table_url(settings.feishu_table_id_review)
    if table_url:
        elements.append({
            "tag": "action",
            "actions": [{
                "tag": "button",
                "text": {"tag": "plain_text", "content": "查看评论库"},
                "url": table_url,
                "type": "primary",
            }],
        })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"📊 评论分析 · {industry}",
            },
            "template": header_color,
        },
        "elements": elements,
    }
