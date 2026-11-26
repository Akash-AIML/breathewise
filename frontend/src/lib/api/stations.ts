import { StationsApiResponse } from "@/types/observation";
import { apiUrl, ApiError, fetchWithTimeout, parseApiResponse, safeErrorMessage } from "./client";
import { stationsResponseSchema } from "./schemas/observation";

export async function fetchStations(
  query?: string,
  lat?: number,
  lon?: number
): Promise<StationsApiResponse> {
  const url = new URL(apiUrl("/api/v1/stations"));
  if (query) {
    url.searchParams.append("query", query);
  }
  if (lat !== undefined && lon !== undefined) {
    url.searchParams.append("lat", lat.toString());
    url.searchParams.append("lon", lon.toString());
  }

  return fetchWithTimeout(
    url.toString(),
    {
      method: "GET",
      headers: { Accept: "application/json" },
    },
    async (response) => {
      if (!response.ok) {
        throw new ApiError(
          safeErrorMessage("Failed to fetch monitoring stations.", response.status),
          response.status
        );
      }
      return parseApiResponse(response, stationsResponseSchema, "Failed to fetch monitoring stations.");
    }
  );
}
