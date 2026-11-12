"""主入口（v2）：chat() 走 chat_v2；v1 主图实现备份为 chat_v1（需 workflow，v2 副本已剔除，
仅保留函数体供回退参考——lazy import 使 import app.main 不崩，调用 chat_v1 才触发缺模块）。

启动：python -m app.main（CLI，交互）
"""
from __future__ import annotations

import asyncio
import time

from app.react_v2 import chat_v2
from app.utils.logger import log_event, round_banner, round_footer, set_session


async def chat(session_id: str, user_message: str) -> dict:
    """单轮对话（v2）：调用 chat_v2，返回 {final_response, needs_human, emotion_text}。"""
    round_banner(session_id, f"提问：{user_message}")
    set_session(session_id)
    log_event(session_id, "chat_in", input=user_message)
    t0 = time.perf_counter()
    result = await chat_v2(session_id, user_message)
    elapsed = f"{round((time.perf_counter() - t0) * 1000)}"
    log_event(session_id, "chat_out", input="v2",
              output=result.get("final_response", ""), elapsed=elapsed)
    round_footer(session_id, f"耗时={elapsed}ms needs_human={result.get('needs_human')}")
    return result


async def chat_v1(session_id: str, user_message: str) -> dict:  # pragma: no cover - v1 备份（v2 副本无 workflow）
    """v1 主图实现备份。仅参考：调用会在 import workflow 处抛 ModuleNotFoundError。"""
    from app.graph.workflow import main_graph  # lazy：import app.main 不崩
    round_banner(session_id, f"提问：{user_message}")
    set_session(session_id)
    log_event(session_id, "chat_in", input=user_message)
    t0 = time.perf_counter()
    state = {"user_message": user_message, "session_id": session_id}
    result = await main_graph.ainvoke(state)
    final = result.get("final_response", "")
    elapsed = f"{round((time.perf_counter() - t0) * 1000)}"
    log_event(session_id, "chat_out",
              input=f"routed={result.get('routed_agents', [])}", output=final, elapsed=elapsed)
    round_footer(session_id, f"耗时={elapsed}ms 路由={result.get('routed_agents', [])}")
    return result


async def cli() -> None:
    session_id = f"cli-{int(time.time())}"
    print("电商智能客服（v2 ReAct）已启动，输入「退出」结束。")
    while True:
        try:
            msg = input("你: ").strip()
        except EOFError:
            break
        if not msg:
            continue
        if msg.lower() in ("退出", "exit", "quit"):
            print("再见。")
            break
        result = await chat(session_id, msg)
        print(f"AI: {result.get('final_response', '')}")


def main() -> None:
    asyncio.run(cli())


if __name__ == "__main__":
    main()
