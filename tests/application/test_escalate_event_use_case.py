"""Tests for the EscalateEventUseCase (the slow background path).

Uses in-memory fakes for every port, proving the use case depends only on
abstractions — no Celery/Redis/Twilio/Anthropic credentials required.
"""

import pytest

from src.application.ports.event_publisher_port import EventPublisherPort
from src.application.ports.llm_port import LLMPort
from src.application.ports.notification_port import (
    TelephonyPort,
    VoiceMessage,
    VoiceSynthesisPort,
)
from src.application.use_cases.escalate_event_use_case import EscalateEventUseCase
from src.domain.entities.security_event import SecurityEvent
from src.domain.exceptions import SecurityEventNotFoundError
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


class FakeLLM(LLMPort):
    async def summarize_incident(self, prompt: str) -> str:
        return "Intruder detected at the loading dock."


class FakeVoice(VoiceSynthesisPort):
    async def synthesize(self, text: str) -> VoiceMessage:
        return VoiceMessage(text=text, audio_url="data:audio/mpeg;base64,AAAA")


class FakeTelephony(TelephonyPort):
    def __init__(self):
        self.calls: list[str] = []

    async def place_call(self, to_number: str, message: VoiceMessage) -> str:
        self.calls.append(to_number)
        return "call-sid"

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


@pytest.mark.asyncio
async def test_escalation_calls_on_call_operator():
    repo = InMemoryRepo()
    telephony = FakeTelephony()
    publisher = FakePublisher()
    event = _high_threat_event()
    await repo.save(event)

    use_case = EscalateEventUseCase(
        repository=repo,
        llm=FakeLLM(),
        voice=FakeVoice(),
        telephony=telephony,
        publisher=publisher,
        on_call_number="+15555550199",
    )

    result = await use_case.execute(event.id)

    assert telephony.calls == ["+15555550199"]
    assert result.description == "Intruder detected at the loading dock."
    assert result.status == "alerting"
    assert len(publisher.published) == 1


@pytest.mark.asyncio
async def test_escalation_missing_event_raises():
    use_case = EscalateEventUseCase(
        repository=InMemoryRepo(),
        llm=FakeLLM(),
        voice=FakeVoice(),
        telephony=FakeTelephony(),
        publisher=FakePublisher(),
        on_call_number="+15555550199",
    )

    with pytest.raises(SecurityEventNotFoundError):
        await use_case.execute("does-not-exist")
