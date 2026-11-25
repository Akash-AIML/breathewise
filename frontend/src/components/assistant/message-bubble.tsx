"use client";

import { Badge } from "@/components/ui/badge";

export interface AssistantMessage {
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

// ─── Risk badge colour (non-colour-only: text label always present) ───────────

export function RiskBadge({ level }: { level: string }) {
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

export function MessageBubble({ msg }: { msg: AssistantMessage }) {
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
