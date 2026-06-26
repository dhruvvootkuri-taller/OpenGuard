"""Application test for AnalyzeFeedFrameUseCase using in-memory fakes.

Verifies the use case depends only on abstractions and that it:
  - persists/publishes/escalates a SecurityEvent ONLY when the vision
    analyser reports a real emergency, and
  - does nothing (no persistence, no escalation) on a clear frame.
"""

import pytest

from src.application.dtos.detection_dtos import AnalyzeFeedFrameInputDTO
from src.application.ports.event_publisher_port import EventPublisherPort
from src.application.ports.task_queue_port import TaskQueuePort
from src.application.ports.vision_analyzer_port import VisionAnalyzerPort
from src.application.use_cases.analyze_feed_frame_use_case import (
    AnalyzeFeedFrameUseCase,
)
from src.domain.entities.security_event import SecurityEvent
from src.domain.repositories.security_event_repository import (
    SecurityEventRepository,
)
from src.domain.services.threat_assessment_service import ThreatAssessmentService
from src.domain.value_objects.emergency_assessment import EmergencyAssessment


class InMemoryRepo(SecurityEventRepository):
    def __init__(self):
        self.items: dict[str, SecurityEvent] = {}

    async def save(self, event: SecurityEvent) -> None:
        self.items[event.id] = event

    async def get_by_id(self, event_id: str):
        return self.items.get(event_id)

    async def list_recent(self, limit: int = 50):
        return list(self.items.values())[:limit]


class FakePublisher(EventPublisherPort):
    def __init__(self):
        self.published = []

    async def publish_event(self, event) -> None:
        self.published.append(event)


class FakeTaskQueue(TaskQueuePort):
    def __init__(self):
        self.enqueued: list[str] = []

    def enqueue_escalation(self, event_id: str) -> str:
        self.enqueued.append(event_id)
        return "task-id"


class StubAnalyzer(VisionAnalyzerPort):
    def __init__(self, assessment: EmergencyAssessment):
        self._assessment = assessment
        self.calls: list[tuple[str, str, str]] = []

    async def analyze_frame(
        self, image_base64: str, media_type: str = "image/jpeg", context: str = ""
    ) -> EmergencyAssessment:
        self.calls.append((image_base64, media_type, context))
        return self._assessment


def _build(analyzer, repo, publisher, queue) -> AnalyzeFeedFrameUseCase:
    return AnalyzeFeedFrameUseCase(
        analyzer=analyzer,
        repository=repo,
        threat_service=ThreatAssessmentService(),
        publisher=publisher,
        task_queue=queue,
    )


@pytest.mark.asyncio
async def test_emergency_frame_creates_and_escalates_event():
    analyzer = StubAnalyzer(
        EmergencyAssessment(
            is_emergency=True,
            label="weapon",
            score=0.96,
            confidence=0.9,
            summary="Person brandishing a knife.",
            x=0.2,
            y=0.2,
            width=0.3,
            height=0.4,
        )
    )
    repo, publisher, queue = InMemoryRepo(), FakePublisher(), FakeTaskQueue()
    use_case = _build(analyzer, repo, publisher, queue)

    result = await use_case.execute(
        AnalyzeFeedFrameInputDTO(
            camera_id="cam-1",
            image_base64="ZmFrZQ==",
            is_armed_zone=True,
            zone="Lobby",
        )
    )

    assert result.is_emergency is True
    assert result.event is not None
    assert result.event.escalated is True
    assert queue.enqueued == [result.event.id]
    assert len(publisher.published) == 1
    assert result.event.id in repo.items
    # Context about the camera/zone is forwarded to the analyser.
    assert "Lobby" in analyzer.calls[0][2]


@pytest.mark.asyncio
async def test_clear_frame_does_nothing():
    analyzer = StubAnalyzer(EmergencyAssessment.none())
    repo, publisher, queue = InMemoryRepo(), FakePublisher(), FakeTaskQueue()
    use_case = _build(analyzer, repo, publisher, queue)

    result = await use_case.execute(
        AnalyzeFeedFrameInputDTO(
            camera_id="cam-1",
            image_base64="ZmFrZQ==",
            is_armed_zone=False,
        )
    )

    assert result.is_emergency is False
    assert result.event is None
    assert repo.items == {}
    assert publisher.published == []
    assert queue.enqueued == []
