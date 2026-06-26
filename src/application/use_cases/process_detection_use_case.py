"""Use Case: Process an incoming camera detection.

Orchestration only. All business rules live in the domain layer
(ThreatAssessmentService + SecurityEvent invariants).

The fast path (assess + persist + publish) runs inline. The slow,
side-effectful escalation work (LLM summary, ElevenLabs voice synthesis,
Twilio call) is offloaded to a background worker through the
``TaskQueuePort`` — implemented with Celery in infrastructure.
"""

from __future__ import annotations

from src.application.dtos.detection_dtos import (
    ProcessDetectionInputDTO,
    SecurityEventDTO,
)
from src.application.mappers.security_event_mapper import SecurityEventMapper
from src.application.ports.event_publisher_port import EventPublisherPort
from src.application.ports.task_queue_port import TaskQueuePort
from src.domain.entities.security_event import SecurityEvent
from src.domain.repositories.security_event_repository import (
    SecurityEventRepository,
)
from src.domain.services.threat_assessment_service import ThreatAssessmentService
from src.domain.value_objects.detection_box import DetectionBox


class ProcessDetectionUseCase:
    """Turn a raw detection into an assessed, persisted, possibly-escalated event."""

    def __init__(
        self,
        repository: SecurityEventRepository,
        threat_service: ThreatAssessmentService,
        publisher: EventPublisherPort,
        task_queue: TaskQueuePort,
    ) -> None:
        self._repository = repository
        self._threat_service = threat_service
        self._publisher = publisher
        self._task_queue = task_queue

    async def execute(self, dto: ProcessDetectionInputDTO) -> SecurityEventDTO:
        # 1. Build domain value objects from the input DTO.
        detections = [
            DetectionBox(
                label=d.label,
                confidence=d.confidence,
                x=d.x,
                y=d.y,
                width=d.width,
                height=d.height,
            )
            for d in dto.detections
        ]

        # 2. Assess the threat using a domain service (pure business logic).
        threat_level = self._threat_service.assess(
            detections=detections, is_armed_zone=dto.is_armed_zone
        )

        # 3. Create the domain entity (protects its own invariants).
        event = SecurityEvent(
            camera_id=dto.camera_id,
            threat_level=threat_level,
            detections=detections,
            description=dto.description,
        )
        event.mark_analyzing()

        # 4. Persist immediately so the event is durable before any slow work.
        await self._repository.save(event)
        result = SecurityEventMapper.to_dto(event)
        await self._publisher.publish_event(result)

        # 5. Offload escalation (LLM + voice + call) to the background worker
        #    when the domain decides a human must be alerted.
        if event.requires_human_escalation():
            self._task_queue.enqueue_escalation(event.id)

        return result
