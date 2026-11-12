/** ServeOn API 客户端：REST 聊天 + 会话管理。 */

const BASE = "";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  response: string;
  routed_agents?: string[];
  thread_id: string;
}

/** 发送聊天消息：POST /v1/chat。 */
export async function sendChat(
  message: string,
  threadId: string,
): Promise<ChatResponse> {
  const resp = await fetch(`${BASE}/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, thread_id: threadId }),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || `HTTP ${resp.status}`);
  }

  return resp.json();
}

/** 重置会话：POST /v1/reset。 */
export async function resetSession(): Promise<void> {
  await fetch(`${BASE}/v1/reset`, { method: "POST" });
}

/** 推送到飞书 GUI：GET http://localhost:8001/api/gui */
export async function pushToFeishu(): Promise<{ status: string; message: string }> {
  const resp = await fetch("http://localhost:8001/api/gui");
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}`);
  }
  return resp.json();
}
