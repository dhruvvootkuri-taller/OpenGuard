"""Port (abstraction) for tracking the active emergency per camera.

De-duplication concern: a single physical incident (e.g. a 30s fire) produces
many emergency frames. Without bookkeeping, each frame would create a new
``SecurityEvent`` and re-enqueue an escalation call. This port records, per
camera, the currently-active *unacknowledged* emergency and when it was last
seen so the use cases can collapse repeated frames into one incident.

State semantics:
  * ``get_active(camera_id)`` returns the active emergency for a camera if one
    exists and is still within the cooldown window; otherwise ``None`` (the
    previous incident has ended via cooldown elapse).
  * ``mark_active`` registers a freshly-created event as the camera's active
    incident.
  * ``touch`` refreshes the last-seen time of an existing incident (extends the
    cooldown) without creating anything new.
  * ``clear`` ends the incident immediately (used on acknowledgement).

This lives in the application layer so use cases depend only on the
abstraction; infrastructure supplies a Redis-backed implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ActiveEmergency:
    """A pointer to the event id representing a camera's ongoing incident."""

    camera_id: str
    event_id: str


class ActiveEmergencyTrackerPort(ABC):
    """Abstraction over per-camera active-emergency bookkeeping."""

    @abstractmethod
    async def get_active(self, camera_id: str) -> ActiveEmergency | None:
        """Return the camera's active, non-expired emergency, or ``None``."""
        raise NotImplementedError

    @abstractmethod
    async def mark_active(self, camera_id: str, event_id: str) -> None:
        """Register ``event_id`` as the camera's active incident."""
        raise NotImplementedError

    @abstractmethod
    async def touch(self, camera_id: str) -> None:
        """Refresh the last-seen time of the camera's active incident."""
        raise NotImplementedError

    @abstractmethod
    async def clear(self, camera_id: str) -> None:
        """End the camera's active incident immediately (e.g. on ack)."""
        raise NotImplementedError
