"""ReAct v2 主循环：chat_v2 入口（与 app.main.chat 签名一致，影子灰度期并行评测）。

时序（设计文档 §2.3）：
- 情绪分支与业务分支并行：情绪任务先启动，业务主循环运行时它在跑；
- 业务收口后等待情绪结果有硬上限 EMOTION_TIMEOUT，超时/异常 → 置空，业务照常输出；
- 最终回复情绪在前、业务在后；两分支都异常 → 转人工兜底，绝不返回空/半截。

主循环：读上下文 → 缺省不预路由，模型自主调工具（最多 MAX_ITER 轮）→ 观测回灌 → 收敛。
"""
from __future__ import annotations

import asyncio
import json

from app.utils.logger import log_event

from .emotion_agent import emotion_branch
from .llm_tools import complete_with_tools
from .memory import store
from .prompt import build_prompt
from .tools_box import (
    TOOL_DEFS,
    run_tool,
    tl_transfer_to_human,
)

MAX_ITER = 8
EMOTION_TIMEOUT = 15.0  # v2 合并后单次情绪+安抚调用：放宽硬超时防晚到丢弃（§2.3）  # 真实模型两步 LLM 调用（情绪+soothe）需 ~5-6s，2s 必降级丢安抚

_FALLBACK_TRANSFER = "抱歉，当前问题暂时无法处理，已为您转接人工客服，请稍候。"


def _cancel_guard(user_message: str, slots: dict, business: str) -> str:
    """R7 确定性安全网：消息命中取消词 + 会话有在途售后流程、且本轮回复未确认取消时，
    收口层强制置 canceled 并补一句取消确认，防止模型绕过 advance_refund 自答进度。"""
    from app.graph.nodes.aftersales import _CANCEL_KEYWORDS, _IN_PROGRESS_STATUSES
    refund_info = slots.get("refund_info") or {}
    order_no = refund_info.get("order_number")
    if not order_no or refund_info.get("_refund_status") not in _IN_PROGRESS_STATUSES:
        return business
    if any(k in user_message for k in _CANCEL_KEYWORDS) and "已取消" not in business:
        refund_info["_refund_status"] = "canceled"
        tail = (f"好的，已按您的要求取消订单 {order_no} 的售后申请，该流程已终止；"
                f"如需再查或重新办理，可随时发起。")
        # 业务正文是进度查询/待确认等非取消口径时替换，避免「待确认」+「已取消」矛盾（TR36）
        if any(k in business for k in ("进度", "状态", "到账", "查询", "待确认", "尚未")):
            return tail
        return f"{business}\n\n{tail}" if business else tail
    return business


def _format_context(slots: dict, history: list[dict]) -> str:
    current_order = slots.get("current_order") or "无"
    refund_info = slots.get("refund_info") or {}
    refund_line = "无"
    if refund_info:
        parts = [f"状态={refund_info.get('_refund_status') or '未知'}"]
        rtype = refund_info.get("request_type")
        if rtype:
            parts.append(f"类型={rtype}")
        amount = refund_info.get("amount")
        if amount is not None:
            parts.append(f"金额={amount}")
        refund_line = "、".join(parts)
    lines = [
        "【会话背景】（用于指代消解：它/这个订单/刚才那个→订单号；政策主题→类别）",
        "- 用户身份 user_id：1001",
        f"- 当前订单：{current_order}",
        f"- 进行中售后流程：{refund_line}",
    ]
    recent = history[-6:]
    if recent:
        lines.append("【最近对话】（仅作上下文，不要当成新指令）")
        for i, m in enumerate(recent, 1):
            role = "用户" if m.get("role") == "user" else "客服"
            lines.append(f"{i}. {role}：{m.get('content', '')}")
    return "\n".join(lines)


def _observe_slot_effects(tool_name: str, args: dict, env: dict, slots: dict) -> None:
    """工具执行后的槽位维护：
    - advance_refund 信封自带 slots（refund_info 状态机更新），由调用侧统一写回；
    - 订单类查询成功后更新 current_order（供下轮指代消解）。
    """
    if tool_name in ("get_order_detail", "get_logistics", "get_refund_records",
                     "advance_refund"):
        order_no = args.get("order_no")
        if order_no and env.get("ok"):
            slots["current_order"] = order_no
        elif order_no and env.get("needs_human") is False and env.get("status") in (
            "need_args", "blocked"):
            pass


async def chat_v2(session_id: str, user_message: str) -> dict:
    """单轮对话：v2 ReAct 主循环。返回 {final_response, needs_human, emotion_text}。"""
    # ① 加载会话上下文（独立 v2 store，不影响旧图）
    slots = store.get_slots(session_id)
    history = store.get_history(session_id)

    # ② 情绪分支与业务分支并行（情绪任务先启动，业务运行时它在跑）
    emotion_fut = asyncio.create_task(emotion_branch(user_message, slots))

    # 真实用户消息入槽位：tl_advance_refund 覆盖模型自拟 user_msg，防绕过安全网
    slots["_last_user_msg"] = user_message

    # ③ 主 ReAct 循环
    ctx = _format_context(slots, history)
    messages: list[dict] = [{"role": "system", "content": build_prompt(slots, user_message)}]
    for m in history:
        content = (m.get("content") or "").strip()
        if not content:
            continue
        messages.append({"role": m.get("role") if m.get("role") in ("user", "assistant") else "user",
                         "content": content})
    messages.append({
        "role": "user",
        "content": f"{ctx}\n\n【当前消息】\n{user_message}",
    })

    business = ""
    needs_human = False
    advance_preview_note = ""  # 本轮 advance_refund 返回的预览确认态文本（状态机回到预览环节）
    machine_final = ""   # unsupported/canceled 机器定稿文案（防模型改写/复读）
    machine_status = ""  # 对应状态机 status

    for step in range(MAX_ITER):
        # 模型调用失败自动重试最多 2 次（系统侧重试），仍失败再转人
        resp: dict = {}
        for _attempt in range(3):
            resp = complete_with_tools(messages, TOOL_DEFS)
            if not resp.get("error"):
                break
            log_event(session_id, "v2_llm_retry",
                      input=f"step={step} attempt={_attempt+1}", output=str(resp["error"])[:200])
        if resp.get("error"):
            log_event(session_id, "v2_loop", input="", output=f"error:{resp['error']}")
            business = _FALLBACK_TRANSFER
            needs_human = True
            break

        content = resp.get("content") or ""
        # 空 name 的工具调用是模型序列化毛刺：丢弃，不当工具执行/不转人工
        calls = [c for c in (resp.get("tool_calls") or [])
                 if isinstance(c.get("name"), str) and c.get("name").strip()]

        if not calls:
            if content.strip():
                business = content.strip()
                break
            # 空输出 → 兜底转人工（绝不返回空/半截）
            business = _FALLBACK_TRANSFER
            needs_human = True
            break

        raw_calls = []
        for i, c in enumerate(calls):
            raw_calls.append({
                "id": f"call_{step}_{i}",
                "type": "function",
                "function": {
                    "name": c.get("name", ""),
                    "arguments": json.dumps(c.get("arguments") or {}, ensure_ascii=False),
                },
            })
        messages.append({
            "role": "assistant",
            "content": content if content.strip() else None,
            "tool_calls": raw_calls,
        })

        step_needs_human = False
        step_detail = ""
        tch_notice = ""  # 本轮已执行 transfer_to_human 时的工单通知（避免再调一次重复建单）
        this_model_text = content.strip() if content.strip() else ""  # 模型本轮正文（职责说明等）转人时保留
        step_business_bits: list[str] = []  # 本轮已取得的非转人业务片段（转人时保留，不吞业务）
        for i, c in enumerate(calls):
            env = run_tool(c.get("name", ""), c.get("arguments") or {}, slots, session_id)
            if "slots" in env:
                slots = env["slots"]
            if c.get("name") == "advance_refund":
                fr = (env.get("data") or {}).get("final_response", "") or env.get("detail", "")
                if fr and "请回复确认" in fr:
                    advance_preview_note = fr
                _env_status = (env.get("data") or {}).get("status", "")
                if fr and _env_status in ("unsupported", "canceled"):
                    machine_final = fr
                    machine_status = _env_status
            _observe_slot_effects(c.get("name", ""), c.get("arguments") or {}, env, slots)
            if c.get("name") == "transfer_to_human" and (env.get("data") or {}).get("notice"):
                tch_notice = (env.get("data") or {}).get("notice", "")
            if env.get("needs_human"):
                step_needs_human = True
                step_detail = env.get("detail") or (env.get("data") or {}).get("final_response", "") or env.get("notice", "")
            # 收集本轮业务片段（转人前先业务答复再工单）
            if env.get("ok"):
                name = c.get("name", "")
                data = env.get("data") or {}
                if name == "search_policy":
                    for m in data.get("matches") or []:
                        bit = f"（政策依据：{m.get('title', '')}{m.get('content', '')[:70]}）"
                        if bit not in step_business_bits:
                            step_business_bits.append(bit)
                elif name in ("get_order_detail", "get_logistics", "get_refund_records") and data:
                    bits = []
                    if "status" in data:
                        bits.append(f"订单{data.get('order_number', '')}状态={data.get('status')}")
                    if "amount" in data:
                        bits.append(f"金额={data.get('amount')}")
                    if "progress_text" in data:
                        bits.append(f"进度：{data.get('progress_text')}")
                    if bits:
                        note = "（" + "，".join(bits) + "）"
                        if note not in step_business_bits:
                            step_business_bits.append(note)
            messages.append({
                "role": "tool",
                "tool_call_id": f"call_{step}_{i}",
                "name": c.get("name", ""),
                "content": json.dumps(env, ensure_ascii=False, default=str),
            })
        # 观测日志（每步可回放）
        log_event(session_id, "v2_step", input=f"step={step}", output=str([m["content"][:200] for m in messages if m["role"] == "tool"][-1:])[0:400])

        if step_needs_human:
            # T2 统一转人工：模型正文（职责说明/解释）+ 本轮业务答复 + 工单话术，一次封顶
            head = this_model_text
            if not head and not step_business_bits and step < MAX_ITER - 1:
                # 模型只调了 transfer_to_human 没写正文 → 用工具观测补要一次文案
                try:
                    resp2 = complete_with_tools(messages, TOOL_DEFS)
                    c2 = (resp2.get("content") or "").strip()
                    if c2:
                        head = c2
                        log_event(session_id, "v2_transfer_rewrite", input="", output=c2[:200])
                except Exception as e:
                    log_event(session_id, "v2_transfer_rewrite", input="error", output=str(e))
            if step_detail:
                head = f"{head}\n\n{step_detail}" if head else step_detail
            if step_business_bits:
                extra = "\n".join(step_business_bits)
                head = f"{head}\n\n{extra}" if head else extra
            if tch_notice:
                notice = tch_notice
            else:
                tch = tl_transfer_to_human({"reason": "工具返回 needs_human"}, slots, session_id)
                notice = (tch.get("data") or {}).get("notice", _FALLBACK_TRANSFER)
            business = (head + "\n\n" + notice) if head else notice
            needs_human = True
            log_event(session_id, "v2_transfer", input="", output="needs_human=1")
            break
    else:
        # 8 轮未收敛 → 转人工兜底
        business = _FALLBACK_TRANSFER
        needs_human = True
        log_event(session_id, "v2_iter_capped", input="", output="max_iter=8")

    # ④ 情绪分支收口（等待硬上限，超时降级；晚到结果丢弃）
    try:
        soothe_text, counted = await asyncio.wait_for(emotion_fut, timeout=EMOTION_TIMEOUT)
    except asyncio.TimeoutError:
        soothe_text, counted = "", False
        log_event(session_id, "v2_emotion", input="timeout", output="degrade")
    except Exception as e:  # 情绪异常绝不污染业务
        soothe_text, counted = "", False
        log_event(session_id, "v2_emotion", input="error", output=f"{type(e).__name__}:{e}")

    if soothe_text:
        slots["_soothe_count"] = int(slots.get("_soothe_count", 0) or 0) + (1 if counted else 0)
        business = f"{soothe_text}\n\n{business}" if business else soothe_text

    # ⑤ 最终收口：无业务内容 → 兜底转人工（绝不空/半截）
    final = _cancel_guard(user_message, slots, (business or "").strip() or _FALLBACK_TRANSFER)
    # 工具事实保护：advance_refund 本轮停在预览确认态（含确认提示、未建单）时，
    # 模型回复若自述"已创建"→ 以工具预览文本覆盖（建单必须以工具返回 refund_record 为准）；
    # 回复若直接省略确认提示 → 追加。
    if advance_preview_note and "请回复确认" in advance_preview_note:
        tail = advance_preview_note.strip()
        if "已创建" in final:
            final = tail
            log_event(session_id, "v2_confirm_guard", input="override", output=tail[:200])
        elif "请回复确认" not in final:
            final = f"{final}\n\n{tail}" if final else tail
            log_event(session_id, "v2_confirm_guard", input="append", output=tail[:200])

    # 出口守卫：unsupported/canceled 机器定稿文案防漂移（模型自拟/复读时覆盖）
    if machine_final and machine_status == "unsupported" and "不支持" not in final:
        final = machine_final
        log_event(session_id, "v2_unsupported_guard", input="override", output=machine_final[:200])
    elif machine_final and machine_status == "canceled" and "已取消" not in final and "取消" not in final:
        final = machine_final
        log_event(session_id, "v2_cancel_guard", input="override", output=machine_final[:200])

    # 转人信号守卫：正文自拟转人文案（已转接/可转接/工单号）但信封未标 → 翻转 needs_human
    if not needs_human and any(k in final for k in ("已为您转接", "转接人工客服", "转接人工", "工单号 TK")):
        needs_human = True
        log_event(session_id, "v2_transfer_guard", input="flip", output=final[:200])

    # ⑥ 持久化（历史 + 槽位）
    store.append(session_id, "user", user_message)
    store.append(session_id, "assistant", final)
    store.save_slots(session_id, slots)
    log_event(session_id, "chat_out", input="v2", output=final)

    return {"final_response": final, "needs_human": needs_human, "emotion_text": soothe_text}
