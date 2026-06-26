"""Repository interface for FeedClip persistence.

Abstraction only — implementations (Redis, etc.) live in infrastructure.
Stores recorded MP4 clips and their timed descriptions so the voice agent
can retrieve exactly what was happening at a given moment.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.feed_clip import FeedClip


class FeedClipRepository(ABC):
    """Persistence contract for recorded feed clips."""

    @abstractmethod
    async def save(self, clip: FeedClip) -> None:
        """Persist (create or update) a feed clip."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, clip_id: str) -> FeedClip | None:
        """Return a single clip by id, or None if it does not exist."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_event_id(self, event_id: str) -> list[FeedClip]:
        """Return all clips recorded for a given security event."""
        raise NotImplementedError

    @abstractmethod
    async def list_recent(self, limit: int = 50) -> list[FeedClip]:
        """Return the most recent clips, newest first."""
        raise NotImplementedError
