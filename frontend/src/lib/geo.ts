export interface GeoNamedPoint {
  name: string;
  city?: string;
  state?: string;
  lat: number;
  lon: number;
}

const EARTH_RADIUS_KM = 6371.0088;

function toRadians(degrees: number): number {
  return (degrees * Math.PI) / 180;
}

export function haversineDistanceKm(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const dLat = toRadians(lat2 - lat1);
  const dLon = toRadians(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(a)));
}

export function nearestNamedLocation<T extends GeoNamedPoint>(
  lat: number,
  lon: number,
  points: readonly T[]
): { point: T; distanceKm: number } | null {
  let best: { point: T; distanceKm: number } | null = null;
  for (const point of points) {
    if (!Number.isFinite(point.lat) || !Number.isFinite(point.lon)) continue;
    const distanceKm = haversineDistanceKm(lat, lon, point.lat, point.lon);
    if (!best || distanceKm < best.distanceKm) {
      best = { point, distanceKm };
    }
  }
  return best;
}

export function formatCoordinates(lat: number, lon: number): string {
  const latHemisphere = lat >= 0 ? "N" : "S";
  const lonHemisphere = lon >= 0 ? "E" : "W";
  return `${Math.abs(lat).toFixed(4)}°${latHemisphere}, ${Math.abs(lon).toFixed(4)}°${lonHemisphere}`;
}
