"""In-memory implementation of VisionRateLimiterPort.

Process-local; suitable for single-worker dev runs and for tests. Enforces the
same four limits as the Redis implementation (per-camera interval, daily budget
kill switch, global per-minute rate, global concurrency) using a monotonic
clock that can be injected for deterministic testing.

For distributed/multi-worker deployments use ``RedisVisionRateLimiter``.
"""

from __future__ import annotations

import time
from typing import Callable

from src.application.ports.vision_rate_limiter_port import (
    STATE_BUDGET_EXCEEDED,
    STATE_GLOBAL_CONCURRENCY,
    STATE_GLOBAL_RATE,
    STATE_PER_CAMERA_INTERVAL,
    RateLimitDecision,
    VisionRateLimiterPort,
)

_ALLOWED = RateLimitDecision(allowed=True)


class InMemoryVisionRateLimiter(VisionRateLimiterPort):
    """Process-local vision cost-control gate."""

    def __init__(
        self,
        *,
        per_camera_min_interval_seconds: float = 2.0,
        max_concurrent_calls: int = 4,
        max_calls_per_minute: int = 60,
        daily_budget_calls: int = 5000,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._interval = max(0.0, float(per_camera_min_interval_seconds))
        self._max_concurrent = int(max_concurrent_calls)
        self._max_per_minute = int(max_calls_per_minute)
        self._daily_budget = int(daily_budget_calls)
        self._clock = clock or time.monotonic

        self._last_analyzed: dict[str, float] = {}
        self._inflight = 0
        self._minute_bucket: int = -1
        self._minute_count = 0
        self._budget_used = 0

    async def try_acquire(self, camera_id: str) -> RateLimitDecision:
        now = self._clock()

        # 1. Per-camera minimum interval.
        if self._interval > 0:
            last = self._last_analyzed.get(camera_id)
            if last is not None and now - last < self._interval:
                wait = self._interval - (now - last)
                return RateLimitDecision(
                    allowed=False,
                    state=STATE_PER_CAMERA_INTERVAL,
                    reason=(
                        "frame skipped: under the per-camera minimum interval "
                        f"({self._interval:.2f}s); ~{wait:.2f}s until next "
                        "analysed frame"
                    ),
                )

        # 2. Daily budget / kill switch.
        if self._daily_budget > 0 and self._budget_used >= self._daily_budget:
            return RateLimitDecision(
                allowed=False,
                state=STATE_BUDGET_EXCEEDED,
                reason=(
                    "vision budget exhausted: daily call budget of "
                    f"{self._daily_budget} reached — analysis halted "
                    "(kill switch)."
                ),
            )

        # 3. Global calls-per-minute cap.
        if self._max_per_minute > 0:
            bucket = int(now // 60)
            if bucket != self._minute_bucket:
                self._minute_bucket = bucket
                self._minute_count = 0
            if self._minute_count >= self._max_per_minute:
                return RateLimitDecision(
                    allowed=False,
                    state=STATE_GLOBAL_RATE,
                    reason=(
                        "global rate cap reached: "
                        f"{self._max_per_minute} vision calls/minute"
                    ),
                )

        # 4. Global concurrency cap.
        if self._max_concurrent > 0 and self._inflight >= self._max_concurrent:
            return RateLimitDecision(
                allowed=False,
                state=STATE_GLOBAL_CONCURRENCY,
                reason=(
                    "global concurrency cap reached: "
                    f"{self._max_concurrent} in-flight vision calls"
                ),
            )

        # Reserve.
        if self._interval > 0:
            self._last_analyzed[camera_id] = now
        if self._max_per_minute > 0:
            self._minute_count += 1
        if self._daily_budget > 0:
            self._budget_used += 1
        if self._max_concurrent > 0:
            self._inflight += 1
        return _ALLOWED

    async def release(self, camera_id: str) -> None:
        if self._max_concurrent > 0 and self._inflight > 0:
            self._inflight -= 1
