import { useState, useRef, useCallback, useEffect } from "react";
import { sendChat, resetSession, pushToFeishu, type ChatMessage } from "../api/client";

interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string;
  routedAgents: string[];
  threadId: string;
}

const AVATAR_USER = "👤";
const AVATAR_BOT = "🤖";

export default function ChatPage() {
  const [state, setState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    error: "",
    routedAgents: [],
    threadId: `sf_${Date.now()}`,
  });
  const [input, setInput] = useState("");
  const [pushingFeishu, setPushingFeishu] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [state.messages, state.isLoading, scrollToBottom]);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || state.isLoading) return;
    setInput("");
    setState((prev) => ({
      ...prev,
      isLoading: true,
      error: "",
      routedAgents: [],
      messages: [...prev.messages, { role: "user", content: text }],
    }));

    try {
      const result = await sendChat(text, state.threadId);
      setState((prev) => ({
        ...prev,
        isLoading: false,
        routedAgents: Array.isArray(result.routed_agents) ? result.routed_agents : [],
        messages: [
          ...prev.messages,
          { role: "assistant", content: result.response },
        ],
      }));
    } catch (err) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: String(err),
      }));
    }
  }, [input, state.isLoading, state.threadId]);

  const handleReset = useCallback(async () => {
    try {
      await resetSession();
      setState((prev) => ({
        ...prev,
        threadId: `sf_${Date.now()}`,
        messages: [],
        routedAgents: [],
        error: "",
      }));
    } catch (err) {
      setState((prev) => ({ ...prev, error: String(err) }));
    }
  }, []);

  const handlePushFeishu = useCallback(async () => {
    setPushingFeishu(true);
    try {
      const result = await pushToFeishu();
      setState((prev) => ({
        ...prev,
        messages: [
          ...prev.messages,
          { role: "assistant", content: `飞书推送：${result.message}` },
        ],
      }));
    } catch (err) {
      setState((prev) => ({ ...prev, error: String(err) }));
    } finally {
      setPushingFeishu(false);
    }
  }, []);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        maxWidth: 820,
        margin: "0 auto",
        fontFamily:
          "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        background: "linear-gradient(135deg, #1a2138 0%, #1e293b 50%, #231a3f 100%)",
      }}
    >
      {/* 顶部栏 */}
      <div
        style={{
          padding: "14px 20px",
          borderBottom: "1px solid rgba(99, 102, 241, 0.2)",
          backdropFilter: "blur(20px)",
          background: "rgba(30, 41, 59, 0.7)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: "linear-gradient(135deg, #6366f1, #a855f7)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 16,
              boxShadow: "0 0 20px rgba(99, 102, 241, 0.4)",
            }}
          >
            🤖
          </div>
          <span
            style={{
              fontWeight: 700,
              fontSize: 16,
              background: "linear-gradient(90deg, #818cf8, #c084fc)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            ServeOn 售后客服
          </span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => window.open("/eval.html", "_blank")}
            style={{
              padding: "6px 14px",
              borderRadius: 8,
              border: "1px solid rgba(78, 205, 196, 0.4)",
              background: "rgba(78, 205, 196, 0.15)",
              color: "#6ee7e0",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 500,
              transition: "all 0.2s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "rgba(78, 205, 196, 0.3)";
              e.currentTarget.style.boxShadow = "0 0 12px rgba(78, 205, 196, 0.3)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "rgba(78, 205, 196, 0.15)";
              e.currentTarget.style.boxShadow = "none";
            }}
          >
            🧪 系统评测
          </button>
          <button
            onClick={handlePushFeishu}
            disabled={pushingFeishu}
            style={{
              padding: "6px 14px",
              borderRadius: 8,
              border: "1px solid rgba(99, 102, 241, 0.4)",
              background: "rgba(99, 102, 241, 0.15)",
              color: "#a5b4fc",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 500,
              transition: "all 0.2s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "rgba(99, 102, 241, 0.3)";
              e.currentTarget.style.boxShadow = "0 0 12px rgba(99, 102, 241, 0.3)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "rgba(99, 102, 241, 0.15)";
              e.currentTarget.style.boxShadow = "none";
            }}
          >
            {pushingFeishu ? "..." : "📨 飞书推送"}
          </button>
          <button
            onClick={handleReset}
            style={{
              padding: "6px 14px",
              borderRadius: 8,
              border: "1px solid rgba(139, 92, 246, 0.4)",
              background: "rgba(139, 92, 246, 0.15)",
              color: "#c4b5fd",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 500,
              transition: "all 0.2s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "rgba(139, 92, 246, 0.3)";
              e.currentTarget.style.boxShadow = "0 0 12px rgba(139, 92, 246, 0.3)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "rgba(139, 92, 246, 0.15)";
              e.currentTarget.style.boxShadow = "none";
            }}
          >
            ↻ 重置会话
          </button>
        </div>
      </div>

      {/* 消息区 */}
      <div
        ref={scrollRef}
        style={{ flex: 1, overflowY: "auto", padding: 20 }}
      >
        {state.messages.length === 0 && !state.isLoading && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              height: "60%",
              color: "#6b7280",
              textAlign: "center",
              gap: 12,
            }}
          >
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: 16,
                background: "linear-gradient(135deg, #6366f1, #a855f7)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 28,
                boxShadow: "0 0 40px rgba(99, 102, 241, 0.3)",
                animation: "pulse 2s ease-in-out infinite",
              }}
            >
              🤖
            </div>
            <div style={{ fontSize: 15, color: "#94a3b8" }}>
              我是 ServeOn 售后助手
              <br />
              可以查询售后政策、订单物流，协助退货退款
            </div>
          </div>
        )}

        {state.messages.map((msg, i) => (
          <div
            key={i}
            style={{
              marginBottom: 16,
              display: "flex",
              justifyContent:
                msg.role === "user" ? "flex-end" : "flex-start",
              gap: 10,
            }}
          >
            {msg.role === "assistant" && (
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 8,
                  background: "linear-gradient(135deg, #6366f1, #a855f7)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 16,
                  flexShrink: 0,
                }}
              >
                {AVATAR_BOT}
              </div>
            )}
            <div
              style={{
                display: "inline-block",
                padding: "10px 16px",
                borderRadius: 12,
                maxWidth: "75%",
                background:
                  msg.role === "user"
                    ? "linear-gradient(135deg, #4f46e5, #7c3aed)"
                    : "rgba(51, 65, 85, 0.7)",
                color: msg.role === "user" ? "#fff" : "#e2e8f0",
                whiteSpace: "pre-wrap",
                lineHeight: 1.6,
                fontSize: 14,
                border:
                  msg.role === "assistant"
                    ? "1px solid rgba(99, 102, 241, 0.2)"
                    : "none",
                boxShadow:
                  msg.role === "user"
                    ? "0 4px 20px rgba(99, 102, 241, 0.3)"
                    : "none",
              }}
            >
              {msg.content}
            </div>
            {msg.role === "user" && (
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 8,
                  background: "rgba(55, 65, 81, 0.8)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 16,
                  flexShrink: 0,
                }}
              >
                {AVATAR_USER}
              </div>
            )}
          </div>
        ))}

        {state.isLoading && (
          <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: "linear-gradient(135deg, #6366f1, #a855f7)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 16,
                flexShrink: 0,
              }}
            >
              {AVATAR_BOT}
            </div>
            <div
              style={{
                padding: "12px 16px",
                borderRadius: 12,
                background: "rgba(51, 65, 85, 0.7)",
                border: "1px solid rgba(99, 102, 241, 0.2)",
              }}
            >
              <div style={{ display: "flex", gap: 4 }}>
                <span style={{ color: "#6366f1", animation: "bounce 1s infinite" }}>●</span>
                <span style={{ color: "#8b5cf6", animation: "bounce 1s infinite 0.2s" }}>●</span>
                <span style={{ color: "#a855f7", animation: "bounce 1s infinite 0.4s" }}>●</span>
              </div>
            </div>
          </div>
        )}

        {state.routedAgents && state.routedAgents.length > 0 && (
          <div
            style={{
              fontSize: 12,
              color: "#6366f1",
              marginTop: 8,
              paddingLeft: 44,
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span style={{ opacity: 0.7 }}>路由 Agent:</span>
            {state.routedAgents.map((agent, i) => (
              <span
                key={i}
                style={{
                  padding: "2px 8px",
                  borderRadius: 4,
                  background: "rgba(99, 102, 241, 0.2)",
                  border: "1px solid rgba(99, 102, 241, 0.3)",
                }}
              >
                {agent}
              </span>
            ))}
          </div>
        )}

        {state.error && (
          <div
            style={{
              color: "#fca5a5",
              fontSize: 13,
              marginTop: 8,
              padding: "8px 12px",
              borderRadius: 8,
              background: "rgba(239, 68, 68, 0.1)",
              border: "1px solid rgba(239, 68, 68, 0.2)",
            }}
          >
            ⚠️ {state.error}
          </div>
        )}
      </div>

      {/* 输入区 */}
      <div
        style={{
          padding: 16,
          borderTop: "1px solid rgba(99, 102, 241, 0.2)",
          backdropFilter: "blur(20px)",
          background: "rgba(30, 41, 59, 0.7)",
        }}
      >
        <div style={{ display: "flex", gap: 10 }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            placeholder="输入售后问题..."
            style={{
              flex: 1,
              padding: "10px 16px",
              borderRadius: 10,
              border: "1px solid rgba(99, 102, 241, 0.3)",
              background: "rgba(51, 65, 85, 0.6)",
              color: "#e2e8f0",
              fontSize: 14,
              outline: "none",
              transition: "border-color 0.2s",
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "rgba(99, 102, 241, 0.6)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "rgba(99, 102, 241, 0.3)";
            }}
            disabled={state.isLoading}
          />
          <button
            onClick={sendMessage}
            disabled={state.isLoading}
            style={{
              padding: "10px 20px",
              borderRadius: 10,
              background: "linear-gradient(135deg, #4f46e5, #7c3aed)",
              color: "#fff",
              cursor: "pointer",
              fontSize: 14,
              fontWeight: 600,
              border: "none",
              boxShadow: "0 4px 16px rgba(99, 102, 241, 0.4)",
              transition: "all 0.2s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.boxShadow = "0 6px 24px rgba(99, 102, 241, 0.6)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.boxShadow = "0 4px 16px rgba(99, 102, 241, 0.4)";
            }}
          >
            {state.isLoading ? "..." : "发送"}
          </button>
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.7; transform: scale(1.05); }
        }
        @keyframes bounce {
          0%, 100% { transform: translateY(0); opacity: 0.4; }
          50% { transform: translateY(-4px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
