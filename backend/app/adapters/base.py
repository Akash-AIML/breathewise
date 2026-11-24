from abc import ABC, abstractmethod
from typing import List, Optional

from app.schemas.observation import NormalizedObservation, StationMetadata


class AirQualityAdapter(ABC):
    """Abstract Base Class for all Air Quality Data Adapters."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier of the provider (e.g., 'cpcb_ogd', 'openaq', 'openmeteo')."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""
        pass

    @abstractmethod
    async def fetch_by_coordinates(
        self, latitude: float, longitude: float
    ) -> Optional[NormalizedObservation]:
        """Fetch observations for given geographic coordinates."""
        pass

    @abstractmethod
    async def search_stations(
        self, city: Optional[str] = None, state: Optional[str] = None
    ) -> List[StationMetadata]:
        """Search available monitoring stations by city or state."""
        pass
