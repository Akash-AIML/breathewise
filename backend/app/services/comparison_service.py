"""Data-driven station comparison built from live metadata or honest grid estimates."""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from app.schemas.comparison import (
    ComparisonBasis,
    ComparisonCandidate,
    ComparisonPreset,
)
from app.schemas.cpcb import CPCBStationObservation
from app.schemas.observation import NormalizedObservation
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
        """Fetch live CPCB observations once; degrade silently to grid estimates."""
        try:
            return await self.air_quality.cpcb_adapter.get_station_observations()
        except Exception:
            # Provider exceptions can contain credentialed URLs. Do not log details.
            logger.warning("Live CPCB comparison lookup unavailable; using grid estimates")
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

    async def resolve(self, ids: list[str]) -> ComparisonResolution:
        live = await self._live_observations()
        live_by_id = {obs.station_id: obs for obs in live}
        grid_by_id = {candidate.id: candidate for candidate in self._grid_candidates()}
        # Legacy IDs without the grid prefix are accepted but never presented as stations.
        legacy_grid_ids = {
            candidate.id.removeprefix(GRID_ID_PREFIX): candidate
            for candidate in self._grid_candidates()
        }

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
            if not candidate:
                unresolved.append(station_id)
                continue

            observation = await self.air_quality.get_air_quality_for_coordinates(
                candidate.latitude, candidate.longitude
            )
            if not observation:
                unresolved.append(station_id)
                continue

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
            resolved.append(
                ResolvedObservation(
                    observation=observation,
                    basis="coordinate_estimate",
                    source="fallback_registry_coordinate_grid",
                )
            )

        return ComparisonResolution(
            observations=[item.observation for item in resolved],
            bases={item.basis for item in resolved},
            sources={item.source for item in resolved},
            unresolved_ids=unresolved,
        )


def _dedupe(candidates: list[ComparisonCandidate]) -> list[ComparisonCandidate]:
    seen = set()
    result = []
    for candidate in candidates:
        if candidate.id in seen:
            continue
        seen.add(candidate.id)
        result.append(candidate)
    return result


def _first(candidates: list[ComparisonCandidate], predicate) -> ComparisonCandidate | None:
    return next((candidate for candidate in candidates if predicate(candidate)), None)


def _matches_city(candidate: ComparisonCandidate, city_key: str) -> bool:
    """Match provider city/state/label variants instead of trusting one exact city string."""
    text = f"{candidate.city or ''} {candidate.state or ''} {candidate.label}".lower()
    return any(alias in text for alias in CITY_ALIASES[city_key])


def _build_presets(
    candidates: list[ComparisonCandidate], basis: LiveBasis
) -> list[ComparisonPreset]:
    prefix = "Live station" if basis == "live_station" else "Grid estimate"
    source = "CPCB/data.gov.in" if basis == "live_station" else "fallback_registry_coordinate_grid"
    presets: list[ComparisonPreset] = []

    def add(
        key: str,
        name: str,
        picked: list[ComparisonCandidate],
        description: str,
    ) -> None:
        if len(picked) < 2 or len({item.id for item in picked}) != len(picked):
            return
        presets.append(
            ComparisonPreset(
                key=key,
                name=name,
                description=description,
                ids=[item.id for item in picked],
                basis=basis,
                source=source,
                candidates=picked,
            )
        )

    delhi = [c for c in candidates if _matches_city(c, "delhi")]
    central = _first(delhi, lambda c: "ito" in c.label.lower() or "central" in c.label.lower())
    central = central or _first(delhi, lambda _c: True)
    industrial = _first(
        delhi,
        lambda c: "anand" in c.label.lower() or "industrial" in c.label.lower(),
    )
    industrial = industrial or _first(delhi, lambda c: central is None or c.id != central.id)
    if central and industrial:
        add(
            "delhi-corridors",
            f"{prefix}: {central.label} vs {industrial.label}",
            [central, industrial],
            "Two Delhi locations selected from current live stations or registered coordinates.",
        )

    metro = [
        _first(candidates, lambda c, key=city: _matches_city(c, key))
        for city in ("delhi", "mumbai", "bengaluru")
    ]
    if all(metro):
        add(
            "metro-cross-city",
            f"{prefix}: Delhi vs Mumbai vs Bengaluru",
            [item for item in metro if item is not None],
            "Three metropolitan locations selected from the current comparison source.",
        )

    gangetic = [
        _first(candidates, lambda c, key=city: _matches_city(c, key))
        for city in ("delhi", "lucknow", "kolkata")
    ]
    if all(gangetic):
        add(
            "indo-gangetic-plain",
            f"{prefix}: Delhi vs Lucknow vs Kolkata",
            [item for item in gangetic if item is not None],
            "Three Indo-Gangetic locations selected from the current comparison source.",
        )

    return presets
