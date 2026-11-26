import { z } from "zod";
import { apiUrl, ApiError, fetchWithTimeout, parseApiResponse } from "./client";
import {
  geocodedLocationSchema,
  locationSearchResponseSchema,
  reverseGeocodeResponseSchema,
  reverseGeocodedPlaceSchema,
} from "./schemas/locations";

export type GeocodedLocation = z.output<typeof geocodedLocationSchema>;
export type ReverseGeocodedPlace = z.output<typeof reverseGeocodedPlaceSchema>;

export async function searchLocations(query: string): Promise<GeocodedLocation[]> {
  const trimmed = query.trim();
  if (trimmed.length < 2) return [];
  // Keep third-party geocoding behind our own origin so CSP policies do not
  // need to allow an external host and the browser never sees provider URLs.
  const url = new URL(apiUrl("/api/v1/locations/search"));
  url.searchParams.set("name", trimmed);

  return fetchWithTimeout(
    url.toString(),
    { headers: { Accept: "application/json" } },
    async (response) => {
      if (!response.ok) {
        throw new ApiError("Location search is temporarily unavailable.", response.status);
      }
      const data = await parseApiResponse(
        response,
        locationSearchResponseSchema,
        "Location search returned an invalid response."
      );
      return data.results.filter(
        (item) => Number.isFinite(item.latitude) && Number.isFinite(item.longitude)
      );
    }
  );
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
    return await fetchWithTimeout(
      url.toString(),
      { headers: { Accept: "application/json" } },
      async (response) => {
        if (!response.ok) return null;
        const parsed = reverseGeocodeResponseSchema.safeParse(await response.json());
        if (!parsed.success || !parsed.data.place?.name) return null;
        return parsed.data.place;
      }
    );
  } catch {
    // Naming is optional: a failed lookup must never block exact coordinates.
    return null;
  }
}
