"""Repository interface for SecurityEvent persistence.

This is an ABSTRACTION (the "what"). Implementations live in infrastructure.
The domain layer never knows whether this is backed by Redis, Postgres, etc.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.security_event import SecurityEvent


class SecurityEventRepository(ABC):
    """Persistence contract for security events."""

    @abstractmethod
    async def save(self, event: SecurityEvent) -> None:
        """Persist (create or update) a security event."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, event_id: str) -> SecurityEvent | None:
        """Return a single event by id, or None if it does not exist."""
        raise NotImplementedError

    @abstractmethod
    async def list_recent(self, limit: int = 50) -> list[SecurityEvent]:
        """Return the most recent events, newest first."""
        raise NotImplementedError

    @abstractmethod
    async def delete(self, event_id: str) -> None:
        """Remove an event entirely (used by the supported 'clear' path)."""
        raise NotImplementedError
