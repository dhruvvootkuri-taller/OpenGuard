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
from src.infrastructure.persistence.in_memory_detection_confirmation_tracker import (
    InMemoryDetectionConfirmationTracker,
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


def _build(
    vision,
    *,
    window=3,
    required=1,
    min_confidence=0.6,
    min_threat_score=0.4,
    task_queue=None,
) -> AnalyzeFeedFrameUseCase:
    return AnalyzeFeedFrameUseCase(
        vision_analyzer=vision,
        repository=InMemoryRepo(),
        threat_service=ThreatAssessmentService(),
        publisher=FakePublisher(),
        task_queue=task_queue or FakeTaskQueue(),
        confirmation=InMemoryDetectionConfirmationTracker(
            window=window, required=required
        ),
        min_confidence=min_confidence,
        min_threat_score=min_threat_score,
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


# --- false-alarm gating -------------------------------------------------------


def _emergency(confidence=0.9, threat_score=0.92, label="weapon"):
    return EmergencyAssessment(
        is_emergency=True,
        threat_score=threat_score,
        confidence=confidence,
        label=label,
        summary="Person brandishing a knife.",
        box=DetectionBox(
            label=label, confidence=confidence, x=0.2, y=0.2, width=0.3, height=0.3
        ),
    )


@pytest.mark.asyncio
async def test_low_confidence_frame_is_candidate_not_event():
    vision = StubVision(assessment=_emergency(confidence=0.3, threat_score=0.92))
    use_case = _build(vision, min_confidence=0.6)

    result = await use_case.execute(_input())

    assert result.is_emergency is False
    assert result.event is None
    assert result.is_candidate is True
    assert "below threshold" in result.candidate_reason


@pytest.mark.asyncio
async def test_low_threat_score_frame_is_candidate_not_event():
    vision = StubVision(assessment=_emergency(confidence=0.9, threat_score=0.2))
    use_case = _build(vision, min_threat_score=0.4)

    result = await use_case.execute(_input())

    assert result.is_emergency is False
    assert result.event is None
    assert result.is_candidate is True


@pytest.mark.asyncio
async def test_single_strong_frame_is_candidate_until_confirmed():
    # window=3, required=2 -> one frame is not enough to escalate.
    queue = FakeTaskQueue()
    vision = StubVision(assessment=_emergency())
    use_case = _build(vision, window=3, required=2, task_queue=queue)

    first = await use_case.execute(_input())
    assert first.is_emergency is False
    assert first.event is None
    assert first.is_candidate is True
    assert "confirmation" in first.candidate_reason
    assert queue.enqueued == []

    # A second matching frame confirms the detection -> real event + escalation.
    second = await use_case.execute(_input())
    assert second.is_emergency is True
    assert second.event is not None
    assert queue.enqueued  # escalation enqueued exactly once it is confirmed


@pytest.mark.asyncio
async def test_isolated_one_frame_hit_never_confirms():
    # An ordinary clip producing a single spurious 'fire' hit among other
    # labels must never reach the confirmation threshold (2 of last 3).
    queue = FakeTaskQueue()
    fire = _emergency(label="fire")
    smoke = _emergency(label="smoke")
    # Distinct labels never accumulate 2 occurrences in the window.
    vision = StubVision(assessment=fire)
    use_case = _build(vision, window=3, required=2, task_queue=queue)

    r1 = await use_case.execute(_input())
    vision._assessment = smoke
    r2 = await use_case.execute(_input())
    vision._assessment = _emergency(label="person")
    r3 = await use_case.execute(_input())

    assert all(r.event is None for r in (r1, r2, r3))
    assert all(r.is_candidate for r in (r1, r2, r3))
    assert queue.enqueued == []
