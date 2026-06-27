"""Port (abstraction) for multi-frame detection confirmation.

Vision verdicts on ambiguous frames are stochastic, so a single frame the
model flags as an emergency must not be trusted on its own. This port records
each (camera, label) observation in a sliding window and reports whether the
same emergency has *persisted* across enough recent frames to be treated as a
confirmed detection rather than a one-frame false alarm.

Defined in the application layer so the feed use case can depend on it without
knowing how the window is stored. Infrastructure implements it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class DetectionConfirmationPort(ABC):
    """Tracks whether an emergency persists across a confirmation window."""

    @abstractmethod
    def record_and_check(self, camera_id: str, label: str) -> bool:
        """Record a confirmed-above-threshold emergency frame and report status.

        Records one positive observation for ``(camera_id, label)`` in the
        sliding window and returns ``True`` when the same emergency has now been
        observed in at least ``required`` of the last ``window`` frames for that
        camera — i.e. it is *confirmed* and may become an event/escalation.

        Args:
            camera_id: The camera the frame came from.
            label: The emergency label the vision model flagged.

        Returns:
            ``True`` if the detection is confirmed (sustained), else ``False``.
        """
        raise NotImplementedError

    @abstractmethod
    def reset(self, camera_id: str) -> None:
        """Clear the confirmation window for a camera (e.g. after an event)."""
        raise NotImplementedError
