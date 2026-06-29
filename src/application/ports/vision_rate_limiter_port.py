"""Port (abstraction) for vision-call cost controls and rate limiting.

The MP4 feed pipeline calls a paid vision model (Claude) on every analysed
frame. Without guard-rails a misbehaving/malicious client — or just several
tiles looping — can drive unbounded Anthropic spend and constitute a DoS. This
port enforces, *server-side and independent of client cadence*, three concerns
before any vision call is made:

  1. Per-camera minimum interval — frames arriving faster than the interval are
     skipped (not analysed), so a single fast-looping tile cannot spam the API.
  2. Global cap — a ceiling on concurrent in-flight vision calls and/or calls
     per rolling minute across all cameras (DoS protection).
  3. Budget / kill switch — a configurable maximum number of vision calls per
     day. Once the budget is exhausted the kill switch halts ALL analysis and
     the denial reason surfaces the state so the UI can show it clearly.

Usage contract (acquire/release):
  * ``try_acquire(camera_id)`` is called BEFORE the vision call. It returns a
    :class:`RateLimitDecision`. When ``allowed`` is ``False`` the caller MUST
    NOT call the vision model and should surface ``reason``/``state``.
  * When a call was allowed, the caller MUST call ``release()`` afterwards
    (in a ``finally``) so the in-flight concurrency gauge is decremented even
    if the vision call raises.

This lives in the application layer so the use case depends only on the
abstraction; infrastructure supplies a Redis-backed implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

# Stable machine-readable states for a denied acquisition. ``allowed`` covers
# the success path; everything else explains why a frame was gated out.
STATE_ALLOWED = "allowed"
STATE_PER_CAMERA_INTERVAL = "per_camera_interval"
STATE_GLOBAL_CONCURRENCY = "global_concurrency"
STATE_GLOBAL_RATE = "global_rate"
STATE_BUDGET_EXCEEDED = "budget_exceeded"


@dataclass(frozen=True)
class RateLimitDecision:
    """Outcome of an ``try_acquire`` call.

    ``allowed`` is ``True`` when the vision call may proceed. When ``False``,
    ``state`` is one of the ``STATE_*`` constants and ``reason`` is a
    human-readable explanation suitable for surfacing to operators.
    """

    allowed: bool
    state: str = STATE_ALLOWED
    reason: str = ""


class VisionRateLimiterPort(ABC):
    """Abstraction over vision-call rate limiting and budget enforcement."""

    @abstractmethod
    async def try_acquire(self, camera_id: str) -> RateLimitDecision:
        """Attempt to reserve a vision call for ``camera_id``.

        Atomically checks the per-camera interval, the global concurrency /
        per-minute caps and the daily budget. On success it records the call
        (advancing all counters) and returns ``allowed=True``; the caller MUST
        later invoke :meth:`release`. On failure nothing is reserved.
        """
        raise NotImplementedError

    @abstractmethod
    async def release(self, camera_id: str) -> None:
        """Release a previously-acquired in-flight slot for ``camera_id``."""
        raise NotImplementedError
