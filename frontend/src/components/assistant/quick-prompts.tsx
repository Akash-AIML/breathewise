"use client";

// ─── Quick prompt chips ───────────────────────────────────────────────────────

export const QUICK_PROMPTS = [
  { label: "🏃 Can I exercise outside?", query: "Is it safe to go jogging or exercise outdoors today?" },
  { label: "📊 Direct impact of my choices", query: "What is the direct impact of switching my commute or using a HEPA purifier today?" },
  { label: "🌫️ Severe winter smog tips", query: "How should my family navigate severe winter smog and thermal inversion hours today?" },
  { label: "👶 Kids safe outdoors?", query: "Is it safe for my children to play outside or go to school?" },
  { label: "🌿 Do plants help?", query: "Can houseplants improve my indoor air quality?" },
  { label: "🚇 Best commute option?", query: "What is the safest way to commute today?" },
  { label: "😷 When to wear a mask?", query: "Should I wear an N95 mask today?" },
  { label: "🏠 Indoor air tips?", query: "How can I improve my indoor air quality right now?" },
];

interface QuickPromptsProps {
  loading: boolean;
  onSend: (query: string) => void;
}

export function QuickPrompts({ loading, onSend }: QuickPromptsProps) {
  return (
    <div
      className="flex gap-2 px-3 py-2 overflow-x-auto scrollbar-thin border-b border-gray-100 dark:border-gray-800"
      aria-label="Quick question suggestions"
      role="toolbar"
    >
      {QUICK_PROMPTS.map((p) => (
        <button
          key={p.query}
          onClick={() => onSend(p.query)}
          disabled={loading}
          className="flex-shrink-0 text-xs bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-700 rounded-full px-3 py-1.5 hover:bg-blue-100 dark:hover:bg-blue-800 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label={`Quick question: ${p.label}`}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}
