"use client";

import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { HouseholdProfile } from "@/types/recommendations";
import { sendAssistantQuery } from "./assistant-api";
import { AssistantMessage, MessageBubble } from "./message-bubble";
import { QuickPrompts } from "./quick-prompts";

// ─── Types ───────────────────────────────────────────────────────────────────

interface ChatAssistantProps {
  lat: number;
  lon: number;
  currentAqi?: number | null;
  profile?: HouseholdProfile;
  className?: string;
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function ChatAssistant({
  lat,
  lon,
  currentAqi,
  profile,
  className = "",
}: ChatAssistantProps) {
  const [messages, setMessages] = useState<AssistantMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "👋 Hi! I'm BreatheWise — your evidence-based air quality assistant.\n\n" +
        "My responses are grounded in real-time sensor telemetry from verified monitoring stations. " +
        "I never fabricate AQI readings or health statistics.\n\n" +
        "Ask me about outdoor safety, commute options, indoor air quality, or your household's specific needs.",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(query: string) {
    const trimmed = query.trim();
    if (!trimmed || loading) return;

    const userMsg: AssistantMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmed,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const history = messages
        .filter((m) => m.id !== "welcome")
        .slice(-4)
        .map((m) => ({ role: m.role, content: m.content }));
      const data = await sendAssistantQuery(trimmed, lat, lon, profile, history);
      const assistantMsg: AssistantMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: data.answer,
        aqi: data.referenced_aqi,
        riskLevel: data.risk_level,
        actions: data.approved_actions,
        rationale: data.scientific_rationale,
        llmGrounded: data.llm_grounded,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to reach BreatheWise assistant.";
      setError(msg);
    } finally {
      setLoading(false);
      // Return focus to input
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend(input);
    }
  }

  return (
    <section
      aria-label="BreatheWise AI Assistant"
      className={`flex flex-col h-full ${className}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
        <div>
          <h2 className="text-base font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <span aria-hidden="true">🌬️</span>
            BreatheWise Assistant
          </h2>
          {currentAqi != null && (
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Grounded on live AQI: <strong>{currentAqi}</strong>
            </p>
          )}
        </div>
        <Badge variant="neutral" className="text-xs text-green-700 border-green-300">
          Evidence-Based
        </Badge>
      </div>

      {/* Quick prompts */}
      <QuickPrompts loading={loading} onSend={handleSend} />

      {/* Messages area */}
      <div
        className="flex-1 overflow-y-auto px-4 py-3 space-y-1 bg-gray-50 dark:bg-gray-950"
        role="list"
        aria-label="Conversation history"
        aria-live="polite"
        aria-atomic="false"
      >
        {messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}

        {/* Loading indicator */}
        {loading && (
          <div
            className="flex justify-start mb-3"
            role="status"
            aria-label="BreatheWise is thinking"
          >
            <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-2">
              <div className="flex gap-1" aria-hidden="true">
                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
              <span className="text-xs text-gray-500 dark:text-gray-400">Fetching real-time data…</span>
            </div>
          </div>
        )}

        {/* Error message */}
        {error && (
          <div
            role="alert"
            className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3"
          >
            ⚠️ {error}
          </div>
        )}

        <div ref={bottomRef} aria-hidden="true" />
      </div>

      {/* Input area */}
      <div className="px-3 py-3 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
        <div className="flex gap-2 items-end">
          <label htmlFor="chat-input" className="sr-only">
            Ask BreatheWise a question about air quality
          </label>
          <textarea
            id="chat-input"
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about outdoor safety, indoor air, commute options…"
            rows={2}
            maxLength={500}
            disabled={loading}
            className="flex-1 resize-none rounded-xl border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 px-3 py-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:border-blue-500 disabled:opacity-50 transition"
            aria-describedby="chat-input-hint"
          />
          <Button
            onClick={() => handleSend(input)}
            disabled={loading || !input.trim()}
            className="self-end"
            aria-label="Send message"
          >
            {loading ? (
              <span aria-hidden="true">⏳</span>
            ) : (
              <span aria-hidden="true">↑</span>
            )}
          </Button>
        </div>
        <p id="chat-input-hint" className="text-xs text-gray-400 dark:text-gray-500 mt-1 px-1">
          Press Enter to send · Shift+Enter for new line · Max 500 chars
        </p>
        <p className="text-xs text-gray-400 dark:text-gray-500 px-1 mt-0.5">
          ⚕️ BreatheWise provides environmental guidance only — not medical advice.
        </p>
      </div>
    </section>
  );
}
