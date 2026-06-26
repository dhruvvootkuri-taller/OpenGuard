"""Use Case: Process an incoming camera detection.

Orchestration only. All business rules live in the domain layer
(ThreatAssessmentService + SecurityEvent invariants).
"""

from __future__ import annotations

from src.application.dtos.detection_dtos import (
    ProcessDetectionInputDTO,
    SecurityEventDTO,
)
from src.application.mappers.security_event_mapper import SecurityEventMapper
from src.application.ports.event_publisher_port import EventPublisherPort
from src.application.ports.llm_port import LLMPort
from src.application.ports.notification_port import (
    TelephonyPort,
    VoiceSynthesisPort,
)
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
        llm: LLMPort,
        voice: VoiceSynthesisPort,
        telephony: TelephonyPort,
        publisher: EventPublisherPort,
        on_call_number: str,
    ) -> None:
        self._repository = repository
        self._threat_service = threat_service
        self._llm = llm
        self._voice = voice
        self._telephony = telephony
        self._publisher = publisher
        self._on_call_number = on_call_number

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

        # 4. Enrich with an LLM-generated incident summary (infra via port).
        labels = ", ".join(sorted({d.label for d in detections}))
        summary = await self._llm.summarize_incident(
            prompt=(
                f"Camera {dto.camera_id} detected: {labels}. "
                f"Threat level: {threat_level}. "
                f"Armed zone: {dto.is_armed_zone}. "
                "Write a one-sentence incident summary for a security operator."
            )
        )
        event.description = summary or event.description

        # 5. Escalate if the domain says we must.
        if event.requires_human_escalation():
            event.mark_alerting()
            voice_message = await self._voice.synthesize(
                f"Open Guard alert. {summary}"
            )
            await self._telephony.place_call(self._on_call_number, voice_message)

        # 6. Persist and publish.
        await self._repository.save(event)
        result = SecurityEventMapper.to_dto(event)
        await self._publisher.publish_event(result)
        return result
