import { HouseholdProfile } from "@/types/recommendations";

// ─── API Helper ───────────────────────────────────────────────────────────────

export async function sendAssistantQuery(
  query: string,
  lat: number,
  lon: number,
  profile?: HouseholdProfile
) {
  const res = await fetch("/api/v1/assistant/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, lat, lon, profile: profile ?? {} }),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { message?: string; detail?: string };
    throw new Error(err.message ?? err.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}
