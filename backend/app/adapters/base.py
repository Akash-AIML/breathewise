from abc import ABC, abstractmethod

from app.schemas.observation import NormalizedObservation, StationMetadata


class AirQualityAdapter(ABC):
    """Abstract Base Class for all Air Quality Data Adapters."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier of the provider (e.g., 'cpcb_ogd', 'openaq', 'openmeteo')."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""

    @abstractmethod
    async def fetch_by_coordinates(
        self, latitude: float, longitude: float
    ) -> NormalizedObservation | None:
        """Fetch observations for given geographic coordinates."""

    @abstractmethod
    async def search_stations(
        self, city: str | None = None, state: str | None = None
    ) -> list[StationMetadata]:
        """Search available monitoring stations by city or state."""
