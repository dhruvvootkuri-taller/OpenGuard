"""In-memory sliding-window implementation of DetectionConfirmationPort.

Keeps, per camera, an ordered window of the last ``window`` flagged labels and
reports a detection as *confirmed* once the same label appears in at least
``required`` of those slots (an "M of last K" rule). This collapses stochastic
one-frame vision hits into sustained, trustworthy detections before any event
or escalation is raised.

State is per-process. For the single-worker dev/demo setup that is sufficient;
a Redis-backed implementation could share state across workers if needed.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Deque, Dict

from src.application.ports.detection_confirmation_port import (
    DetectionConfirmationPort,
)


class InMemoryDetectionConfirmationTracker(DetectionConfirmationPort):
    """M-of-last-K confirmation window, keyed per camera."""

    def __init__(self, window: int = 3, required: int = 2) -> None:
        if window < 1:
            raise ValueError("window must be >= 1")
        if required < 1:
            raise ValueError("required must be >= 1")
        if required > window:
            raise ValueError("required must be <= window")
        self._window = window
        self._required = required
        # camera_id -> deque of the last `window` flagged labels.
        self._frames: Dict[str, Deque[str]] = defaultdict(
            lambda: deque(maxlen=self._window)
        )

    def record_and_check(self, camera_id: str, label: str) -> bool:
        frames = self._frames[camera_id]
        frames.append(label)
        occurrences = sum(1 for seen in frames if seen == label)
        return occurrences >= self._required

    def reset(self, camera_id: str) -> None:
        self._frames.pop(camera_id, None)
