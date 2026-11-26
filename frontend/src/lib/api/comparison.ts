import { ComparisonApiResponse, ComparisonPresetsResponse } from "@/types/observation";
import { apiUrl, ApiError, fetchWithTimeout, parseApiResponse, safeErrorMessage } from "./client";
import {
  comparisonPresetsResponseSchema,
  comparisonResponseSchema,
} from "./schemas/comparison";

export async function fetchComparisonPresets(): Promise<ComparisonPresetsResponse> {
  return fetchWithTimeout(
    apiUrl("/api/v1/stations/comparison-presets"),
    {
      method: "GET",
      headers: { Accept: "application/json" },
    },
    async (response) => {
      if (!response.ok) {
        throw new ApiError(
          safeErrorMessage("Failed to load comparison presets.", response.status),
          response.status
        );
      }
      return parseApiResponse(
        response,
        comparisonPresetsResponseSchema,
        "Failed to load comparison presets."
      );
    }
  );
}

export async function fetchStationComparison(stationIds: string[]): Promise<ComparisonApiResponse> {
  const url = new URL(apiUrl("/api/v1/stations/compare"));
  url.searchParams.append("station_ids", stationIds.join(","));

  return fetchWithTimeout(
    url.toString(),
    {
      method: "GET",
      headers: { Accept: "application/json" },
    },
    async (response) => {
      if (!response.ok) {
        throw new ApiError(
          safeErrorMessage("Failed to compare stations.", response.status),
          response.status
        );
      }
      return parseApiResponse(response, comparisonResponseSchema, "Failed to compare stations.");
    }
  );
}
