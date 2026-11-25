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

// Empty default keeps production requests on the deployment origin, where
// /api/v1 is proxied to the backend. A separate host is opt-in via env var.
const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

function apiUrl(path: string): string {
  const origin = typeof window === "undefined" ? "http://localhost" : window.location.origin;
  return new URL(`${API_BASE_URL}${path}`, origin).toString();
}

export interface GeocodedLocation {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  admin1?: string;
  country?: string;
}

export async function searchLocations(query: string): Promise<GeocodedLocation[]> {
  const trimmed = query.trim();
  if (trimmed.length < 2) return [];
  // Keep third-party geocoding behind our own origin so CSP policies do not
  // need to allow an external host and the browser never sees provider URLs.
  const url = new URL(apiUrl("/api/v1/locations/search"));
  url.searchParams.set("name", trimmed);

  const response = await fetch(url.toString(), { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new ApiError("Location search is temporarily unavailable.", response.status);
  }
  const data = (await response.json()) as { results?: GeocodedLocation[] };
  return (data.results ?? []).filter(
    (item) => Number.isFinite(item.latitude) && Number.isFinite(item.longitude)
  );
}

export interface ReverseGeocodedPlace {
  name: string;
  state?: string | null;
  country?: string | null;
  display_name?: string | null;
  source: string;
}

/** Best-effort locality lookup. Returns null instead of breaking the location flow. */
export async function fetchReverseGeocode(
  lat: number,
  lon: number
): Promise<ReverseGeocodedPlace | null> {
  const url = new URL(apiUrl("/api/v1/locations/reverse"));
  url.searchParams.set("lat", lat.toString());
  url.searchParams.set("lon", lon.toString());

  try {
    const response = await fetch(url.toString(), { headers: { Accept: "application/json" } });
    if (!response.ok) return null;
    const data = (await response.json()) as { place?: ReverseGeocodedPlace | null };
    return data.place?.name ? data.place : null;
  } catch {
    return null;
  }
}

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
  const url = new URL(apiUrl("/api/v1/air-quality"));
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

  const response = await fetch(url.toString(), {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new ApiError(errorBody.message || "Failed to fetch monitoring stations.", response.status);
  }

  return response.json();
}

export async function fetchStationComparison(stationIds: string[]): Promise<ComparisonApiResponse> {
  const url = new URL(apiUrl("/api/v1/stations/compare"));
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
  const response = await fetch(apiUrl("/api/v1/recommendations/plan"), {
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
  const url = new URL(apiUrl("/api/v1/recommendations/indoor"));
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
  const url = new URL(apiUrl("/api/v1/recommendations/sustainable-alternatives"));
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
