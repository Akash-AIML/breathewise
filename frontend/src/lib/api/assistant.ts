import { z } from "zod";
import { HouseholdProfile } from "@/types/recommendations";
import { ASSISTANT_TIMEOUT_MS, fetchWithTimeout, parseApiResponse } from "./client";
import { assistantResponseSchema } from "./schemas/assistant";

export interface ChatTurnPayload {
  role: "user" | "assistant";
  content: string;
}

function safeAssistantMessage(status: number): string {
  if (status === 429) return "Too many assistant requests. Please wait a moment and try again.";
  if (status >= 500) return "The assistant is temporarily unavailable. Please try again.";
  return "The assistant could not answer that request.";
}

export async function sendAssistantQuery(
  query: string,
  lat: number,
  lon: number,
  profile?: HouseholdProfile,
  history: ChatTurnPayload[] = []
): Promise<z.output<typeof assistantResponseSchema>> {
  return fetchWithTimeout(
    "/api/v1/assistant/chat",
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        query,
        lat,
        lon,
        profile: profile ?? {},
        history: history.slice(-6).map((t) => ({ role: t.role, content: t.content.slice(0, 600) })),
      }),
    },
    async (res) => {
      // Do not surface untrusted upstream text in the assistant UI.
      if (!res.ok) throw new Error(safeAssistantMessage(res.status));
      return parseApiResponse(
        res,
        assistantResponseSchema,
        "The assistant returned an unexpected response. Please try again."
      );
    },
    ASSISTANT_TIMEOUT_MS
  );
}
