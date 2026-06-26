"""Repository interface for CallRecord persistence.

Abstraction only — implementations (Redis, etc.) live in infrastructure.
Backs the call-history log the dashboard and audits read from.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.call_record import CallRecord


class CallRecordRepository(ABC):
    """Persistence contract for outbound call history."""

    @abstractmethod
    async def save(self, call: CallRecord) -> None:
        """Persist (create or update) a call record."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, call_id: str) -> CallRecord | None:
        """Return a single call by id, or None if it does not exist."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_event_id(self, event_id: str) -> list[CallRecord]:
        """Return all calls placed for a given security event."""
        raise NotImplementedError

    @abstractmethod
    async def list_recent(self, limit: int = 50) -> list[CallRecord]:
        """Return the most recent calls, newest first."""
        raise NotImplementedError
