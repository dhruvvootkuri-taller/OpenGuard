"""Use Case: Acknowledge a security event."""

from __future__ import annotations

from src.application.dtos.detection_dtos import (
    AcknowledgeEventInputDTO,
    SecurityEventDTO,
)
from src.application.mappers.security_event_mapper import SecurityEventMapper
from src.application.ports.active_emergency_tracker_port import (
    ActiveEmergencyTrackerPort,
)
from src.domain.exceptions import SecurityEventNotFoundError
from src.domain.repositories.security_event_repository import (
    SecurityEventRepository,
)


class AcknowledgeEventUseCase:
    def __init__(
        self,
        repository: SecurityEventRepository,
        active_tracker: ActiveEmergencyTrackerPort,
    ) -> None:
        self._repository = repository
        self._active_tracker = active_tracker

    async def execute(self, dto: AcknowledgeEventInputDTO) -> SecurityEventDTO:
        event = await self._repository.get_by_id(dto.event_id)
        if event is None:
            raise SecurityEventNotFoundError(dto.event_id)

        # State transition is enforced by the domain entity.
        event.acknowledge(dto.operator_id)
        await self._repository.save(event)

        # Acknowledging ends the incident: clear the active marker so a new
        # incident on this camera is allowed immediately (before cooldown).
        await self._active_tracker.clear(event.camera_id)
        return SecurityEventMapper.to_dto(event)
