import {
  AirQualityApiResponse,
  ComparisonApiResponse,
  StationMetadata,
  StationsApiResponse,
} from "@/types/observation";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function fetchAirQuality(
  lat: number,
  lon: number,
  bypassCache: boolean = false
): Promise<AirQualityApiResponse> {
  const url = new URL(`${API_BASE_URL}/api/v1/air-quality`);
  url.searchParams.append("lat", lat.toString());
  url.searchParams.append("lon", lon.toString());
  if (bypassCache) {
    url.searchParams.append("bypass_cache", "true");
  }

  const response = await fetch(url.toString(), {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new ApiError(errorBody.message || "Failed to fetch air quality data.", response.status);
  }

  return response.json();
}

export async function fetchStations(query?: string): Promise<StationsApiResponse> {
  const url = new URL(`${API_BASE_URL}/api/v1/stations`);
  if (query) {
    url.searchParams.append("query", query);
  }

  const response = await fetch(url.toString(), {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new ApiError("Failed to fetch monitoring stations.", response.status);
  }

  return response.json();
}

export async function fetchStationComparison(stationIds: string[]): Promise<ComparisonApiResponse> {
  const url = new URL(`${API_BASE_URL}/api/v1/stations/compare`);
  url.searchParams.append("station_ids", stationIds.join(","));

  const response = await fetch(url.toString(), {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new ApiError(errorBody.message || "Failed to compare stations.", response.status);
  }

  return response.json();
}
