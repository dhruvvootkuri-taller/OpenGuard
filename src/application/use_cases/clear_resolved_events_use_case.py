"""Use Case: Clear resolved/dismissed events.

A supported reset path so a demo/test run can be wiped without manual Redis
surgery. By default it removes only terminal (resolved/dismissed) events,
keeping active incidents untouched. ``include_active=True`` performs a full
reset of every event the recency index knows about.
"""

from __future__ import annotations

from src.application.dtos.detection_dtos import ClearResolvedOutputDTO
from src.domain.repositories.security_event_repository import (
    SecurityEventRepository,
)


class ClearResolvedEventsUseCase:
    def __init__(self, repository: SecurityEventRepository) -> None:
        self._repository = repository

    async def execute(self, include_active: bool = False) -> ClearResolvedOutputDTO:
        # Pull a generous window so a demo's full backlog is covered.
        events = await self._repository.list_recent(limit=1000)
        cleared = 0
        for event in events:
            if include_active or event.is_terminal():
                await self._repository.delete(event.id)
                cleared += 1
        return ClearResolvedOutputDTO(cleared=cleared)
