"""Application test using in-memory fakes for all ports.

Demonstrates that the use case depends only on abstractions. The detection
fast-path persists + publishes the event and enqueues escalation onto the
(faked) task queue when the domain decides a human must be alerted.
"""

import pytest

from src.application.dtos.detection_dtos import (
    DetectionBoxDTO,
    ProcessDetectionInputDTO,
)
from src.application.ports.active_emergency_tracker_port import (
    ActiveEmergency,
    ActiveEmergencyTrackerPort,
)
from src.application.ports.event_publisher_port import EventPublisherPort
from src.application.ports.task_queue_port import TaskQueuePort
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


def _build_use_case(repo, publisher, queue, tracker=None) -> ProcessDetectionUseCase:
    return ProcessDetectionUseCase(
        repository=repo,
        threat_service=ThreatAssessmentService(),
        publisher=publisher,
        task_queue=queue,
        active_tracker=tracker or FakeActiveTracker(),
    )


@pytest.mark.asyncio
async def test_high_threat_enqueues_escalation():
    repo = InMemoryRepo()
    publisher = FakePublisher()
    queue = FakeTaskQueue()
    use_case = _build_use_case(repo, publisher, queue)

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
    assert queue.enqueued == [result.id]
    assert len(publisher.published) == 1
    assert result.id in repo.items


@pytest.mark.asyncio
async def test_low_threat_does_not_enqueue_escalation():
    repo = InMemoryRepo()
    publisher = FakePublisher()
    queue = FakeTaskQueue()
    use_case = _build_use_case(repo, publisher, queue)

    result = await use_case.execute(
        ProcessDetectionInputDTO(
            camera_id="cam-1",
            detections=[
                DetectionBoxDTO(
                    label="cat", confidence=0.4, x=0.1, y=0.1,
                    width=0.05, height=0.05,
                )
            ],
            is_armed_zone=False,
        )
    )

    assert result.escalated is False
    assert queue.enqueued == []
    assert len(publisher.published) == 1


def _knife_detection(camera_id="cam-1") -> ProcessDetectionInputDTO:
    return ProcessDetectionInputDTO(
        camera_id=camera_id,
        detections=[
            DetectionBoxDTO(
                label="knife", confidence=0.95, x=0.1, y=0.1,
                width=0.2, height=0.2,
            )
        ],
        is_armed_zone=True,
    )


@pytest.mark.asyncio
async def test_repeated_escalating_detections_collapse_to_one_incident():
    repo = InMemoryRepo()
    publisher = FakePublisher()
    queue = FakeTaskQueue()
    tracker = FakeActiveTracker()
    use_case = _build_use_case(repo, publisher, queue, tracker)

    results = [await use_case.execute(_knife_detection()) for _ in range(5)]

    assert len(repo.items) == 1
    assert len(queue.enqueued) == 1
    assert len({r.id for r in results}) == 1
    assert len(tracker.touches) == 4


@pytest.mark.asyncio
async def test_new_incident_after_clear():
    repo = InMemoryRepo()
    publisher = FakePublisher()
    queue = FakeTaskQueue()
    tracker = FakeActiveTracker()
    use_case = _build_use_case(repo, publisher, queue, tracker)

    first = await use_case.execute(_knife_detection())
    await tracker.clear("cam-1")
    second = await use_case.execute(_knife_detection())

    assert first.id != second.id
    assert len(queue.enqueued) == 2


@pytest.mark.asyncio
async def test_dedup_is_per_camera():
    repo = InMemoryRepo()
    publisher = FakePublisher()
    queue = FakeTaskQueue()
    tracker = FakeActiveTracker()
    use_case = _build_use_case(repo, publisher, queue, tracker)

    await use_case.execute(_knife_detection("cam-1"))
    await use_case.execute(_knife_detection("cam-1"))
    await use_case.execute(_knife_detection("cam-2"))

    assert len(repo.items) == 2
    assert len(queue.enqueued) == 2
