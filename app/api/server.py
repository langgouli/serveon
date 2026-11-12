"""FastAPI 服务（v2）：chat_v2 封装为 HTTP。
启动：uvicorn app.api.server:app --port 8766
（v1 副本端口 8765 走 v1 主图；web 前端代理端口需对应。）
"""
from __future__ import annotations

import os

os.environ.setdefault("LLM_PROVIDER", "ark")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.react_v2 import chat_v2
from app.react_v2.memory import store

app = FastAPI(title="电商智能客服 API（v2 ReAct）", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    thread_id: str


class ChatResponse(BaseModel):
    response: str
    thread_id: str
    needs_human: bool = False
    emotion_text: str = ""
    routed_agents: list[str] = []  # 兼容 v1 前端外壳字段（v2 无路由信息，恒为空）


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/chat", response_model=ChatResponse)
async def chat_api(req: ChatRequest) -> ChatResponse:
    result = await chat_v2(req.thread_id, req.message)
    return ChatResponse(
        response=result.get("final_response", ""),
        thread_id=req.thread_id,
        needs_human=bool(result.get("needs_human", False)),
        emotion_text=result.get("emotion_text", ""),
    )


@app.post("/v1/reset")
async def reset_api() -> dict:
    store.reset()
    return {"status": "ok"}
