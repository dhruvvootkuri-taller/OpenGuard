"""Tests for vision cost controls / rate limiting.

Covers the limiter itself (per-camera interval skip, global concurrency/rate
caps, daily budget kill switch) and that AnalyzeFeedFrameUseCase honours it:
a throttled frame is NOT analysed (the vision model is never called) and the
throttle state is surfaced on the output DTO.
"""

import pytest

from src.application.dtos.detection_dtos import AnalyzeFrameInputDTO
from src.application.ports.vision_rate_limiter_port import (
    STATE_BUDGET_EXCEEDED,
    STATE_GLOBAL_CONCURRENCY,
    STATE_GLOBAL_RATE,
    STATE_PER_CAMERA_INTERVAL,
)
from src.application.use_cases.analyze_feed_frame_use_case import (
    AnalyzeFeedFrameUseCase,
)
from src.domain.services.threat_assessment_service import ThreatAssessmentService
from src.domain.value_objects.detection_box import DetectionBox
from src.domain.value_objects.emergency_assessment import EmergencyAssessment
from src.infrastructure.persistence.in_memory_detection_confirmation_tracker import (
    InMemoryDetectionConfirmationTracker,
)
from src.infrastructure.persistence.in_memory_vision_rate_limiter import (
    InMemoryVisionRateLimiter,
)
from src.infrastructure.persistence.redis_vision_rate_limiter import (
    RedisVisionRateLimiter,
)
from tests.application.test_analyze_feed_frame_use_case import (
    FakeActiveTracker,
    FakePublisher,
    FakeTaskQueue,
    InMemoryRepo,
    StubVision,
)
from tests.infrastructure.fake_redis import FakeRedis


class _ManualClock:
    """A controllable monotonic clock for deterministic interval tests."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _emergency() -> EmergencyAssessment:
    return EmergencyAssessment(
        is_emergency=True,
        threat_score=0.95,
        confidence=0.95,
        label="fire",
        summary="Visible flames.",
        box=DetectionBox(
            label="fire", confidence=0.95, x=0.1, y=0.1, width=0.4, height=0.4
        ),
    )


def _input(camera_id="CAM-01") -> AnalyzeFrameInputDTO:
    return AnalyzeFrameInputDTO(
        camera_id=camera_id, image_base64="ZmFrZQ==", media_type="image/jpeg"
    )


def _use_case(vision, limiter) -> AnalyzeFeedFrameUseCase:
    return AnalyzeFeedFrameUseCase(
        vision_analyzer=vision,
        repository=InMemoryRepo(),
        threat_service=ThreatAssessmentService(),
        publisher=FakePublisher(),
        task_queue=FakeTaskQueue(),
        active_tracker=FakeActiveTracker(),
        confirmation=InMemoryDetectionConfirmationTracker(window=3, required=1),
        rate_limiter=limiter,
        min_confidence=0.0,
        min_threat_score=0.0,
    )


# --- limiter unit behaviour ---------------------------------------------------


@pytest.mark.asyncio
async def test_per_camera_interval_skips_excess_frames():
    clock = _ManualClock()
    limiter = InMemoryVisionRateLimiter(
        per_camera_min_interval_seconds=2.0,
        max_concurrent_calls=0,
        max_calls_per_minute=0,
        daily_budget_calls=0,
        clock=clock,
    )

    first = await limiter.try_acquire("CAM-1")
    assert first.allowed is True
    await limiter.release("CAM-1")

    # A second frame arriving immediately is under the interval -> skipped.
    second = await limiter.try_acquire("CAM-1")
    assert second.allowed is False
    assert second.state == STATE_PER_CAMERA_INTERVAL

    # After the interval elapses the camera may be analysed again.
    clock.advance(2.0)
    third = await limiter.try_acquire("CAM-1")
    assert third.allowed is True


@pytest.mark.asyncio
async def test_per_camera_interval_is_independent_per_camera():
    clock = _ManualClock()
    limiter = InMemoryVisionRateLimiter(
        per_camera_min_interval_seconds=2.0,
        max_concurrent_calls=0,
        max_calls_per_minute=0,
        daily_budget_calls=0,
        clock=clock,
    )

    assert (await limiter.try_acquire("CAM-1")).allowed is True
    # A different camera is not blocked by CAM-1's recent frame.
    assert (await limiter.try_acquire("CAM-2")).allowed is True
    # CAM-1 itself is still within its interval.
    assert (await limiter.try_acquire("CAM-1")).allowed is False


@pytest.mark.asyncio
async def test_global_concurrency_cap_enforced():
    limiter = InMemoryVisionRateLimiter(
        per_camera_min_interval_seconds=0,
        max_concurrent_calls=2,
        max_calls_per_minute=0,
        daily_budget_calls=0,
    )

    # Two distinct cameras hold both in-flight slots without releasing.
    assert (await limiter.try_acquire("CAM-1")).allowed is True
    assert (await limiter.try_acquire("CAM-2")).allowed is True

    third = await limiter.try_acquire("CAM-3")
    assert third.allowed is False
    assert third.state == STATE_GLOBAL_CONCURRENCY

    # Releasing one slot frees capacity for the next call.
    await limiter.release("CAM-1")
    assert (await limiter.try_acquire("CAM-3")).allowed is True


@pytest.mark.asyncio
async def test_global_per_minute_rate_cap_enforced():
    clock = _ManualClock()
    limiter = InMemoryVisionRateLimiter(
        per_camera_min_interval_seconds=0,
        max_concurrent_calls=0,
        max_calls_per_minute=2,
        daily_budget_calls=0,
        clock=clock,
    )

    assert (await limiter.try_acquire("CAM-1")).allowed is True
    assert (await limiter.try_acquire("CAM-2")).allowed is True
    denied = await limiter.try_acquire("CAM-3")
    assert denied.allowed is False
    assert denied.state == STATE_GLOBAL_RATE

    # A new minute bucket resets the per-minute counter.
    clock.advance(60.0)
    assert (await limiter.try_acquire("CAM-3")).allowed is True


@pytest.mark.asyncio
async def test_daily_budget_kill_switch_halts_analysis():
    limiter = InMemoryVisionRateLimiter(
        per_camera_min_interval_seconds=0,
        max_concurrent_calls=0,
        max_calls_per_minute=0,
        daily_budget_calls=2,
    )

    assert (await limiter.try_acquire("CAM-1")).allowed is True
    assert (await limiter.try_acquire("CAM-1")).allowed is True

    # Budget exhausted -> kill switch halts everything, even other cameras.
    denied = await limiter.try_acquire("CAM-2")
    assert denied.allowed is False
    assert denied.state == STATE_BUDGET_EXCEEDED
    assert "kill switch" in denied.reason


@pytest.mark.asyncio
async def test_zero_disables_all_limits():
    limiter = InMemoryVisionRateLimiter(
        per_camera_min_interval_seconds=0,
        max_concurrent_calls=0,
        max_calls_per_minute=0,
        daily_budget_calls=0,
    )
    # Hammer the same camera repeatedly; nothing is ever throttled.
    for _ in range(50):
        assert (await limiter.try_acquire("CAM-1")).allowed is True


# --- Redis-backed limiter -----------------------------------------------------


@pytest.mark.asyncio
async def test_redis_limiter_per_camera_interval_and_concurrency():
    redis = FakeRedis()
    limiter = RedisVisionRateLimiter(
        redis,
        per_camera_min_interval_seconds=2.0,
        max_concurrent_calls=1,
        max_calls_per_minute=0,
        daily_budget_calls=0,
    )

    first = await limiter.try_acquire("CAM-1")
    assert first.allowed is True

    # Concurrency cap of 1 is held (no release) -> different camera is blocked.
    blocked = await limiter.try_acquire("CAM-2")
    assert blocked.allowed is False
    assert blocked.state == STATE_GLOBAL_CONCURRENCY

    await limiter.release("CAM-1")
    # CAM-1 immediately again is under its per-camera interval -> skipped.
    again = await limiter.try_acquire("CAM-1")
    assert again.allowed is False
    assert again.state == STATE_PER_CAMERA_INTERVAL


@pytest.mark.asyncio
async def test_redis_limiter_daily_budget():
    redis = FakeRedis()
    limiter = RedisVisionRateLimiter(
        redis,
        per_camera_min_interval_seconds=0,
        max_concurrent_calls=0,
        max_calls_per_minute=0,
        daily_budget_calls=1,
    )
    assert (await limiter.try_acquire("CAM-1")).allowed is True
    denied = await limiter.try_acquire("CAM-1")
    assert denied.allowed is False
    assert denied.state == STATE_BUDGET_EXCEEDED


# --- use-case integration -----------------------------------------------------


@pytest.mark.asyncio
async def test_throttled_frame_is_not_analysed():
    clock = _ManualClock()
    limiter = InMemoryVisionRateLimiter(
        per_camera_min_interval_seconds=5.0,
        max_concurrent_calls=0,
        max_calls_per_minute=0,
        daily_budget_calls=0,
        clock=clock,
    )
    vision = StubVision(assessment=_emergency())
    use_case = _use_case(vision, limiter)

    first = await use_case.execute(_input())
    assert first.is_throttled is False
    assert vision.calls == 1

    # Second frame within the interval is throttled -> vision NOT called again.
    second = await use_case.execute(_input())
    assert second.is_throttled is True
    assert second.throttle_state == STATE_PER_CAMERA_INTERVAL
    assert second.is_emergency is False
    assert second.event is None
    assert vision.calls == 1  # the model was not called for the skipped frame


@pytest.mark.asyncio
async def test_budget_kill_switch_surfaces_state_through_use_case():
    limiter = InMemoryVisionRateLimiter(
        per_camera_min_interval_seconds=0,
        max_concurrent_calls=0,
        max_calls_per_minute=0,
        daily_budget_calls=1,
    )
    vision = StubVision(assessment=_emergency())
    use_case = _use_case(vision, limiter)

    await use_case.execute(_input())
    halted = await use_case.execute(_input())

    assert halted.is_throttled is True
    assert halted.throttle_state == STATE_BUDGET_EXCEEDED
    assert vision.calls == 1


@pytest.mark.asyncio
async def test_inflight_slot_released_even_when_vision_raises():
    from src.application.ports.vision_analyzer_port import VisionAnalyzerError

    limiter = InMemoryVisionRateLimiter(
        per_camera_min_interval_seconds=0,
        max_concurrent_calls=1,
        max_calls_per_minute=0,
        daily_budget_calls=0,
    )
    vision = StubVision(error=VisionAnalyzerError("boom"))
    use_case = _use_case(vision, limiter)

    with pytest.raises(VisionAnalyzerError):
        await use_case.execute(_input())

    # The single concurrency slot must have been released despite the error,
    # so a subsequent acquire still succeeds.
    assert (await limiter.try_acquire("CAM-9")).allowed is True
