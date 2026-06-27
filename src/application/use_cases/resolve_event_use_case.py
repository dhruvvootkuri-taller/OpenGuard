"""Use Case: Resolve a security event.

Resolving marks an incident as handled and drops it from the active views.
Escalated events remain in Call History as an audit trail (the frontend keeps
showing escalated-and-resolved events there); non-escalated one-offs simply
fall off the live panels.
"""

from __future__ import annotations

from src.application.dtos.detection_dtos import (
    ResolveEventInputDTO,
    SecurityEventDTO,
)
from src.application.mappers.security_event_mapper import SecurityEventMapper
from src.domain.exceptions import SecurityEventNotFoundError
from src.domain.repositories.security_event_repository import (
    SecurityEventRepository,
)


class ResolveEventUseCase:
    def __init__(self, repository: SecurityEventRepository) -> None:
        self._repository = repository

    async def execute(self, dto: ResolveEventInputDTO) -> SecurityEventDTO:
        event = await self._repository.get_by_id(dto.event_id)
        if event is None:
            raise SecurityEventNotFoundError(dto.event_id)

        # Idempotent: resolving an already-resolved event is a no-op.
        if event.is_active():
            event.resolve()
            await self._repository.save(event)
        return SecurityEventMapper.to_dto(event)
