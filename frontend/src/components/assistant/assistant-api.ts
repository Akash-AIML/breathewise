import { HouseholdProfile } from "@/types/recommendations";

// The backend may spend up to LLM_REQUEST_BUDGET_SECONDS (20s) trying the whole
// model chain. Leave headroom for network/proxy overhead so a successful
// failover is not aborted by the browser at the exact backend deadline.
const ASSISTANT_TIMEOUT_MS = 25000;

function safeMessage(status: number): string {
  if (status === 429) return "Too many assistant requests. Please wait a moment and try again.";
  if (status >= 500) return "The assistant is temporarily unavailable. Please try again.";
  return "The assistant could not answer that request.";
}

export async function sendAssistantQuery(
  query: string,
  lat: number,
  lon: number,
  profile?: HouseholdProfile
) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ASSISTANT_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch("/api/v1/assistant/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ query, lat, lon, profile: profile ?? {} }),
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }

  // Do not surface untrusted upstream text in the assistant UI.
  if (!res.ok) throw new Error(safeMessage(res.status));
  return res.json();
}
