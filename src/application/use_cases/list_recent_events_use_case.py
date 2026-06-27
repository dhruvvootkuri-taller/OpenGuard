"""Use Case: List the most recent security events.

This is also where stale active events are lazily auto-expired: any event that
has not seen a new frame/detection for longer than the configured inactivity
TTL is auto-resolved before the list is returned. Running it here means the
dashboard poll keeps the active views fresh without a separate scheduler.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.application.dtos.detection_dtos import SecurityEventDTO
from src.application.mappers.security_event_mapper import SecurityEventMapper
from src.domain.repositories.security_event_repository import (
    SecurityEventRepository,
)


class ListRecentEventsUseCase:
    def __init__(
        self,
        repository: SecurityEventRepository,
        inactivity_ttl_seconds: int = 0,
    ) -> None:
        self._repository = repository
        self._inactivity_ttl_seconds = inactivity_ttl_seconds

    async def execute(self, limit: int = 50) -> list[SecurityEventDTO]:
        events = await self._repository.list_recent(limit=limit)
        if self._inactivity_ttl_seconds > 0:
            now = datetime.now(timezone.utc)
            for event in events:
                if event.is_stale(
                    now=now, ttl_seconds=self._inactivity_ttl_seconds
                ):
                    event.expire()
                    # Best-effort: persist the auto-resolution so it sticks.
                    try:
                        await self._repository.save(event)
                    except Exception:  # noqa: BLE001
                        # A failed write must never break the dashboard poll.
                        pass
        return [SecurityEventMapper.to_dto(e) for e in events]
