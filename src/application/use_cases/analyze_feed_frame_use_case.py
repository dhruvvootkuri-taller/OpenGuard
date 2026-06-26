"""Use Case: Analyze a single camera-feed frame for an emergency.

Orchestration only. The decision of *whether* a frame is an emergency is
delegated to the VisionAnalyzerPort (Anthropic Claude vision in
infrastructure). The decision of *how severe* a confirmed emergency is stays
in the domain (ThreatAssessmentService + SecurityEvent invariants).

Real-time contract: each frame is analysed independently as it arrives, so
the caller (a playing MP4 feed) never has to wait for the whole clip. When no
emergency is present the use case persists nothing and returns a result whose
``event`` is None — the feed simply carries on.
"""

from __future__ import annotations

from src.application.dtos.detection_dtos import (
    AnalyzeFeedFrameInputDTO,
    AnalyzeFeedFrameResultDTO,
)
from src.application.mappers.security_event_mapper import SecurityEventMapper
from src.application.ports.event_publisher_port import EventPublisherPort
from src.application.ports.task_queue_port import TaskQueuePort
from src.application.ports.vision_analyzer_port import VisionAnalyzerPort
from src.domain.entities.security_event import SecurityEvent
from src.domain.repositories.security_event_repository import (
    SecurityEventRepository,
)
from src.domain.services.threat_assessment_service import ThreatAssessmentService
from src.domain.value_objects.detection_box import DetectionBox
from src.domain.value_objects.threat_level import ThreatLevel


class AnalyzeFeedFrameUseCase:
    """Turn one MP4 frame into a SecurityEvent — but only on a real emergency."""

    def __init__(
        self,
        analyzer: VisionAnalyzerPort,
        repository: SecurityEventRepository,
        threat_service: ThreatAssessmentService,
        publisher: EventPublisherPort,
        task_queue: TaskQueuePort,
    ) -> None:
        self._analyzer = analyzer
        self._repository = repository
        self._threat_service = threat_service
        self._publisher = publisher
        self._task_queue = task_queue

    async def execute(
        self, dto: AnalyzeFeedFrameInputDTO
    ) -> AnalyzeFeedFrameResultDTO:
        # 1. Ask the vision analyser whether this frame shows an emergency.
        context = (
            f"Camera {dto.camera_id}"
            + (f" in zone '{dto.zone}'" if dto.zone else "")
            + (" (armed/restricted zone)" if dto.is_armed_zone else "")
        )
        assessment = await self._analyzer.analyze_frame(
            image_base64=dto.image_base64,
            media_type=dto.media_type,
            context=context,
        )

        # 2. No emergency -> do nothing. The live feed continues uninterrupted.
        if not assessment.is_emergency:
            return AnalyzeFeedFrameResultDTO(
                camera_id=dto.camera_id,
                is_emergency=False,
                label=assessment.label,
                summary=assessment.summary,
                event=None,
            )

        # 3. Confirmed emergency -> build a domain detection from the assessment.
        detection = DetectionBox(
            label=assessment.label,
            confidence=assessment.confidence,
            x=assessment.x,
            y=assessment.y,
            width=assessment.width,
            height=assessment.height,
        )

        # 4. Severity is a domain decision. We seed it with the analyser's
        #    score so a clearly dangerous situation is treated as such, then
        #    let the domain service amplify for armed zones / weapons.
        assessed = self._threat_service.assess(
            detections=[detection], is_armed_zone=dto.is_armed_zone
        )
        vision_level = ThreatLevel.from_score(
            score=assessment.score, confidence=assessment.confidence
        )
        threat_level = (
            assessed
            if assessed.severity >= vision_level.severity
            else vision_level
        )

        # 5. Create, persist and publish the event immediately (durable first).
        event = SecurityEvent(
            camera_id=dto.camera_id,
            threat_level=threat_level,
            detections=[detection],
            description=assessment.summary or f"Emergency detected: {assessment.label}",
        )
        event.mark_analyzing()

        await self._repository.save(event)
        event_dto = SecurityEventMapper.to_dto(event)
        await self._publisher.publish_event(event_dto)

        # 6. Offload escalation (LLM summary + voice + call) when the domain
        #    decides a human must be alerted.
        if event.requires_human_escalation():
            self._task_queue.enqueue_escalation(event.id)

        return AnalyzeFeedFrameResultDTO(
            camera_id=dto.camera_id,
            is_emergency=True,
            label=assessment.label,
            summary=event.description,
            event=event_dto,
        )
