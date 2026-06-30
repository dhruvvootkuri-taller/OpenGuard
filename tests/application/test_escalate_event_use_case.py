"""Tests for the EscalateEventUseCase (the slow background path).

Uses in-memory fakes for every port, proving the use case depends only on
abstractions — no Celery/Redis/Twilio/Anthropic credentials required.

Covers escalation reliability: a call that is answered stops escalation; a
no-answer triggers a retry then fallback to the next contact; exhausting every
contact marks the event UNREACHABLE.
"""

import pytest

from src.application.ports.event_publisher_port import EventPublisherPort
from src.application.ports.llm_port import LLMPort
from src.application.ports.notification_port import (
    CallOutcome,
    TelephonyPort,
    VoiceMessage,
    VoiceSynthesisPort,
)
from src.application.use_cases.escalate_event_use_case import EscalateEventUseCase
from src.domain.entities.call_record import CallRecord, CallStatus
from src.domain.entities.security_event import EscalationOutcome, SecurityEvent
from src.domain.exceptions import SecurityEventNotFoundError
from src.domain.repositories.call_record_repository import CallRecordRepository
from src.domain.repositories.security_event_repository import (
    SecurityEventRepository,
)
from src.domain.value_objects.detection_box import DetectionBox
from src.domain.value_objects.threat_level import ThreatLevel, ThreatSeverity


class InMemoryRepo(SecurityEventRepository):
    def __init__(self):
        self.items: dict[str, SecurityEvent] = {}

    async def save(self, event: SecurityEvent) -> None:
        self.items[event.id] = event

    async def get_by_id(self, event_id: str):
        return self.items.get(event_id)

    async def list_recent(self, limit: int = 50):
        return list(self.items.values())[:limit]

    async def delete(self, event_id: str) -> None:
        self.items.pop(event_id, None)


class InMemoryCallRepo(CallRecordRepository):
    def __init__(self):
        self.calls: list[CallRecord] = []

    async def save(self, call: CallRecord) -> None:
        self.calls.append(call)

    async def get_by_id(self, call_id: str):
        return next((c for c in self.calls if c.id == call_id), None)

    async def get_by_event_id(self, event_id: str):
        return [c for c in self.calls if c.event_id == event_id]

    async def list_recent(self, limit: int = 50):
        return list(self.calls)[:limit]


class FakeLLM(LLMPort):
    async def summarize_incident(self, prompt: str) -> str:
        return "Intruder detected at the loading dock."


class FakeVoice(VoiceSynthesisPort):
    async def synthesize(self, text: str) -> VoiceMessage:
        return VoiceMessage(text=text, audio_url="data:audio/mpeg;base64,AAAA")


class ScriptedTelephony(TelephonyPort):
    """Telephony fake whose poll outcomes are scripted per placed call.

    ``outcomes`` is a list of terminal CallOutcomes returned in order, one per
    ``place_call``. This lets a test express "first call no-answer, second call
    answered" without any real polling.
    """

    def __init__(self, outcomes: list[CallOutcome]):
        self._outcomes = list(outcomes)
        self.calls: list[str] = []
        self._by_sid: dict[str, CallOutcome] = {}

    async def place_call(self, to_number: str, message: VoiceMessage) -> str:
        self.calls.append(to_number)
        sid = f"call-sid-{len(self.calls)}"
        outcome = self._outcomes.pop(0) if self._outcomes else CallOutcome.NO_ANSWER
        self._by_sid[sid] = outcome
        return sid

    async def poll_call_status(self, provider_call_id: str) -> CallOutcome:
        return self._by_sid[provider_call_id]

    async def send_sms(self, to_number: str, body: str) -> str:
        return "msg-sid"


class FakePublisher(EventPublisherPort):
    def __init__(self):
        self.published = []

    async def publish_event(self, event) -> None:
        self.published.append(event)


def _high_threat_event() -> SecurityEvent:
    event = SecurityEvent(
        camera_id="cam-1",
        threat_level=ThreatLevel(severity=ThreatSeverity.CRITICAL, confidence=0.95),
        detections=[
            DetectionBox(
                label="knife", confidence=0.95, x=0.1, y=0.1, width=0.2, height=0.2
            )
        ],
    )
    event.mark_analyzing()
    return event


async def _noop_sleep(_seconds: float) -> None:
    return None


def _build(repo, telephony, *, publisher=None, call_repo=None, **kwargs):
    return EscalateEventUseCase(
        repository=repo,
        llm=FakeLLM(),
        voice=FakeVoice(),
        telephony=telephony,
        publisher=publisher or FakePublisher(),
        on_call_number="+15555550199",
        call_record_repository=call_repo,
        sleep=_noop_sleep,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_answered_call_stops_escalation_and_records_reached():
    repo = InMemoryRepo()
    call_repo = InMemoryCallRepo()
    telephony = ScriptedTelephony([CallOutcome.ANSWERED])
    publisher = FakePublisher()
    event = _high_threat_event()
    await repo.save(event)

    use_case = _build(
        repo,
        telephony,
        publisher=publisher,
        call_repo=call_repo,
        on_call_numbers=["+15555550199", "+15555550200"],
        max_retries_per_contact=2,
    )

    result = await use_case.execute(event.id)

    # Only ONE call placed — answered immediately, no retry/fallback.
    assert telephony.calls == ["+15555550199"]
    assert result.status == "alerting"
    assert result.escalation_outcome == EscalationOutcome.REACHED.value
    assert result.escalation_reached_contact == "+15555550199"
    assert result.escalation_attempts == 1
    assert repo.items[event.id].escalation_outcome is EscalationOutcome.REACHED
    # A CallRecord was logged and completed.
    assert len(call_repo.calls) == 1
    assert call_repo.calls[0].status is CallStatus.COMPLETED
    assert len(publisher.published) == 1


@pytest.mark.asyncio
async def test_no_answer_retries_then_falls_back_to_next_contact():
    repo = InMemoryRepo()
    call_repo = InMemoryCallRepo()
    # Contact 1: no-answer on initial + retry. Contact 2: answered.
    telephony = ScriptedTelephony(
        [CallOutcome.NO_ANSWER, CallOutcome.NO_ANSWER, CallOutcome.ANSWERED]
    )
    event = _high_threat_event()
    await repo.save(event)

    use_case = _build(
        repo,
        telephony,
        call_repo=call_repo,
        on_call_numbers=["+15555550199", "+15555550200"],
        max_retries_per_contact=1,
    )

    result = await use_case.execute(event.id)

    # First contact dialed twice (initial + 1 retry), then fell back to second.
    assert telephony.calls == [
        "+15555550199",
        "+15555550199",
        "+15555550200",
    ]
    assert result.escalation_outcome == EscalationOutcome.REACHED.value
    assert result.escalation_reached_contact == "+15555550200"
    # Two distinct contacts attempted.
    assert result.escalation_attempts == 2
    # Three CallRecords: two failed (no-answer), one completed.
    assert len(call_repo.calls) == 3
    assert [c.status for c in call_repo.calls] == [
        CallStatus.NO_ANSWER,
        CallStatus.NO_ANSWER,
        CallStatus.COMPLETED,
    ]


@pytest.mark.asyncio
async def test_all_contacts_exhausted_marks_unreachable():
    repo = InMemoryRepo()
    call_repo = InMemoryCallRepo()
    # Every call fails to reach anyone.
    telephony = ScriptedTelephony(
        [
            CallOutcome.NO_ANSWER,
            CallOutcome.BUSY,
            CallOutcome.FAILED,
            CallOutcome.NO_ANSWER,
        ]
    )
    event = _high_threat_event()
    await repo.save(event)

    use_case = _build(
        repo,
        telephony,
        call_repo=call_repo,
        on_call_numbers=["+15555550199", "+15555550200"],
        max_retries_per_contact=1,
    )

    result = await use_case.execute(event.id)

    # Both contacts dialed twice each (initial + retry) = 4 calls.
    assert telephony.calls == [
        "+15555550199",
        "+15555550199",
        "+15555550200",
        "+15555550200",
    ]
    assert result.escalation_outcome == EscalationOutcome.UNREACHABLE.value
    assert result.escalation_reached_contact is None
    assert result.escalation_attempts == 2
    assert repo.items[event.id].escalation_outcome is EscalationOutcome.UNREACHABLE
    assert len(call_repo.calls) == 4


@pytest.mark.asyncio
async def test_single_contact_default_still_calls():
    """Back-compat: with no ordered list, the legacy on_call_number is used."""
    repo = InMemoryRepo()
    telephony = ScriptedTelephony([CallOutcome.ANSWERED])
    event = _high_threat_event()
    await repo.save(event)

    use_case = _build(repo, telephony)  # no on_call_numbers override

    result = await use_case.execute(event.id)

    assert telephony.calls == ["+15555550199"]
    assert result.escalation_outcome == EscalationOutcome.REACHED.value


@pytest.mark.asyncio
async def test_escalation_missing_event_raises():
    use_case = _build(InMemoryRepo(), ScriptedTelephony([CallOutcome.ANSWERED]))

    with pytest.raises(SecurityEventNotFoundError):
        await use_case.execute("does-not-exist")
