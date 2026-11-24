"use client";

import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

// ─── Types ───────────────────────────────────────────────────────────────────

interface AssistantMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  aqi?: number | null;
  riskLevel?: string;
  actions?: string[];
  rationale?: string;
  llmGrounded?: boolean;
  timestamp: Date;
}

interface HouseholdProfile {
  has_children?: boolean;
  has_elderly?: boolean;
  has_respiratory_sensitivity?: boolean;
  has_cardiac_condition?: boolean;
}

interface ChatAssistantProps {
  lat: number;
  lon: number;
  currentAqi?: number | null;
  profile?: HouseholdProfile;
  className?: string;
}

// ─── Quick prompt chips ───────────────────────────────────────────────────────

const QUICK_PROMPTS = [
  { label: "🏃 Can I exercise outside?", query: "Is it safe to go jogging or exercise outdoors today?" },
  { label: "👶 Kids safe outdoors?", query: "Is it safe for my children to play outside or go to school?" },
  { label: "🌿 Do plants help?", query: "Can houseplants improve my indoor air quality?" },
  { label: "🚇 Best commute option?", query: "What is the safest way to commute today?" },
  { label: "😷 When to wear a mask?", query: "Should I wear an N95 mask today?" },
  { label: "🏠 Indoor air tips?", query: "How can I improve my indoor air quality right now?" },
];

// ─── API Helper ───────────────────────────────────────────────────────────────

async function sendAssistantQuery(
  query: string,
  lat: number,
  lon: number,
  profile?: HouseholdProfile
) {
  const res = await fetch("/api/assistant/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, lat, lon, profile: profile ?? {} }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

// ─── Risk badge colour (non-colour-only: text label always present) ───────────

function RiskBadge({ level }: { level: string }) {
  const map: Record<string, string> = {
    low: "bg-green-100 text-green-800 border-green-300",
    moderate: "bg-yellow-100 text-yellow-800 border-yellow-300",
    high: "bg-orange-100 text-orange-800 border-orange-300",
    very_high: "bg-red-100 text-red-800 border-red-300",
    severe: "bg-purple-100 text-purple-800 border-purple-300",
    hazardous: "bg-gray-900 text-white border-gray-700",
  };
  const cls = map[level.toLowerCase()] ?? "bg-gray-100 text-gray-800";
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${cls}`}
      aria-label={`Risk level: ${level.replace("_", " ")}`}
    >
      Risk: {level.replace("_", " ").toUpperCase()}
    </span>
  );
}

// ─── Single message bubble ────────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: AssistantMessage }) {
  const isUser = msg.role === "user";
  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}
      role="listitem"
    >
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
          isUser
            ? "bg-blue-600 text-white rounded-br-sm"
            : "bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-gray-100 rounded-bl-sm"
        }`}
      >
        {/* Message text */}
        <p className="whitespace-pre-wrap">{msg.content}</p>

        {/* Grounding badges — only on assistant messages */}
        {!isUser && (
          <div className="mt-2 space-y-1.5">
            {msg.aqi != null && (
              <div className="flex flex-wrap gap-1.5 items-center">
                <Badge variant="neutral" className="text-xs">
                  AQI {msg.aqi}
                </Badge>
                {msg.riskLevel && <RiskBadge level={msg.riskLevel} />}
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {msg.llmGrounded ? "🤖 AI-explained" : "⚙️ Deterministic engine"}
                </span>
              </div>
            )}

            {/* Approved actions */}
            {msg.actions && msg.actions.length > 0 && (
              <details className="text-xs text-gray-600 dark:text-gray-400">
                <summary className="cursor-pointer hover:text-blue-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded">
                  {msg.actions.length} recommended action{msg.actions.length > 1 ? "s" : ""}
                </summary>
                <ul className="mt-1 ml-3 space-y-0.5 list-disc">
                  {msg.actions.map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
              </details>
            )}

            {/* Scientific rationale */}
            {msg.rationale && (
              <details className="text-xs text-gray-500 dark:text-gray-400">
                <summary className="cursor-pointer hover:text-blue-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded">
                  Scientific rationale
                </summary>
                <p className="mt-1 ml-3 italic">{msg.rationale}</p>
              </details>
            )}
          </div>
        )}

        <time
          className={`block text-xs mt-1 ${
            isUser ? "text-blue-200" : "text-gray-400 dark:text-gray-500"
          }`}
          dateTime={msg.timestamp.toISOString()}
        >
          {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </time>
      </div>
    </div>
  );
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
      const data = await sendAssistantQuery(trimmed, lat, lon, profile);
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
      <div
        className="flex gap-2 px-3 py-2 overflow-x-auto scrollbar-thin border-b border-gray-100 dark:border-gray-800"
        aria-label="Quick question suggestions"
        role="toolbar"
      >
        {QUICK_PROMPTS.map((p) => (
          <button
            key={p.query}
            onClick={() => handleSend(p.query)}
            disabled={loading}
            className="flex-shrink-0 text-xs bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-700 rounded-full px-3 py-1.5 hover:bg-blue-100 dark:hover:bg-blue-800 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label={`Quick question: ${p.label}`}
          >
            {p.label}
          </button>
        ))}
      </div>

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
