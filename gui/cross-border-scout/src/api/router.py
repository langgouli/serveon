"""API 路由：配置、任务、看板、健康检查。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.config import settings, reload_settings
from src.gui.services.env_service import EnvService

router = APIRouter(prefix="/api", tags=["api"])


# ============ 配置接口 ============

class ConfigUpdate(BaseModel):
    """配置更新请求。"""

    feishu_app_id: str | None = None
    feishu_app_secret: str | None = None
    feishu_bitable_app_token: str | None = None
    feishu_tenant_domain: str | None = None
    feishu_table_id_collection_config: str | None = None
    feishu_table_id_selection: str | None = None
    feishu_table_id_review: str | None = None
    feishu_table_id_report: str | None = None
    openai_api_key: str | None = None
    openai_api_base: str | None = None
    anthropic_api_key: str | None = None


@router.get("/config")
async def get_config() -> dict:
    """读取当前配置。"""
    return {
        "feishu_app_id": settings.feishu_app_id,
        "feishu_app_secret": settings.feishu_app_secret,
        "feishu_bitable_app_token": settings.feishu_bitable_app_token,
        "feishu_tenant_domain": settings.feishu_tenant_domain,
        "feishu_table_id_collection_config": settings.feishu_table_id_collection_config,
        "feishu_table_id_selection": settings.feishu_table_id_selection,
        "feishu_table_id_review": settings.feishu_table_id_review,
        "feishu_table_id_report": settings.feishu_table_id_report,
        "openai_api_key": settings.openai_api_key,
        "openai_api_base": settings.openai_api_base,
        "anthropic_api_key": settings.anthropic_api_key,
    }


@router.put("/config")
async def update_config(config: ConfigUpdate) -> dict:
    """更新配置。"""
    env_data = {}
    for field, value in config.model_dump().items():
        if value is not None:
            env_data[field.upper()] = value

    if not env_data:
        raise HTTPException(status_code=400, detail="无配置项需要更新")

    try:
        EnvService.save_env(env_data)
        reload_settings()
        return {"status": "success", "message": "配置已保存并生效"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ 任务接口 ============

@router.post("/tasks/collect")
async def run_collection() -> dict:
    """触发选品数据采集。"""
    from src.scheduler.tasks import product_collection_task

    try:
        result = product_collection_task()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/analyze")
async def run_analysis() -> dict:
    """触发选品策略分析。"""
    from src.scheduler.tasks import selection_analysis_task

    try:
        result = selection_analysis_task()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/cleanup")
async def run_cleanup() -> dict:
    """触发数据清理。"""
    from src.scheduler.tasks import data_cleanup_task

    try:
        result = data_cleanup_task()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ 数据看板接口 ============

@router.get("/stats")
async def get_stats() -> dict:
    """获取数据统计。"""
    from src.feishu.bitable import bitable_client

    try:
        selection_count = 0
        if settings.feishu_table_id_selection:
            records = bitable_client.query_records(settings.feishu_table_id_selection)
            selection_count = len(records)

        review_count = 0
        if settings.feishu_table_id_review:
            records = bitable_client.query_records(settings.feishu_table_id_review)
            review_count = len(records)

        report_count = 0
        if settings.feishu_table_id_report:
            records = bitable_client.query_records(settings.feishu_table_id_report)
            report_count = len(records)

        return {
            "selection_count": selection_count,
            "review_count": review_count,
            "report_count": report_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查接口 ============

@router.get("/health")
async def health_check() -> dict:
    """健康检查。"""
    # 检查飞书凭证
    feishu_cred = bool(settings.feishu_app_id and settings.feishu_app_secret)

    # 检查 AI 模型凭证
    has_ai = (
        bool(settings.openai_api_key and settings.openai_api_key != "sk-xxxxxxxx")
    ) or bool(settings.anthropic_api_key and settings.anthropic_api_key != "sk-ant-xxxxxxxx")

    # 检查表 ID 配置
    tables = [
        ("采集配置", settings.feishu_table_id_collection_config),
        ("选品池", settings.feishu_table_id_selection),
        ("评论库", settings.feishu_table_id_review),
        ("分析报告", settings.feishu_table_id_report),
    ]
    configured = sum(1 for _, tid in tables if tid)

    # 检查飞书连通性
    feishu_conn = False
    if settings.feishu_app_id and settings.feishu_table_id_selection:
        try:
            from src.feishu.bitable import bitable_client
            bitable_client.query_records(settings.feishu_table_id_selection, page_size=1)
            feishu_conn = True
        except Exception:
            pass

    return {
        "feishu_cred": feishu_cred,
        "ai_cred": has_ai,
        "table_id_configured": configured,
        "table_id_total": len(tables),
        "feishu_conn": feishu_conn,
    }


# ============ GUI 接口 ============

_gui_process = None


@router.get("/gui")
async def open_gui() -> dict:
    """启动 GUI 界面。"""
    import subprocess
    import sys
    from pathlib import Path

    global _gui_process

    if _gui_process and _gui_process.poll() is None:
        return {"status": "success", "message": "GUI已在运行"}

    # 项目根目录：src/api/router.py -> parents[2]
    project_root = Path(__file__).resolve().parents[2]

    try:
        _gui_process = subprocess.Popen(
            [sys.executable, "-m", "src.gui.main"],
            cwd=str(project_root),
        )
        return {"status": "success", "message": "GUI已启动"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
