"""API 主入口：FastAPI 应用。"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.router import router

app = FastAPI(
    title="跨境电商选品策略平台 API",
    description="选品策略平台接口：配置、任务、看板、健康检查",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root() -> dict:
    """根路径。"""
    return {"status": "success", "message": "跨境电商选品策略平台 API"}
