import { AirQualityApiResponse } from "@/types/observation";
import {
  apiUrl,
  ApiError,
  fetchWithTimeout,
  isProduction,
  parseApiResponse,
  safeErrorMessage,
} from "./client";
import { airQualityResponseSchema } from "./schemas/observation";

export async function fetchAirQuality(
  lat: number,
  lon: number,
  bypassCache: boolean = false
): Promise<AirQualityApiResponse> {
  const url = new URL(apiUrl("/api/v1/air-quality"));
  url.searchParams.append("lat", lat.toString());
  url.searchParams.append("lon", lon.toString());
  // Production intentionally forbids cache bypass; do not waste a request on a
  // 403 the backend will always return.
  if (bypassCache && !isProduction) {
    url.searchParams.append("bypass_cache", "true");
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
          safeErrorMessage("Failed to fetch air quality data.", response.status),
          response.status
        );
      }
      return parseApiResponse(response, airQualityResponseSchema, "Failed to fetch air quality data.");
    }
  );
}
