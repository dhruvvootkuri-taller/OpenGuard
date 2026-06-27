"""Use Case: Dismiss a security event.

Dismissing flags an event as a non-incident (false positive / noise) and drops
it from every active view. Unlike resolve, a dismissed event is never treated
as audit-trail history.
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


class DismissEventUseCase:
    def __init__(self, repository: SecurityEventRepository) -> None:
        self._repository = repository

    async def execute(self, dto: ResolveEventInputDTO) -> SecurityEventDTO:
        event = await self._repository.get_by_id(dto.event_id)
        if event is None:
            raise SecurityEventNotFoundError(dto.event_id)

        if event.is_active():
            event.dismiss()
            await self._repository.save(event)
        return SecurityEventMapper.to_dto(event)
