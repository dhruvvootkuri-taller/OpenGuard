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
    AnalyzeFrameInputDTO,
    DetectionBoxDTO,
    ProcessDetectionInputDTO,
    ResolveEventInputDTO,
)
from src.application.ports.vision_analyzer_port import VisionAnalyzerError
from src.application.use_cases.acknowledge_event_use_case import (
    AcknowledgeEventUseCase,
)
from src.application.use_cases.analyze_feed_frame_use_case import (
    AnalyzeFeedFrameUseCase,
)
from src.application.use_cases.clear_resolved_events_use_case import (
    ClearResolvedEventsUseCase,
)
from src.application.use_cases.dismiss_event_use_case import (
    DismissEventUseCase,
)
from src.application.use_cases.list_recent_events_use_case import (
    ListRecentEventsUseCase,
)
from src.application.use_cases.process_detection_use_case import (
    ProcessDetectionUseCase,
)
from src.application.use_cases.resolve_event_use_case import (
    ResolveEventUseCase,
)
from src.interfaces.http.schemas import (
    AcknowledgeRequest,
    AnalyzeFrameRequest,
    AnalyzeFrameResponse,
    ClearResolvedRequest,
    ClearResolvedResponse,
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
        analyze_feed_frame: AnalyzeFeedFrameUseCase,
        resolve_event: ResolveEventUseCase,
        dismiss_event: DismissEventUseCase,
        clear_resolved_events: ClearResolvedEventsUseCase,
    ) -> None:
        self._process_detection = process_detection
        self._acknowledge_event = acknowledge_event
        self._list_recent_events = list_recent_events
        self._analyze_feed_frame = analyze_feed_frame
        self._resolve_event = resolve_event
        self._dismiss_event = dismiss_event
        self._clear_resolved_events = clear_resolved_events
        self.router = APIRouter(prefix="/api/events", tags=["events"])
        # Feed-frame analysis lives under its own /api/feeds prefix.
        self.feeds_router = APIRouter(prefix="/api/feeds", tags=["feeds"])
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
        self.router.add_api_route(
            "/{event_id}/resolve", self.resolve, methods=["POST"],
            response_model=SecurityEventResponse,
        )
        self.router.add_api_route(
            "/{event_id}/dismiss", self.dismiss, methods=["POST"],
            response_model=SecurityEventResponse,
        )
        self.router.add_api_route(
            "/clear-resolved", self.clear_resolved, methods=["POST"],
            response_model=ClearResolvedResponse,
        )
        self.feeds_router.add_api_route(
            "/{camera_id}/frame", self.analyze_frame, methods=["POST"],
            response_model=AnalyzeFrameResponse,
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

    async def analyze_frame(
        self, camera_id: str, request: AnalyzeFrameRequest
    ) -> AnalyzeFrameResponse:
        try:
            result = await self._analyze_feed_frame.execute(
                AnalyzeFrameInputDTO(
                    camera_id=camera_id,
                    image_base64=request.image_base64,
                    media_type=request.media_type,
                    is_armed_zone=request.is_armed_zone,
                    zone=request.zone,
                )
            )
        except VisionAnalyzerError as exc:
            # Surface vision/provider failures (bad key, retired model) as a
            # 502 — never silently report "all clear".
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        event = (
            SecurityEventResponse(**dataclasses.asdict(result.event))
            if result.event is not None
            else None
        )
        return AnalyzeFrameResponse(
            camera_id=result.camera_id,
            is_emergency=result.is_emergency,
            label=result.label,
            summary=result.summary,
            event=event,
            is_candidate=result.is_candidate,
            candidate_reason=result.candidate_reason,
            is_throttled=result.is_throttled,
            throttle_state=result.throttle_state,
            throttle_reason=result.throttle_reason,
        )

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

    async def resolve(self, event_id: str) -> SecurityEventResponse:
        try:
            result = await self._resolve_event.execute(
                ResolveEventInputDTO(event_id=event_id)
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return SecurityEventResponse(**dataclasses.asdict(result))

    async def dismiss(self, event_id: str) -> SecurityEventResponse:
        try:
            result = await self._dismiss_event.execute(
                ResolveEventInputDTO(event_id=event_id)
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return SecurityEventResponse(**dataclasses.asdict(result))

    async def clear_resolved(
        self, request: ClearResolvedRequest | None = None
    ) -> ClearResolvedResponse:
        include_active = request.include_active if request is not None else False
        result = await self._clear_resolved_events.execute(
            include_active=include_active
        )
        return ClearResolvedResponse(cleared=result.cleared)
