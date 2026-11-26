// Thin facade: feature modules live in ./api and are re-exported here so
// existing imports from "@/lib/api" keep working.
export {
  ApiError,
  fetchAirQuality,
  fetchComparisonPresets,
  fetchIndoorGuidance,
  fetchPersonalizedPlan,
  fetchReverseGeocode,
  fetchStationComparison,
  fetchStations,
  fetchSustainableAlternatives,
  searchLocations,
  sendAssistantQuery,
  type ChatTurnPayload,
  type GeocodedLocation,
  type ReverseGeocodedPlace,
} from "./api/index";
