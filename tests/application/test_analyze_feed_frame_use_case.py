"""Application tests for AnalyzeFeedFrameUseCase using in-memory fakes.

Covers the three browser-end-to-end behaviours:
  * emergency frame -> is_emergency True, a SecurityEvent is persisted/published
  * calm frame      -> is_emergency False, nothing persisted
  * provider error  -> VisionAnalyzerError propagates (never a silent all-clear)
"""

import pytest

from src.application.dtos.detection_dtos import AnalyzeFrameInputDTO
from src.application.ports.event_publisher_port import EventPublisherPort
from src.application.ports.task_queue_port import TaskQueuePort
from src.application.ports.vision_analyzer_port import (
    VisionAnalyzerError,
    VisionAnalyzerPort,
)
from src.application.use_cases.analyze_feed_frame_use_case import (
    AnalyzeFeedFrameUseCase,
)
from src.domain.entities.security_event import SecurityEvent
from src.domain.repositories.security_event_repository import (
    SecurityEventRepository,
)
from src.domain.services.threat_assessment_service import ThreatAssessmentService
from src.domain.value_objects.detection_box import DetectionBox
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


class StubVision(VisionAnalyzerPort):
    def __init__(self, assessment=None, error=None):
        self._assessment = assessment
        self._error = error
        self.calls = 0

    async def assess_frame(self, image_base64, media_type, is_armed_zone, zone):
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._assessment


def _build(vision) -> AnalyzeFeedFrameUseCase:
    return AnalyzeFeedFrameUseCase(
        vision_analyzer=vision,
        repository=InMemoryRepo(),
        threat_service=ThreatAssessmentService(),
        publisher=FakePublisher(),
        task_queue=FakeTaskQueue(),
    )


def _input() -> AnalyzeFrameInputDTO:
    return AnalyzeFrameInputDTO(
        camera_id="CAM-01",
        image_base64="ZmFrZQ==",
        media_type="image/jpeg",
        is_armed_zone=True,
        zone="Main Entrance",
    )


@pytest.mark.asyncio
async def test_emergency_frame_creates_event():
    vision = StubVision(
        assessment=EmergencyAssessment(
            is_emergency=True,
            threat_score=0.92,
            confidence=0.9,
            label="weapon",
            summary="Person brandishing a knife.",
            box=DetectionBox(
                label="weapon", confidence=0.9, x=0.2, y=0.2, width=0.3, height=0.3
            ),
        )
    )
    use_case = _build(vision)

    result = await use_case.execute(_input())

    assert result.is_emergency is True
    assert result.event is not None
    assert result.event.camera_id == "CAM-01"
    assert result.event.detections  # has at least one box


@pytest.mark.asyncio
async def test_calm_frame_creates_no_event():
    vision = StubVision(assessment=EmergencyAssessment.all_clear())
    use_case = _build(vision)

    result = await use_case.execute(_input())

    assert result.is_emergency is False
    assert result.event is None


@pytest.mark.asyncio
async def test_provider_error_propagates_not_silent_all_clear():
    vision = StubVision(error=VisionAnalyzerError("bad api key / retired model"))
    use_case = _build(vision)

    with pytest.raises(VisionAnalyzerError):
        await use_case.execute(_input())
