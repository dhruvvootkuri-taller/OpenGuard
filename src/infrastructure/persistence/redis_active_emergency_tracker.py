"""Redis implementation of the ActiveEmergencyTrackerPort.

One key per camera holds the active incident's event id. The key carries a TTL
equal to the de-duplication window, so an incident automatically ends when the
camera stops sending emergency frames for ``window_seconds`` (cooldown elapse).
Each new emergency frame ``touch``-es the key, refreshing the TTL and keeping
the incident "alive". Acknowledgement ``clear``-s the key so a brand-new
incident is allowed immediately.

Per-camera independence is intrinsic: the key includes the camera id.
"""

from __future__ import annotations

import redis.asyncio as redis

from src.application.ports.active_emergency_tracker_port import (
    ActiveEmergency,
    ActiveEmergencyTrackerPort,
)

_ACTIVE_KEY = "open_guard:active_emergency:{camera_id}"


class RedisActiveEmergencyTracker(ActiveEmergencyTrackerPort):
    """Stores the active emergency event id per camera with a TTL window."""

    def __init__(self, client: "redis.Redis", window_seconds: int = 60) -> None:
        self._client = client
        self._window_seconds = max(1, int(window_seconds))

    async def get_active(self, camera_id: str) -> ActiveEmergency | None:
        raw = await self._client.get(_ACTIVE_KEY.format(camera_id=camera_id))
        if raw is None:
            return None
        event_id = raw.decode() if isinstance(raw, bytes) else raw
        return ActiveEmergency(camera_id=camera_id, event_id=event_id)

    async def mark_active(self, camera_id: str, event_id: str) -> None:
        await self._client.set(
            _ACTIVE_KEY.format(camera_id=camera_id),
            event_id,
            ex=self._window_seconds,
        )

    async def touch(self, camera_id: str) -> None:
        # Re-set with a refreshed TTL only if the incident still exists.
        key = _ACTIVE_KEY.format(camera_id=camera_id)
        raw = await self._client.get(key)
        if raw is None:
            return
        event_id = raw.decode() if isinstance(raw, bytes) else raw
        await self._client.set(key, event_id, ex=self._window_seconds)

    async def clear(self, camera_id: str) -> None:
        await self._client.delete(_ACTIVE_KEY.format(camera_id=camera_id))
