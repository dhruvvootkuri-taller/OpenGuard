"""HTTP controller for security events.

Thin: validate input -> call use case -> serialize output.
Imports only from the application layer (use cases + DTOs) and the
web framework. Never touches domain entities or infrastructure directly.
"""

from __future__ import annotations

import dataclasses

from fastapi import APIRouter, HTTPException

from src.application.dtos.detection_dtos import (
    AcknowledgeEventInputDTO,
    DetectionBoxDTO,
    ProcessDetectionInputDTO,
)
from src.application.use_cases.acknowledge_event_use_case import (
    AcknowledgeEventUseCase,
)
from src.application.use_cases.list_recent_events_use_case import (
    ListRecentEventsUseCase,
)
from src.application.use_cases.process_detection_use_case import (
    ProcessDetectionUseCase,
)
from src.interfaces.http.schemas import (
    AcknowledgeRequest,
    ProcessDetectionRequest,
    SecurityEventResponse,
)


class SecurityEventController:
    """Wires use cases into FastAPI routes."""

    def __init__(
        self,
        process_detection: ProcessDetectionUseCase,
        acknowledge_event: AcknowledgeEventUseCase,
        list_recent_events: ListRecentEventsUseCase,
    ) -> None:
        self._process_detection = process_detection
        self._acknowledge_event = acknowledge_event
        self._list_recent_events = list_recent_events
        self.router = APIRouter(prefix="/api/events", tags=["events"])
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            "", self.create_event, methods=["POST"],
            response_model=SecurityEventResponse, status_code=201,
        )
        self.router.add_api_route(
            "", self.list_events, methods=["GET"],
            response_model=list[SecurityEventResponse],
        )
        self.router.add_api_route(
            "/{event_id}/acknowledge", self.acknowledge, methods=["POST"],
            response_model=SecurityEventResponse,
        )

    async def create_event(
        self, request: ProcessDetectionRequest
    ) -> SecurityEventResponse:
        dto = ProcessDetectionInputDTO(
            camera_id=request.camera_id,
            detections=[
                DetectionBoxDTO(**d.model_dump()) for d in request.detections
            ],
            is_armed_zone=request.is_armed_zone,
            description=request.description,
        )
        result = await self._process_detection.execute(dto)
        return SecurityEventResponse(**dataclasses.asdict(result))

    async def list_events(self, limit: int = 50) -> list[SecurityEventResponse]:
        results = await self._list_recent_events.execute(limit=limit)
        return [SecurityEventResponse(**dataclasses.asdict(r)) for r in results]

    async def acknowledge(
        self, event_id: str, request: AcknowledgeRequest
    ) -> SecurityEventResponse:
        try:
            result = await self._acknowledge_event.execute(
                AcknowledgeEventInputDTO(
                    event_id=event_id, operator_id=request.operator_id
                )
            )
        except Exception as exc:  # noqa: BLE001
            # Map application/domain errors to HTTP status codes here.
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return SecurityEventResponse(**dataclasses.asdict(result))
