"""Data-driven station comparison built from live metadata or honest grid estimates."""

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import partial
from typing import Literal

from app.schemas.comparison import (
    ComparisonBasis,
    ComparisonCandidate,
    ComparisonDifferential,
    ComparisonPreset,
    ComparisonResponse,
)
from app.schemas.cpcb import CPCBStationObservation
from app.schemas.observation import NormalizedObservation, PollutantType
from app.services.air_quality_service import INDIAN_CITIES_REGISTRY, AirQualityService

logger = logging.getLogger(__name__)

LiveBasis = Literal["live_station", "coordinate_estimate"]
GRID_ID_PREFIX = "grid:"
GRID_NOTE = "Coordinate-grid estimate at a registered location, not a physical station observation."
CITY_ALIASES = {
    "delhi": ("delhi",),
    "mumbai": ("mumbai", "bombay"),
    "bengaluru": ("bengaluru", "bangalore"),
    "lucknow": ("lucknow",),
    "kolkata": ("kolkata", "calcutta"),
}


@dataclass(frozen=True)
class ResolvedObservation:
    observation: NormalizedObservation
    basis: LiveBasis
    source: str


@dataclass(frozen=True)
class ComparisonResolution:
    observations: list[NormalizedObservation]
    bases: set[LiveBasis]
    sources: set[str]
    unresolved_ids: list[str]

    @property
    def basis(self) -> ComparisonBasis:
        if self.bases == {"live_station"}:
            return "live_station"
        if self.bases == {"coordinate_estimate"}:
            return "coordinate_estimate"
        return "mixed"

    @property
    def source(self) -> str:
        if len(self.sources) == 1:
            return next(iter(self.sources))
        return "mixed sources"


class ComparisonService:
    def __init__(self, air_quality_service: AirQualityService | None = None) -> None:
        self.air_quality = air_quality_service or AirQualityService()

    async def _live_observations(self) -> list[CPCBStationObservation]:
        """Fetch live CPCB observations once; degrade cleanly to grid estimates."""
        try:
            return await self.air_quality.cpcb_adapter.get_station_observations()
        except Exception as exc:
            # Log only the exception type: provider errors can embed credentialed URLs.
            logger.warning(
                "Live CPCB comparison lookup unavailable (%s); using grid estimates",
                type(exc).__name__,
            )
            return []

    @staticmethod
    def _live_candidates(
        observations: Iterable[CPCBStationObservation],
    ) -> list[ComparisonCandidate]:
        candidates = [
            ComparisonCandidate(
                id=obs.station_id,
                label=obs.station,
                city=obs.city,
                state=obs.state,
                latitude=obs.latitude,
                longitude=obs.longitude,
                basis="live_station",
                source="CPCB/data.gov.in",
            )
            for obs in observations
        ]
        return _dedupe(candidates)

    @staticmethod
    def _grid_candidates() -> list[ComparisonCandidate]:
        return [
            ComparisonCandidate(
                id=f"{GRID_ID_PREFIX}{station.station_id}",
                label=f"{station.station_name} (grid estimate)",
                city=station.city,
                state=station.state,
                latitude=station.latitude,
                longitude=station.longitude,
                basis="coordinate_estimate",
                source="fallback_registry_coordinate_grid",
            )
            for station in INDIAN_CITIES_REGISTRY
        ]

    async def get_presets(self) -> tuple[list[ComparisonPreset], str, str]:
        """Build comparison presets from current live stations, or labelled grid coordinates."""
        live = await self._live_observations()
        if live:
            candidates = self._live_candidates(live)
            presets = _build_presets(candidates, "live_station")
            if presets:
                return (
                    presets,
                    "CPCB/data.gov.in",
                    ("Presets use reported CPCB station coordinates and live observations."),
                )

        candidates = self._grid_candidates()
        presets = _build_presets(candidates, "coordinate_estimate")
        return (
            presets,
            "fallback_registry_coordinate_grid",
            (
                "Live station coordinates are unavailable. These presets compare exact registered "
                "coordinates through the grid provider and are not CPCB station observations."
            ),
        )

    async def _resolve_grid_candidate(
        self, candidate: ComparisonCandidate
    ) -> ResolvedObservation | None:
        observation = await self.air_quality.get_air_quality_for_coordinates(
            candidate.latitude, candidate.longitude
        )
        if not observation:
            return None

        observation = observation.model_copy(deep=True)
        observation.station.station_id = candidate.id
        observation.station.station_name = candidate.label
        observation.station.city = candidate.city or ""
        observation.station.state = candidate.state or ""
        observation.station.provider = "fallback_registry_coordinate"
        observation.station.distance_km = 0.0
        observation.notes = (
            f"{GRID_NOTE} {observation.notes}".strip() if observation.notes else GRID_NOTE
        )
        return ResolvedObservation(
            observation=observation,
            basis="coordinate_estimate",
            source="fallback_registry_coordinate_grid",
        )

    async def resolve(self, ids: list[str]) -> ComparisonResolution:
        live = await self._live_observations()
        live_by_id = {obs.station_id: obs for obs in live}
        grid_candidates = self._grid_candidates()
        grid_by_id = {c.id: c for c in grid_candidates}
        # Legacy IDs without the grid prefix are accepted but never presented as stations.
        legacy_grid_ids = {c.id.removeprefix(GRID_ID_PREFIX): c for c in grid_candidates}

        resolved: list[ResolvedObservation] = []
        unresolved: list[str] = []
        for raw_id in ids:
            station_id = raw_id.strip()
            if station_id in live_by_id:
                obs = live_by_id[station_id]
                normalized = self.air_quality.cpcb_adapter.to_normalized(
                    obs, obs.latitude, obs.longitude, 0.0
                )
                resolved.append(
                    ResolvedObservation(
                        observation=normalized,
                        basis="live_station",
                        source="CPCB/data.gov.in",
                    )
                )
                continue

            candidate = grid_by_id.get(station_id) or legacy_grid_ids.get(station_id)
            item = await self._resolve_grid_candidate(candidate) if candidate else None
            if item is None:
                unresolved.append(station_id)
            else:
                resolved.append(item)

        return ComparisonResolution(
            observations=[item.observation for item in resolved],
            bases={item.basis for item in resolved},
            sources={item.source for item in resolved},
            unresolved_ids=unresolved,
        )

    def build_response(
        self, ids: list[str], resolution: ComparisonResolution
    ) -> ComparisonResponse:
        """Assemble a ComparisonResponse with differential analytics and provenance."""
        observations = resolution.observations
        differential = _compute_differential(observations, resolution.basis)
        basis_messages = {
            "live_station": "Live CPCB station observations.",
            "coordinate_estimate": (
                "Coordinate-grid estimates at registered locations, not physical station observations."
            ),
            "mixed": "Mixed live stations and coordinate-grid estimates.",
        }
        message = basis_messages[resolution.basis]
        if resolution.unresolved_ids:
            message += f" Unresolved IDs: {', '.join(resolution.unresolved_ids)}."

        return ComparisonResponse(
            success=True,
            stations_count=len(observations),
            observations=observations,
            differential=differential,
            basis=resolution.basis,
            source=resolution.source,
            requested_ids=ids,
            unresolved_ids=resolution.unresolved_ids,
            message=message,
        )


def _pm25_value(observation: NormalizedObservation) -> float:
    reading = observation.readings.get(PollutantType.PM2_5.value)
    return reading.value if reading else 0.0


def _compute_differential(
    observations: list[NormalizedObservation], basis: ComparisonBasis
) -> ComparisonDifferential | None:
    valid_aqi_obs = [o for o in observations if o.calculated_aqi is not None]
    if len(valid_aqi_obs) < 2:
        return None
    sorted_by_aqi = sorted(valid_aqi_obs, key=lambda x: x.calculated_aqi or 0)
    cleanest, worst = sorted_by_aqi[0], sorted_by_aqi[-1]
    aqi_diff = (worst.calculated_aqi or 0) - (cleanest.calculated_aqi or 0)
    pm25_diff = round(_pm25_value(worst) - _pm25_value(cleanest), 1)
    basis_label = {
        "live_station": "Live stations",
        "coordinate_estimate": "Grid estimates",
        "mixed": "Mixed sources",
    }[basis]
    summary = (
        f"{basis_label}: {cleanest.station.station_name} reports cleaner air "
        f"({cleanest.calculated_aqi} AQI) compared to "
        f"{worst.station.station_name} ({worst.calculated_aqi} AQI), "
        f"with an AQI difference of {aqi_diff} points."
    )
    return ComparisonDifferential(
        cleanest_station_id=cleanest.station.station_id,
        cleanest_station_name=cleanest.station.station_name,
        most_polluted_station_id=worst.station.station_id,
        most_polluted_station_name=worst.station.station_name,
        aqi_difference=aqi_diff,
        pm25_difference_ug_m3=pm25_diff,
        summary=summary,
    )


def _dedupe(candidates: list[ComparisonCandidate]) -> list[ComparisonCandidate]:
    seen: set[str] = set()
    result: list[ComparisonCandidate] = []
    for candidate in candidates:
        if candidate.id in seen:
            continue
        seen.add(candidate.id)
        result.append(candidate)
    return result


def _first(
    candidates: list[ComparisonCandidate], predicate: Callable[[ComparisonCandidate], bool]
) -> ComparisonCandidate | None:
    return next((candidate for candidate in candidates if predicate(candidate)), None)


def _matches_city(candidate: ComparisonCandidate, city_key: str) -> bool:
    """Match provider city/state/label variants instead of trusting one exact city string."""
    text = f"{candidate.city or ''} {candidate.state or ''} {candidate.label}".lower()
    return any(alias in text for alias in CITY_ALIASES[city_key])


def _make_preset(
    key: str,
    name: str,
    picked: list[ComparisonCandidate],
    description: str,
    basis: LiveBasis,
    source: str,
) -> ComparisonPreset | None:
    if len(picked) < 2 or len({item.id for item in picked}) != len(picked):
        return None
    return ComparisonPreset(
        key=key,
        name=name,
        description=description,
        ids=[item.id for item in picked],
        basis=basis,
        source=source,
        candidates=picked,
    )


def _delhi_preset(
    candidates: list[ComparisonCandidate], prefix: str, basis: LiveBasis, source: str
) -> ComparisonPreset | None:
    delhi = [c for c in candidates if _matches_city(c, "delhi")]
    central = _first(delhi, lambda c: "ito" in c.label.lower() or "central" in c.label.lower())
    central = central or _first(delhi, lambda _c: True)
    industrial = _first(
        delhi, lambda c: "anand" in c.label.lower() or "industrial" in c.label.lower()
    )
    industrial = industrial or _first(delhi, lambda c: central is None or c.id != central.id)
    if not (central and industrial):
        return None
    return _make_preset(
        "delhi-corridors",
        f"{prefix}: {central.label} vs {industrial.label}",
        [central, industrial],
        "Two Delhi locations selected from current live stations or registered coordinates.",
        basis,
        source,
    )


def _multi_city_preset(
    candidates: list[ComparisonCandidate],
    key: str,
    title: str,
    cities: tuple[str, ...],
    description: str,
    basis: LiveBasis,
    source: str,
) -> ComparisonPreset | None:
    picked = [_first(candidates, partial(_matches_city, city_key=city)) for city in cities]
    if not all(picked):
        return None
    return _make_preset(
        key,
        title,
        [item for item in picked if item is not None],
        description,
        basis,
        source,
    )


def _build_presets(
    candidates: list[ComparisonCandidate], basis: LiveBasis
) -> list[ComparisonPreset]:
    prefix = "Live station" if basis == "live_station" else "Grid estimate"
    source = "CPCB/data.gov.in" if basis == "live_station" else "fallback_registry_coordinate_grid"
    maybe_presets = [
        _delhi_preset(candidates, prefix, basis, source),
        _multi_city_preset(
            candidates,
            "metro-cross-city",
            f"{prefix}: Delhi vs Mumbai vs Bengaluru",
            ("delhi", "mumbai", "bengaluru"),
            "Three metropolitan locations selected from the current comparison source.",
            basis,
            source,
        ),
        _multi_city_preset(
            candidates,
            "indo-gangetic-plain",
            f"{prefix}: Delhi vs Lucknow vs Kolkata",
            ("delhi", "lucknow", "kolkata"),
            "Three Indo-Gangetic locations selected from the current comparison source.",
            basis,
            source,
        ),
    ]
    return [preset for preset in maybe_presets if preset is not None]
