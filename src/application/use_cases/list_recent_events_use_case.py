"""Use Case: List the most recent security events."""

from __future__ import annotations

from src.application.dtos.detection_dtos import SecurityEventDTO
from src.application.mappers.security_event_mapper import SecurityEventMapper
from src.domain.repositories.security_event_repository import (
    SecurityEventRepository,
)


class ListRecentEventsUseCase:
    def __init__(self, repository: SecurityEventRepository) -> None:
        self._repository = repository

    async def execute(self, limit: int = 50) -> list[SecurityEventDTO]:
        events = await self._repository.list_recent(limit=limit)
        return [SecurityEventMapper.to_dto(e) for e in events]
