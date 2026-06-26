"""Use Case: Escalate a security event to an on-call human.

This is the slow, side-effectful part of the pipeline (LLM summary + voice
synthesis + outbound phone call). It is designed to be executed *out of band*
by a background worker (Celery) so the request path stays fast.

Orchestration only — escalation rules live in the domain entity
(`SecurityEvent.requires_human_escalation`).
"""

from __future__ import annotations

from src.application.dtos.detection_dtos import SecurityEventDTO
from src.application.mappers.security_event_mapper import SecurityEventMapper
from src.application.ports.event_publisher_port import EventPublisherPort
from src.application.ports.llm_port import LLMPort
from src.application.ports.notification_port import (
    TelephonyPort,
    VoiceSynthesisPort,
)
from src.domain.exceptions import SecurityEventNotFoundError
from src.domain.repositories.security_event_repository import (
    SecurityEventRepository,
)


class EscalateEventUseCase:
    """Summarize, synthesize, call, persist and publish an escalated event."""

    def __init__(
        self,
        repository: SecurityEventRepository,
        llm: LLMPort,
        voice: VoiceSynthesisPort,
        telephony: TelephonyPort,
        publisher: EventPublisherPort,
        on_call_number: str,
    ) -> None:
        self._repository = repository
        self._llm = llm
        self._voice = voice
        self._telephony = telephony
        self._publisher = publisher
        self._on_call_number = on_call_number

    async def execute(self, event_id: str) -> SecurityEventDTO:
        event = await self._repository.get_by_id(event_id)
        if event is None:
            raise SecurityEventNotFoundError(event_id)

        # Enrich with an LLM-generated incident summary (infra via port).
        labels = ", ".join(sorted({d.label for d in event.detections}))
        summary = await self._llm.summarize_incident(
            prompt=(
                f"Camera {event.camera_id} detected: {labels}. "
                f"Threat level: {event.threat_level}. "
                "Write a one-sentence incident summary for a security operator."
            )
        )
        event.description = summary or event.description

        # Only escalate to a human when the domain says we must.
        if event.requires_human_escalation():
            event.mark_alerting()
            voice_message = await self._voice.synthesize(
                f"Open Guard alert. {event.description}"
            )
            await self._telephony.place_call(self._on_call_number, voice_message)

        await self._repository.save(event)
        result = SecurityEventMapper.to_dto(event)
        await self._publisher.publish_event(result)
        return result
