"""Value Object: EmergencyAssessment.

Immutable verdict produced by a vision model for a single camera frame.
It answers the only question the feed pipeline cares about: *is this frame
an emergency, and if so, how serious and where?*

This module imports NOTHING outside the domain layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.domain.exceptions import DomainValidationError
from src.domain.value_objects.detection_box import DetectionBox


@dataclass(frozen=True)
class EmergencyAssessment:
    """A vision model's verdict for one analysed frame.

    ``threat_score`` is a normalised 0..1 severity estimate. ``box`` is the
    optional region of interest the model flagged. When ``is_emergency`` is
    ``False`` the rest of the fields describe a benign scene.
    """

    is_emergency: bool
    threat_score: float
    confidence: float
    label: str
    summary: str
    box: Optional[DetectionBox] = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.threat_score <= 1.0:
            raise DomainValidationError("threat_score must be between 0.0 and 1.0")
        if not 0.0 <= self.confidence <= 1.0:
            raise DomainValidationError("confidence must be between 0.0 and 1.0")
        if not self.label or not self.label.strip():
            raise DomainValidationError("EmergencyAssessment requires a label")

    @classmethod
    def all_clear(cls, label: str = "all clear", summary: str = "") -> "EmergencyAssessment":
        """A benign verdict: no emergency detected."""
        return cls(
            is_emergency=False,
            threat_score=0.0,
            confidence=1.0,
            label=label,
            summary=summary or "No emergency detected in frame.",
            box=None,
        )
