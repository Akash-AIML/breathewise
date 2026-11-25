import {
  AirQualityApiResponse,
  ComparisonApiResponse,
  ComparisonPresetsResponse,
  StationsApiResponse,
} from "@/types/observation";
import {
  HouseholdProfile,
  IndoorGuidance,
  PersonalizedPlan,
  SustainableAlternative,
} from "@/types/recommendations";

// Empty default keeps production requests on the deployment origin, where the
// explicit rewrite allowlist proxies /api/v1 to the backend. A remote base URL
// is ignored in production so a public NEXT_PUBLIC_* value cannot redirect
// coordinates or household profiles to a third-party host.
const configuredBaseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");
const isProduction = process.env.NEXT_PUBLIC_APP_ENV === "production" || process.env.NODE_ENV === "production";
const API_BASE_URL =
  isProduction && configuredBaseUrl && !configuredBaseUrl.startsWith("/") ? "" : configuredBaseUrl;

const REQUEST_TIMEOUT_MS = 15000;

function apiUrl(path: string): string {
  const origin = typeof window === "undefined" ? "http://localhost" : window.location.origin;
  return new URL(`${API_BASE_URL}${path}`, origin).toString();
}

async function fetchWithTimeout(url: string, init: RequestInit = {}): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

/** Never render raw upstream error text in the UI: it is untrusted content. */
function safeErrorMessage(fallback: string, status: number): string {
  if (status === 429) return "Too many requests. Please wait a moment and try again.";
  if (status >= 500) return `${fallback} The service is temporarily unavailable.`;
  return fallback;
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

  const response = await fetchWithTimeout(url.toString(), { headers: { Accept: "application/json" } });
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
    const response = await fetchWithTimeout(url.toString(), { headers: { Accept: "application/json" } });
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
  // Production intentionally forbids cache bypass; do not waste a request on a
  // 403 the backend will always return.
  if (bypassCache && !isProduction) {
    url.searchParams.append("bypass_cache", "true");
  }

  const response = await fetchWithTimeout(url.toString(), {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new ApiError(safeErrorMessage("Failed to fetch air quality data.", response.status), response.status);
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

  const response = await fetchWithTimeout(url.toString(), {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new ApiError(safeErrorMessage("Failed to fetch monitoring stations.", response.status), response.status);
  }

  return response.json();
}

export async function fetchComparisonPresets(): Promise<ComparisonPresetsResponse> {
  const response = await fetchWithTimeout(apiUrl("/api/v1/stations/comparison-presets"), {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new ApiError(
      safeErrorMessage("Failed to load comparison presets.", response.status),
      response.status
    );
  }

  const data = (await response.json()) as Partial<ComparisonPresetsResponse>;
  return {
    success: data.success ?? true,
    source: data.source ?? "unknown",
    presets: Array.isArray(data.presets) ? data.presets : [],
    message: data.message ?? "",
  };
}

export async function fetchStationComparison(stationIds: string[]): Promise<ComparisonApiResponse> {
  const url = new URL(apiUrl("/api/v1/stations/compare"));
  url.searchParams.append("station_ids", stationIds.join(","));

  const response = await fetchWithTimeout(url.toString(), {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new ApiError(safeErrorMessage("Failed to compare stations.", response.status), response.status);
  }

  return response.json();
}

export async function fetchPersonalizedPlan(
  lat: number,
  lon: number,
  profile: HouseholdProfile
): Promise<PersonalizedPlan> {
  const response = await fetchWithTimeout(apiUrl("/api/v1/recommendations/plan"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ lat, lon, profile }),
  });

  if (!response.ok) {
    throw new ApiError(safeErrorMessage("Failed to generate personalized plan.", response.status), response.status);
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

  const response = await fetchWithTimeout(url.toString(), {
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

  const response = await fetchWithTimeout(url.toString(), {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new ApiError("Failed to fetch sustainable alternatives.", response.status);
  }

  return response.json();
}
