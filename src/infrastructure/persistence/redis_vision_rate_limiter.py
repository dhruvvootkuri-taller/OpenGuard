"""Redis-backed implementation of VisionRateLimiterPort.

State is split across a handful of keys so enforcement is distributed (correct
even with multiple API workers):

  * ``open_guard:vision:last:{camera_id}`` — last-analysed unix-ms per camera,
    used for the per-camera minimum interval. Carries a TTL of the interval so
    it self-expires.
  * ``open_guard:vision:inflight`` — integer gauge of concurrent in-flight
    calls (incremented on acquire, decremented on release).
  * ``open_guard:vision:rate:{minute}`` — per-minute counter (key bucketed by
    epoch minute, TTL ~2 minutes) for the calls-per-minute cap.
  * ``open_guard:vision:budget:{yyyymmdd}`` — daily call counter (TTL ~26h) for
    the budget / kill switch.

Each limit is independently disable-able by passing ``0`` (or a negative) for
its bound. The checks short-circuit in the cheap-first order: per-camera
interval, budget (kill switch), global per-minute rate, then concurrency.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import redis.asyncio as redis

from src.application.ports.vision_rate_limiter_port import (
    STATE_BUDGET_EXCEEDED,
    STATE_GLOBAL_CONCURRENCY,
    STATE_GLOBAL_RATE,
    STATE_PER_CAMERA_INTERVAL,
    RateLimitDecision,
    VisionRateLimiterPort,
)

_LAST_KEY = "open_guard:vision:last:{camera_id}"
_INFLIGHT_KEY = "open_guard:vision:inflight"
_RATE_KEY = "open_guard:vision:rate:{minute}"
_BUDGET_KEY = "open_guard:vision:budget:{day}"

_ALLOWED = RateLimitDecision(allowed=True)


class RedisVisionRateLimiter(VisionRateLimiterPort):
    """Distributed vision cost-control gate over Redis."""

    def __init__(
        self,
        client: "redis.Redis",
        *,
        per_camera_min_interval_seconds: float = 2.0,
        max_concurrent_calls: int = 4,
        max_calls_per_minute: int = 60,
        daily_budget_calls: int = 5000,
    ) -> None:
        self._client = client
        # A non-positive bound disables that specific limit.
        self._interval_ms = max(0.0, float(per_camera_min_interval_seconds)) * 1000.0
        self._max_concurrent = int(max_concurrent_calls)
        self._max_per_minute = int(max_calls_per_minute)
        self._daily_budget = int(daily_budget_calls)

    async def try_acquire(self, camera_id: str) -> RateLimitDecision:
        now_ms = time.time() * 1000.0

        # 1. Per-camera minimum interval — skip excess frames per camera.
        if self._interval_ms > 0:
            last_key = _LAST_KEY.format(camera_id=camera_id)
            raw = await self._client.get(last_key)
            if raw is not None:
                last_ms = float(raw.decode() if isinstance(raw, bytes) else raw)
                if now_ms - last_ms < self._interval_ms:
                    wait = (self._interval_ms - (now_ms - last_ms)) / 1000.0
                    return RateLimitDecision(
                        allowed=False,
                        state=STATE_PER_CAMERA_INTERVAL,
                        reason=(
                            "frame skipped: under the per-camera minimum "
                            f"interval ({self._interval_ms / 1000.0:.2f}s); "
                            f"~{wait:.2f}s until next analysed frame"
                        ),
                    )

        # 2. Daily budget / kill switch — halt ALL analysis once exhausted.
        if self._daily_budget > 0:
            budget_key = _BUDGET_KEY.format(day=_utc_day())
            used = _as_int(await self._client.get(budget_key))
            if used >= self._daily_budget:
                return RateLimitDecision(
                    allowed=False,
                    state=STATE_BUDGET_EXCEEDED,
                    reason=(
                        "vision budget exhausted: daily call budget of "
                        f"{self._daily_budget} reached — analysis halted "
                        "(kill switch). Resets at UTC midnight."
                    ),
                )

        # 3. Global calls-per-minute cap.
        if self._max_per_minute > 0:
            rate_key = _RATE_KEY.format(minute=int(time.time()) // 60)
            current = _as_int(await self._client.get(rate_key))
            if current >= self._max_per_minute:
                return RateLimitDecision(
                    allowed=False,
                    state=STATE_GLOBAL_RATE,
                    reason=(
                        "global rate cap reached: "
                        f"{self._max_per_minute} vision calls/minute"
                    ),
                )

        # 4. Global concurrency cap on in-flight calls.
        if self._max_concurrent > 0:
            inflight = _as_int(await self._client.get(_INFLIGHT_KEY))
            if inflight >= self._max_concurrent:
                return RateLimitDecision(
                    allowed=False,
                    state=STATE_GLOBAL_CONCURRENCY,
                    reason=(
                        "global concurrency cap reached: "
                        f"{self._max_concurrent} in-flight vision calls"
                    ),
                )

        # Reserve: advance every counter so this call is accounted for.
        await self._record(camera_id, now_ms)
        return _ALLOWED

    async def release(self, camera_id: str) -> None:
        if self._max_concurrent <= 0:
            return
        current = _as_int(await self._client.get(_INFLIGHT_KEY))
        if current <= 0:
            return
        await self._client.set(_INFLIGHT_KEY, str(current - 1))

    async def _record(self, camera_id: str, now_ms: float) -> None:
        if self._interval_ms > 0:
            ttl = max(1, int(self._interval_ms / 1000.0) + 1)
            await self._client.set(
                _LAST_KEY.format(camera_id=camera_id), str(now_ms), ex=ttl
            )
        if self._max_per_minute > 0:
            rate_key = _RATE_KEY.format(minute=int(time.time()) // 60)
            current = _as_int(await self._client.get(rate_key))
            await self._client.set(rate_key, str(current + 1), ex=120)
        if self._daily_budget > 0:
            budget_key = _BUDGET_KEY.format(day=_utc_day())
            used = _as_int(await self._client.get(budget_key))
            await self._client.set(budget_key, str(used + 1), ex=26 * 3600)
        if self._max_concurrent > 0:
            inflight = _as_int(await self._client.get(_INFLIGHT_KEY))
            await self._client.set(_INFLIGHT_KEY, str(inflight + 1))


def _as_int(raw) -> int:
    if raw is None:
        return 0
    if isinstance(raw, bytes):
        raw = raw.decode()
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return 0


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")
