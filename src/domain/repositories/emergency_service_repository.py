"""Repository interface for EmergencyService persistence.

Abstraction only — implementations (Redis, etc.) live in infrastructure.
Users add/maintain services through this contract and the voice agent reads
the active catalogue from it to decide who to call.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.emergency_service import EmergencyService


class EmergencyServiceRepository(ABC):
    """Persistence contract for emergency services / helplines."""

    @abstractmethod
    async def save(self, service: EmergencyService) -> None:
        """Persist (create or update) an emergency service."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, service_id: str) -> EmergencyService | None:
        """Return a single service by id, or None if it does not exist."""
        raise NotImplementedError

    @abstractmethod
    async def list_all(self) -> list[EmergencyService]:
        """Return every service, ordered by priority (try-first first)."""
        raise NotImplementedError

    @abstractmethod
    async def list_active(self) -> list[EmergencyService]:
        """Return only active services, ordered by priority."""
        raise NotImplementedError

    @abstractmethod
    async def delete(self, service_id: str) -> None:
        """Remove a service from the catalogue."""
        raise NotImplementedError
