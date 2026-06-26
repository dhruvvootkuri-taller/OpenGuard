"""Port for publishing events to subscribers (e.g. Redis pub/sub)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.application.dtos.detection_dtos import SecurityEventDTO


class EventPublisherPort(ABC):
    """Abstraction over a real-time event bus (implemented with Redis)."""

    @abstractmethod
    async def publish_event(self, event: SecurityEventDTO) -> None:
        """Publish a security event to interested subscribers."""
        raise NotImplementedError
