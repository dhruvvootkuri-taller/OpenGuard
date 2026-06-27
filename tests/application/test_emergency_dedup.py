"""Tests for the emergency de-duplication tracker and ack-clearing behaviour.

Covers the Redis-backed tracker mapping and that acknowledging an event ends
the incident (clears the active marker) so a new incident is allowed at once.
"""

import pytest

from src.application.dtos.detection_dtos import AcknowledgeEventInputDTO
from src.application.use_cases.acknowledge_event_use_case import (
    AcknowledgeEventUseCase,
)
from src.domain.entities.security_event import SecurityEvent
from src.domain.value_objects.detection_box import DetectionBox
from src.domain.value_objects.threat_level import ThreatLevel, ThreatSeverity
from src.infrastructure.persistence.redis_active_emergency_tracker import (
    RedisActiveEmergencyTracker,
)
from src.infrastructure.persistence.redis_security_event_repository import (
    RedisSecurityEventRepository,
)
from tests.infrastructure.fake_redis import FakeRedis


@pytest.mark.asyncio
async def test_tracker_marks_gets_and_clears():
    tracker = RedisActiveEmergencyTracker(FakeRedis(), window_seconds=60)

    assert await tracker.get_active("CAM-1") is None

    await tracker.mark_active("CAM-1", "evt-1")
    active = await tracker.get_active("CAM-1")
    assert active is not None
    assert active.camera_id == "CAM-1"
    assert active.event_id == "evt-1"

    await tracker.clear("CAM-1")
    assert await tracker.get_active("CAM-1") is None


@pytest.mark.asyncio
async def test_tracker_is_per_camera():
    tracker = RedisActiveEmergencyTracker(FakeRedis(), window_seconds=60)

    await tracker.mark_active("CAM-1", "evt-1")
    await tracker.mark_active("CAM-2", "evt-2")

    assert (await tracker.get_active("CAM-1")).event_id == "evt-1"
    assert (await tracker.get_active("CAM-2")).event_id == "evt-2"


@pytest.mark.asyncio
async def test_touch_only_refreshes_existing_incident():
    tracker = RedisActiveEmergencyTracker(FakeRedis(), window_seconds=60)

    # Touch on a camera with no active incident is a no-op.
    await tracker.touch("CAM-1")
    assert await tracker.get_active("CAM-1") is None

    await tracker.mark_active("CAM-1", "evt-1")
    await tracker.touch("CAM-1")
    assert (await tracker.get_active("CAM-1")).event_id == "evt-1"


@pytest.mark.asyncio
async def test_acknowledge_clears_active_marker():
    redis = FakeRedis()
    repo = RedisSecurityEventRepository(redis)
    tracker = RedisActiveEmergencyTracker(redis, window_seconds=60)

    event = SecurityEvent(
        camera_id="CAM-1",
        threat_level=ThreatLevel(severity=ThreatSeverity.CRITICAL, confidence=0.9),
        detections=[
            DetectionBox(
                label="fire", confidence=0.9, x=0.1, y=0.1, width=0.4, height=0.4
            )
        ],
    )
    event.mark_alerting()
    await repo.save(event)
    await tracker.mark_active("CAM-1", event.id)

    use_case = AcknowledgeEventUseCase(repository=repo, active_tracker=tracker)
    await use_case.execute(
        AcknowledgeEventInputDTO(event_id=event.id, operator_id="op-1")
    )

    # Incident ended -> a new incident on this camera is allowed immediately.
    assert await tracker.get_active("CAM-1") is None
