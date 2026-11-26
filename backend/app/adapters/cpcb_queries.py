import logging
from typing import TYPE_CHECKING, Any

from app.adapters.cpcb_transport import CPCBProviderError, redact_secrets
from app.core.config import settings
from app.schemas.cpcb import CPCBStationObservation

logger = logging.getLogger(__name__)


class CPCBQueriesMixin:
    """Station discovery, filter verification, and station queries for CPCBAdapter."""

    if TYPE_CHECKING:

        async def _fetch_pages(
            self,
            filters: dict[str, str] | None = None,
            max_pages: int | None = None,
            page_size: int | None = None,
        ) -> tuple[list[dict[str, Any]], int | None]: ...

        def parse_records(self, records: list[dict[str, Any]]) -> list[CPCBStationObservation]: ...
        async def _load_with_fallback(self, key: str, loader: Any) -> Any: ...

    async def _sample_observations(self) -> list[CPCBStationObservation]:
        async def load() -> list[CPCBStationObservation]:
            records, _ = await self._fetch_pages(
                max_pages=1,
                page_size=max(settings.CPCB_MIN_OFFLINE_STATION_SAMPLE, 5),
            )
            return self.parse_records(records)

        observations: list[CPCBStationObservation] = await self._load_with_fallback("sample", load)
        return observations

    async def _all_observations(self) -> list[CPCBStationObservation]:
        """Bounded pagination, cached. Only used when a precise filter is unavailable."""

        async def load() -> list[CPCBStationObservation]:
            records, _ = await self._fetch_pages()
            return self.parse_records(records)

        observations: list[CPCBStationObservation] = await self._load_with_fallback("all", load)
        return observations

    @staticmethod
    def _matches(observation: CPCBStationObservation, city: str | None, state: str | None) -> bool:
        if city and observation.city.strip().lower() != city.strip().lower():
            return False
        return not (state and observation.state.strip().lower() != state.strip().lower())

    async def verify_filters(self) -> dict[str, dict[str, Any]]:
        """Independently probe Tamil Nadu and Chennai filters against live data."""

        async def load() -> dict[str, dict[str, Any]]:
            sample = await self._sample_observations()
            observed_cities = {obs.city.strip().lower() for obs in sample}
            observed_states = {obs.state.strip().lower() for obs in sample}
            results: dict[str, dict[str, Any]] = {}

            for field, value, observed in (
                ("state", "Tamil Nadu", observed_states),
                ("city", "Chennai", observed_cities),
            ):
                entry: dict[str, Any] = {
                    "value": value,
                    "observed_in_unfiltered_sample": value.lower() in observed,
                    "verified": False,
                    "status": "value_not_in_sample",
                    "record_count": 0,
                }
                if entry["observed_in_unfiltered_sample"]:
                    try:
                        records, total = await self._fetch_pages(
                            filters={f"filters[{field}]": value}, max_pages=1, page_size=5
                        )
                    except CPCBProviderError as exc:
                        entry["status"] = "provider_unavailable"
                        entry["detail"] = redact_secrets(exc)
                    else:
                        parsed = self.parse_records(records)
                        expected_city = value if field == "city" else None
                        expected_state = value if field == "state" else None
                        entry["record_count"] = len(records)
                        entry["reported_total"] = total
                        if not records:
                            entry["status"] = "no_records"
                        elif parsed and all(
                            self._matches(obs, expected_city, expected_state) for obs in parsed
                        ):
                            entry["verified"] = True
                            entry["status"] = "verified"
                        else:
                            entry["status"] = "filter_returned_unrelated_records"
                results[field] = entry
            return results

        result: dict[str, dict[str, Any]] = await self._load_with_fallback(
            "filter_verification", load
        )
        return result

    async def _value_is_verified(
        self,
        sample: list[CPCBStationObservation],
        field: str,
        value: str | None,
        probe: str,
        canonical: str,
    ) -> bool:
        """Accept a filter value seen in the sample or confirmed by an upstream probe."""
        if not value:
            return True
        needle = value.strip().lower()
        if needle in {getattr(obs, field).strip().lower() for obs in sample}:
            return True
        verification = await self.verify_filters()
        return bool(verification.get(probe, {}).get("verified")) and needle == canonical

    async def _filter_is_verified(self, city: str | None, state: str | None) -> bool:
        """Only use upstream filters for values actually seen or probed successfully."""
        sample = await self._sample_observations()
        if not await self._value_is_verified(sample, "city", city, "city", "chennai"):
            return False
        return await self._value_is_verified(sample, "state", state, "state", "tamil nadu")

    async def get_station_observations(
        self, city: str | None = None, state: str | None = None
    ) -> list[CPCBStationObservation]:
        key = f"filter:{city or ''}:{state or ''}"

        async def load() -> list[CPCBStationObservation]:
            observations: list[CPCBStationObservation] = []
            if city or state:
                if await self._filter_is_verified(city, state):
                    filters: dict[str, str] = {}
                    if state:
                        filters["filters[state]"] = state
                    if city:
                        filters["filters[city]"] = city
                    records, _ = await self._fetch_pages(filters=filters)
                    observations = [
                        obs
                        for obs in self.parse_records(records)
                        if self._matches(obs, city, state)
                    ]
                    if not observations:
                        logger.info(
                            "CPCBAdapter: verified filter returned zero records; "
                            "falling back to bounded unfiltered pagination."
                        )
                else:
                    logger.info("CPCBAdapter: filter value not verified; using local filtering.")
            if not observations:
                observations = [
                    obs for obs in await self._all_observations() if self._matches(obs, city, state)
                ]
            return observations

        observations: list[CPCBStationObservation] = await self._load_with_fallback(key, load)
        return observations
