"""Use Case: Escalate a security event to an on-call human.

This is the slow, side-effectful part of the pipeline (LLM summary + voice
synthesis + outbound phone call). It is designed to be executed *out of band*
by a background worker (Celery) so the request path stays fast.

Escalation must be *reliable*: a single unanswered call is not enough for an
emergency system. This use case places a call to the first on-call contact,
polls the telephony provider for the outcome and — if the call is not answered
within a timeout — retries the same contact and then falls back to the next
contact in an ordered, configurable on-call list. The final outcome (REACHED
vs UNREACHABLE) is recorded on the event and a CallRecord is persisted per
attempt for the dashboard's Call History.

Orchestration only — escalation rules live in the domain entity
(`SecurityEvent.requires_human_escalation`).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence

from src.application.dtos.detection_dtos import SecurityEventDTO
from src.application.mappers.security_event_mapper import SecurityEventMapper
from src.application.ports.event_publisher_port import EventPublisherPort
from src.application.ports.llm_port import LLMPort
from src.application.ports.notification_port import (
    CallOutcome,
    TelephonyPort,
    VoiceMessage,
    VoiceSynthesisPort,
)
from src.domain.entities.call_record import CallRecord, CallStatus
from src.domain.exceptions import SecurityEventNotFoundError
from src.domain.repositories.call_record_repository import CallRecordRepository
from src.domain.repositories.security_event_repository import (
    SecurityEventRepository,
)


class EscalateEventUseCase:
    """Summarize, synthesize, call (with retry/fallback), persist and publish."""

    def __init__(
        self,
        repository: SecurityEventRepository,
        llm: LLMPort,
        voice: VoiceSynthesisPort,
        telephony: TelephonyPort,
        publisher: EventPublisherPort,
        on_call_number: str,
        *,
        call_record_repository: CallRecordRepository | None = None,
        on_call_numbers: Sequence[str] | None = None,
        max_retries_per_contact: int = 1,
        answer_timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 2.0,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._repository = repository
        self._llm = llm
        self._voice = voice
        self._telephony = telephony
        self._publisher = publisher
        self._call_record_repository = call_record_repository
        # Ordered on-call list; defaults to the single legacy on_call_number so
        # existing single-contact deployments keep working unchanged.
        contacts = [c for c in (on_call_numbers or []) if c and c.strip()]
        if not contacts and on_call_number and on_call_number.strip():
            contacts = [on_call_number]
        self._contacts: list[str] = contacts
        self._max_retries_per_contact = max(0, max_retries_per_contact)
        self._answer_timeout_seconds = max(0.0, answer_timeout_seconds)
        self._poll_interval_seconds = max(0.0, poll_interval_seconds)
        self._sleep = sleep or asyncio.sleep

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
        if event.requires_human_escalation() and self._contacts:
            event.mark_alerting()
            voice_message = await self._voice.synthesize(
                f"Open Guard alert. {event.description}"
            )
            await self._escalate_with_retry_fallback(event, voice_message)

        await self._repository.save(event)
        result = SecurityEventMapper.to_dto(event)
        await self._publisher.publish_event(result)
        return result

    async def _escalate_with_retry_fallback(
        self, event, voice_message: VoiceMessage
    ) -> None:
        """Try each contact (with retries) until one is reached or all fail.

        Records the final outcome on ``event`` and persists a CallRecord per
        attempt so the dashboard's Call History reflects what happened.
        """
        attempts = 0
        for contact in self._contacts:
            attempts += 1
            # One contact = its initial call + up to N retries.
            for _ in range(self._max_retries_per_contact + 1):
                outcome = await self._place_and_await_outcome(
                    event_id=event.id,
                    contact=contact,
                    voice_message=voice_message,
                )
                if outcome.reached():
                    event.record_escalation_reached(contact, attempts=attempts)
                    return

        # Every contact tried and none answered.
        event.record_escalation_unreachable(attempts=max(attempts, 1))

    async def _place_and_await_outcome(
        self, *, event_id: str, contact: str, voice_message: VoiceMessage
    ) -> CallOutcome:
        """Place a call, persist a CallRecord and poll until a terminal outcome."""
        call_record = CallRecord(
            to_number=contact,
            transcript=voice_message.text,
            event_id=event_id,
        )
        try:
            provider_call_id = await self._telephony.place_call(
                contact, voice_message
            )
        except Exception:  # noqa: BLE001 — a failed dial is a failed attempt.
            call_record.fail(CallStatus.FAILED)
            await self._persist_call(call_record)
            return CallOutcome.FAILED

        call_record.provider_call_id = provider_call_id
        outcome = await self._poll_until_terminal(provider_call_id)
        self._apply_outcome_to_record(call_record, outcome)
        await self._persist_call(call_record)
        return outcome

    async def _poll_until_terminal(self, provider_call_id: str) -> CallOutcome:
        """Poll the provider until a terminal outcome or the answer timeout."""
        elapsed = 0.0
        while True:
            try:
                outcome = await self._telephony.poll_call_status(provider_call_id)
            except Exception:  # noqa: BLE001 — treat polling failure as failed call.
                return CallOutcome.FAILED
            if outcome.is_terminal():
                return outcome
            if elapsed >= self._answer_timeout_seconds:
                # Rang past the timeout without being answered.
                return CallOutcome.NO_ANSWER
            await self._sleep(self._poll_interval_seconds)
            elapsed += self._poll_interval_seconds

    @staticmethod
    def _apply_outcome_to_record(
        call_record: CallRecord, outcome: CallOutcome
    ) -> None:
        if outcome.reached():
            call_record.complete(duration_seconds=0.0)
        elif outcome is CallOutcome.NO_ANSWER:
            call_record.fail(CallStatus.NO_ANSWER)
        else:
            call_record.fail(CallStatus.FAILED)

    async def _persist_call(self, call_record: CallRecord) -> None:
        if self._call_record_repository is not None:
            await self._call_record_repository.save(call_record)
