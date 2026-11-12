"""定时任务函数定义：每个任务独立 try-except，失败不影响其他任务。

三个核心任务：
1. product_collection_task - 选品数据采集（增量同步）
2. selection_analysis_task - 选品策略分析（调用 Agent 生成报告）
3. data_cleanup_task - 数据清理（每三天执行，防止数据堆积）
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from src.config import settings
from src.feishu.bitable import bitable_client
from src.feishu.field_mapping import _extract_text
from src.observability.logger import get_logger

logger = get_logger()


def _extract_field_value(field_value: Any, default: str = "") -> str:
    """统一解析飞书字段值，兼容文本/单选/多选格式。

    Args:
        field_value: 飞书返回的字段原始值
        default: 解析失败时的默认值

    Returns:
        字段值的字符串形式
    """
    if field_value is None:
        return default
    if isinstance(field_value, str):
        return field_value
    if isinstance(field_value, list):
        if not field_value:
            return default
        first = field_value[0]
        if isinstance(first, dict):
            return first.get("text") or first.get("name") or default
        return str(first)
    return str(field_value)


def _load_collection_configs() -> list[dict[str, Any]]:
    """从飞书"采集配置"表读取所有启用的采集配置。

    Returns:
        启用状态的配置列表
    """
    table_id = settings.feishu_table_id_collection_config
    if not table_id:
        logger.error("采集配置表 ID 未配置")
        return []

    filter_condition = {
        "conjunction": "and",
        "conditions": [
            {
                "field_name": "启用状态",
                "operator": "is",
                "value": ["启用"],
            }
        ],
    }
    records = bitable_client.query_records(table_id, filter_condition=filter_condition)

    configs: list[dict[str, Any]] = []
    for record in records:
        fields = record.get("fields", {})
        industry = _extract_field_value(fields.get("行业"))
        platform_raw = fields.get("平台", [])

        # 平台可能是多选 [{"name": "亚马逊"}, {"name": "eBay"}]
        platforms = []
        if isinstance(platform_raw, list):
            for p in platform_raw:
                if isinstance(p, dict):
                    platforms.append(p.get("name", ""))
                elif isinstance(p, str):
                    platforms.append(p)
        elif isinstance(platform_raw, str):
            platforms.append(platform_raw)

        count = fields.get("采集数量", 20)
        review_count = fields.get("评论采集数", 0)

        # 检查启用状态（SQL 过滤可能不生效时二次检查）
        enable_status = _extract_field_value(fields.get("启用状态"))
        if enable_status and enable_status != "启用":
            continue

        if not industry:
            continue

        configs.append({
            "industry": industry,
            "platforms": platforms,
            "collect_count": int(count) if count else 20,
            "review_count": int(review_count) if review_count else 0,
        })

    return configs


def product_collection_task() -> dict[str, Any]:
    """选品数据采集任务：从采集配置表读取配置，执行采集并同步到选品池。

    Returns:
        采集结果统计
    """
    try:
        logger.info("开始执行选品数据采集任务")

        # 加载采集配置
        configs_data = _load_collection_configs()
        if not configs_data:
            logger.warning("无启用的采集配置，跳过采集")
            return {"status": "skipped", "reason": "无启用配置"}

        # 执行采集
        from src.pipeline.collectors.collection_config import CollectionConfig
        from src.pipeline.collection_runner import CollectionRunner
        from src.feishu.sync_service import create_selection_sync_service

        configs = [
            CollectionConfig(
                industry=c["industry"],
                platforms=c["platforms"],
                collect_count=c.get("collect_count", 20),
                review_count=c.get("review_count", 0),
            )
            for c in configs_data
        ]

        runner = CollectionRunner(sync_service=create_selection_sync_service())
        result = runner.run(configs)

        # 统计
        total_products = sum(len(r.products) for r in result.collection_results)
        new_count = result.sync_result.new_count if result.sync_result else 0

        logger.info(f"采集完成：{total_products} 个商品，新增 {new_count} 个")

        # 推送采集日报卡片
        try:
            from src.feishu.application_bot import application_bot
            from src.feishu.feishu_bot import feishu_bot
            from src.feishu.card_templates import build_collection_report_card

            date_str = datetime.now().strftime("%Y-%m-%d")
            card = build_collection_report_card(
                date=date_str,
                total_configs=len(configs),
                new_count=new_count,
                update_count=result.sync_result.update_count if result.sync_result else 0,
                skip_count=result.sync_result.skip_count if result.sync_result else 0,
                fail_count=result.sync_result.fail_count if result.sync_result else 0,
            )
            # 优先使用 Webhook 机器人，失败则回退到应用机器人
            pushed = False
            if feishu_bot.is_configured:
                pushed = feishu_bot.send_card(card)
            if not pushed:
                pushed = application_bot.send_card(card)
            if pushed:
                logger.info("采集日报卡片已推送")
        except Exception as e:
            logger.error(f"推送采集日报失败: {e}")

        return {
            "status": "success",
            "total_products": total_products,
            "new_count": new_count,
        }

    except Exception as e:
        logger.error(f"采集任务失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def selection_analysis_task() -> dict[str, Any]:
    """选品策略分析任务：对采集到的商品数据执行 Agent 分析，生成报告并推送。

    Returns:
        分析结果统计
    """
    try:
        logger.info("开始执行选品策略分析任务")

        # 读取采集配置，获取需要分析的行业+平台
        configs_data = _load_collection_configs()
        if not configs_data:
            logger.warning("无启用的采集配置，跳过分析")
            return {"status": "skipped", "reason": "无启用配置"}

        # 执行 Agent 分析
        from src.ai.agents.selection_agent import run_selection_agent

        analysis_results = []
        for config in configs_data:
            industry = config["industry"]
            for platform in config["platforms"]:
                try:
                    logger.info(f"分析 {industry}/{platform}...")
                    result = run_selection_agent(industry, platform)

                    if result["success"]:
                        analysis_results.append({
                            "industry": industry,
                            "platform": platform,
                            "success": True,
                            "analysis": result["analysis"],
                        })
                        logger.info(f"{industry}/{platform} 分析完成")
                    else:
                        analysis_results.append({
                            "industry": industry,
                            "platform": platform,
                            "success": False,
                            "error": result["error"],
                        })
                        logger.warning(f"{industry}/{platform} 分析失败: {result['error']}")

                except Exception as e:
                    logger.error(f"分析 {industry}/{platform} 异常: {e}")
                    analysis_results.append({
                        "industry": industry,
                        "platform": platform,
                        "success": False,
                        "error": str(e),
                    })

        # 推送选品策略报告卡片
        success_count = sum(1 for r in analysis_results if r["success"])
        try:
            from src.feishu.application_bot import application_bot
            from src.feishu.feishu_bot import feishu_bot
            from src.feishu.card_templates import build_selection_strategy_card

            # 推送第一个成功的结果作为示例
            first_success = next(
                (r for r in analysis_results if r["success"]), None
            )
            if first_success:
                card = build_selection_strategy_card(
                    industry=first_success["industry"],
                    platform=first_success["platform"],
                    analysis=first_success["analysis"],
                )
                # 优先使用 Webhook 机器人，失败则回退到应用机器人
                pushed = False
                if feishu_bot.is_configured:
                    pushed = feishu_bot.send_card(card)
                if not pushed:
                    pushed = application_bot.send_card(card)
                if pushed:
                    logger.info("选品策略报告卡片已推送")

        except Exception as e:
            logger.error(f"推送选品策略报告失败: {e}")

        return {
            "status": "success",
            "total": len(analysis_results),
            "success_count": success_count,
        }

    except Exception as e:
        logger.error(f"分析任务失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def data_cleanup_task() -> dict[str, Any]:
    """数据清理任务：清理超过保留天数的数据。

    Returns:
        清理结果统计
    """
    try:
        logger.info("开始执行数据清理任务")

        retention_days = settings.data_retention_days
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cutoff_ms = int(cutoff_date.timestamp() * 1000)

        logger.info(f"清理 {cutoff_date.strftime('%Y-%m-%d')} 之前的数据（保留 {retention_days} 天）")

        # 清理选品池
        selection_table_id = settings.feishu_table_id_selection
        if selection_table_id:
            records = bitable_client.query_records(selection_table_id)
            deleted_count = 0
            for record in records:
                fields = record.get("fields", {})
                update_time = fields.get("更新时间")
                if isinstance(update_time, int) and update_time < cutoff_ms:
                    try:
                        bitable_client.delete_record(selection_table_id, record["record_id"])
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"删除记录失败: {e}")
            logger.info(f"选品池清理完成，删除 {deleted_count} 条")

        # 清理评论库
        review_table_id = settings.feishu_table_id_review
        if review_table_id:
            records = bitable_client.query_records(review_table_id)
            deleted_count = 0
            for record in records:
                fields = record.get("fields", {})
                review_time = fields.get("评论时间")
                if isinstance(review_time, int) and review_time < cutoff_ms:
                    try:
                        bitable_client.delete_record(review_table_id, record["record_id"])
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"删除评论记录失败: {e}")
            logger.info(f"评论库清理完成，删除 {deleted_count} 条")

        return {"status": "success", "cutoff_date": cutoff_date.strftime("%Y-%m-%d")}

    except Exception as e:
        logger.error(f"数据清理任务失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
