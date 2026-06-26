"""Value Object: EmergencyAssessment.

Immutable result of analysing a single camera-feed frame for an emergency.
Produced by the vision subsystem (e.g. an LLM that "looks" at a frame) and
consumed by the application layer to decide whether a SecurityEvent should be
raised.

This module imports NOTHING outside the domain layer.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.exceptions import DomainValidationError


@dataclass(frozen=True)
class EmergencyAssessment:
    """A frame-level verdict on whether an emergency is occurring.

    Fields:
      - is_emergency: True only when the analyser is confident an emergency
        is actually happening. When False the feed should do nothing.
      - label: short category of the situation (e.g. "fire", "assault",
        "person"). Always present so a DetectionBox can be derived.
      - score: 0..1 severity score mapped onto a ThreatLevel downstream.
      - confidence: 0..1 confidence in the assessment.
      - summary: one-line human-readable description of the situation.
      - x/y/width/height: normalised (0..1) bounding box of the area of
        concern. Defaults cover the full frame when the analyser cannot
        localise the event.
    """

    is_emergency: bool
    label: str
    score: float
    confidence: float
    summary: str = ""
    x: float = 0.0
    y: float = 0.0
    width: float = 1.0
    height: float = 1.0

    def __post_init__(self) -> None:
        if not self.label or not self.label.strip():
            raise DomainValidationError("EmergencyAssessment requires a label")
        for name, value in (("score", self.score), ("confidence", self.confidence)):
            if not 0.0 <= value <= 1.0:
                raise DomainValidationError(f"{name} must be between 0.0 and 1.0")
        for name, value in (("x", self.x), ("y", self.y)):
            if not 0.0 <= value <= 1.0:
                raise DomainValidationError(f"{name} must be normalised between 0 and 1")
        for name, value in (("width", self.width), ("height", self.height)):
            if not 0.0 < value <= 1.0:
                raise DomainValidationError(f"{name} must be in (0, 1]")

    @classmethod
    def none(cls) -> "EmergencyAssessment":
        """A safe, non-emergency assessment (used when nothing is detected)."""
        return cls(
            is_emergency=False,
            label="clear",
            score=0.0,
            confidence=1.0,
            summary="No emergency detected.",
        )
