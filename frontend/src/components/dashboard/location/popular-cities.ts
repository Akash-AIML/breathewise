import { MapStation } from "@/components/dashboard/station-map";

/** Fallback picker only. Device/geocoded coordinates are never snapped to these. */
export const POPULAR_CITIES: (MapStation & { distance_km?: number })[] = [
  { name: "Delhi (ITO)", station_id: "cpcb_delhi_ito", city: "Delhi", state: "Delhi", lat: 28.6289, lon: 77.2407 },
  { name: "Delhi (Anand Vihar)", station_id: "cpcb_delhi_anand_vihar", city: "Delhi", state: "Delhi", lat: 28.6469, lon: 77.3160 },
  { name: "Mumbai (Bandra)", station_id: "cpcb_mumbai_bandra", city: "Mumbai", state: "Maharashtra", lat: 19.0657, lon: 72.8687 },
  { name: "Bengaluru (BTM)", station_id: "cpcb_bengaluru_btm", city: "Bengaluru", state: "Karnataka", lat: 12.9166, lon: 77.6101 },
  { name: "Kolkata (Victoria)", station_id: "cpcb_kolkata_victoria", city: "Kolkata", state: "West Bengal", lat: 22.5448, lon: 88.3426 },
  { name: "Chennai (Alandur)", station_id: "cpcb_chennai_alandur", city: "Chennai", state: "Tamil Nadu", lat: 13.0033, lon: 80.2014 },
  { name: "Hyderabad (Sanathnagar)", station_id: "cpcb_hyderabad_sanathnagar", city: "Hyderabad", state: "Telangana", lat: 17.4589, lon: 78.4347 },
  { name: "Ahmedabad (Maninagar)", station_id: "cpcb_ahmedabad_maninagar", city: "Ahmedabad", state: "Gujarat", lat: 22.9984, lon: 72.6033 },
  { name: "Pune (Shivajinagar)", station_id: "cpcb_pune_shivajinagar", city: "Pune", state: "Maharashtra", lat: 18.5314, lon: 73.8446 },
  { name: "Lucknow (Lalbagh)", station_id: "cpcb_lucknow_lalbagh", city: "Lucknow", state: "Uttar Pradesh", lat: 26.8467, lon: 80.9462 },
];
