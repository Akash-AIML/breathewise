import {
  AirQualityApiResponse,
  ComparisonApiResponse,
  StationsApiResponse,
} from "@/types/observation";
import {
  HouseholdProfile,
  IndoorGuidance,
  PersonalizedPlan,
  SustainableAlternative,
} from "@/types/recommendations";

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

export async function fetchPersonalizedPlan(
  lat: number,
  lon: number,
  profile: HouseholdProfile
): Promise<PersonalizedPlan> {
  const response = await fetch(`${API_BASE_URL}/api/v1/recommendations/plan`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ lat, lon, profile }),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new ApiError(errorBody.message || "Failed to generate personalized plan.", response.status);
  }

  return response.json();
}

export async function fetchIndoorGuidance(
  areaSqft: number = 600,
  aqi?: number
): Promise<IndoorGuidance> {
  const url = new URL(`${API_BASE_URL}/api/v1/recommendations/indoor`);
  url.searchParams.append("area_sqft", areaSqft.toString());
  if (aqi !== undefined) {
    url.searchParams.append("aqi", aqi.toString());
  }

  const response = await fetch(url.toString(), {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new ApiError("Failed to fetch indoor guidance.", response.status);
  }

  return response.json();
}

export async function fetchSustainableAlternatives(
  aqi?: number
): Promise<SustainableAlternative[]> {
  const url = new URL(`${API_BASE_URL}/api/v1/recommendations/sustainable-alternatives`);
  if (aqi !== undefined) {
    url.searchParams.append("aqi", aqi.toString());
  }

  const response = await fetch(url.toString(), {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new ApiError("Failed to fetch sustainable alternatives.", response.status);
  }

  return response.json();
}
