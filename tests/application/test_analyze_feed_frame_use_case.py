"""Application tests for AnalyzeFeedFrameUseCase using in-memory fakes.

Covers the three browser-end-to-end behaviours:
  * emergency frame -> is_emergency True, a SecurityEvent is persisted/published
  * calm frame      -> is_emergency False, nothing persisted
  * provider error  -> VisionAnalyzerError propagates (never a silent all-clear)
"""

import pytest

from src.application.dtos.detection_dtos import AnalyzeFrameInputDTO
from src.application.ports.active_emergency_tracker_port import (
    ActiveEmergency,
    ActiveEmergencyTrackerPort,
)
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
from src.infrastructure.persistence.in_memory_vision_rate_limiter import (
    InMemoryVisionRateLimiter,
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

    async def delete(self, event_id: str) -> None:
        self.items.pop(event_id, None)


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


class FakeActiveTracker(ActiveEmergencyTrackerPort):
    """In-memory active-emergency tracker (no TTL; cleared explicitly)."""

    def __init__(self):
        self.active: dict[str, str] = {}
        self.touches: list[str] = []

    async def get_active(self, camera_id: str):
        event_id = self.active.get(camera_id)
        if event_id is None:
            return None
        return ActiveEmergency(camera_id=camera_id, event_id=event_id)

    async def mark_active(self, camera_id: str, event_id: str) -> None:
        self.active[camera_id] = event_id

    async def touch(self, camera_id: str) -> None:
        if camera_id in self.active:
            self.touches.append(camera_id)

    async def clear(self, camera_id: str) -> None:
        self.active.pop(camera_id, None)


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
    repo=None,
    queue=None,
    tracker=None,
    window=3,
    required=1,
    min_confidence=0.6,
    min_threat_score=0.4,
    rate_limiter=None,
) -> AnalyzeFeedFrameUseCase:
    return AnalyzeFeedFrameUseCase(
        vision_analyzer=vision,
        repository=repo or InMemoryRepo(),
        threat_service=ThreatAssessmentService(),
        publisher=FakePublisher(),
        task_queue=queue or FakeTaskQueue(),
        active_tracker=tracker or FakeActiveTracker(),
        confirmation=InMemoryDetectionConfirmationTracker(
            window=window, required=required
        ),
        rate_limiter=rate_limiter
        # Disable all cost-control limits by default so existing behavioural
        # tests are unaffected; rate-limiting has its own dedicated tests.
        or InMemoryVisionRateLimiter(
            per_camera_min_interval_seconds=0,
            max_concurrent_calls=0,
            max_calls_per_minute=0,
            daily_budget_calls=0,
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


def _fire_vision() -> StubVision:
    return StubVision(
        assessment=EmergencyAssessment(
            is_emergency=True,
            threat_score=0.95,
            confidence=0.95,
            label="fire",
            summary="Visible flames in the kitchen.",
            box=DetectionBox(
                label="fire", confidence=0.95, x=0.1, y=0.1, width=0.4, height=0.4
            ),
        )
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
    use_case = _build(vision, window=3, required=2, queue=queue)

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
    use_case = _build(vision, window=3, required=2, queue=queue)

    r1 = await use_case.execute(_input())
    vision._assessment = smoke
    r2 = await use_case.execute(_input())
    vision._assessment = _emergency(label="person")
    r3 = await use_case.execute(_input())

    assert all(r.event is None for r in (r1, r2, r3))
    assert all(r.is_candidate for r in (r1, r2, r3))
    assert queue.enqueued == []


@pytest.mark.asyncio
async def test_repeated_emergency_frames_collapse_to_one_incident():
    repo = InMemoryRepo()
    queue = FakeTaskQueue()
    tracker = FakeActiveTracker()
    use_case = _build(_fire_vision(), repo=repo, queue=queue, tracker=tracker)

    results = [await use_case.execute(_input()) for _ in range(5)]

    # Exactly one SecurityEvent persisted, one escalation enqueued.
    assert len(repo.items) == 1
    assert len(queue.enqueued) == 1
    # All five responses reference the same event.
    event_ids = {r.event.id for r in results}
    assert len(event_ids) == 1
    # The 4 follow-up frames refreshed (touched) the cooldown.
    assert len(tracker.touches) == 4


@pytest.mark.asyncio
async def test_new_incident_allowed_after_cooldown_clear():
    repo = InMemoryRepo()
    queue = FakeTaskQueue()
    tracker = FakeActiveTracker()
    use_case = _build(_fire_vision(), repo=repo, queue=queue, tracker=tracker)

    first = await use_case.execute(_input())
    # Simulate cooldown elapse / acknowledgement clearing the active marker.
    await tracker.clear("CAM-01")
    second = await use_case.execute(_input())

    assert first.event.id != second.event.id
    assert len(repo.items) == 2
    assert len(queue.enqueued) == 2


@pytest.mark.asyncio
async def test_per_camera_independence():
    repo = InMemoryRepo()
    queue = FakeTaskQueue()
    tracker = FakeActiveTracker()
    use_case = _build(_fire_vision(), repo=repo, queue=queue, tracker=tracker)

    cam_a = AnalyzeFrameInputDTO(
        camera_id="CAM-A", image_base64="ZmFrZQ==", media_type="image/jpeg",
        is_armed_zone=True, zone="A",
    )
    cam_b = AnalyzeFrameInputDTO(
        camera_id="CAM-B", image_base64="ZmFrZQ==", media_type="image/jpeg",
        is_armed_zone=True, zone="B",
    )

    await use_case.execute(cam_a)
    await use_case.execute(cam_a)
    await use_case.execute(cam_b)

    # One incident per camera -> two events, two escalations.
    assert len(repo.items) == 2
    assert len(queue.enqueued) == 2