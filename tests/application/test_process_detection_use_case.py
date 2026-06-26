"""Application test using in-memory fakes for all ports.

Demonstrates that the use case depends only on abstractions.
"""

import pytest

from src.application.dtos.detection_dtos import (
    DetectionBoxDTO,
    ProcessDetectionInputDTO,
)
from src.application.ports.event_publisher_port import EventPublisherPort
from src.application.ports.llm_port import LLMPort
from src.application.ports.notification_port import (
    TelephonyPort,
    VoiceMessage,
    VoiceSynthesisPort,
)
from src.application.use_cases.process_detection_use_case import (
    ProcessDetectionUseCase,
)
from src.domain.entities.security_event import SecurityEvent
from src.domain.repositories.security_event_repository import (
    SecurityEventRepository,
)
from src.domain.services.threat_assessment_service import ThreatAssessmentService


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


@pytest.mark.asyncio
async def test_high_threat_triggers_call():
    repo = InMemoryRepo()
    telephony = FakeTelephony()
    publisher = FakePublisher()

    use_case = ProcessDetectionUseCase(
        repository=repo,
        threat_service=ThreatAssessmentService(),
        llm=FakeLLM(),
        voice=FakeVoice(),
        telephony=telephony,
        publisher=publisher,
        on_call_number="+15555550199",
    )

    result = await use_case.execute(
        ProcessDetectionInputDTO(
            camera_id="cam-1",
            detections=[
                DetectionBoxDTO(
                    label="knife", confidence=0.95, x=0.1, y=0.1,
                    width=0.2, height=0.2,
                )
            ],
            is_armed_zone=True,
        )
    )

    assert result.escalated is True
    assert telephony.calls == ["+15555550199"]
    assert len(publisher.published) == 1
    assert result.description == "Intruder detected at the loading dock."
