"""Value Object: DetectionBox.

Immutable bounding box produced by the vision subsystem (e.g. OpenCV).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.exceptions import DomainValidationError


@dataclass(frozen=True)
class DetectionBox:
    """A bounding box around a detected object/person.

    Coordinates are normalised (0.0 .. 1.0) so they are resolution-independent.
    """

    label: str
    confidence: float
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        if not self.label or not self.label.strip():
            raise DomainValidationError("DetectionBox requires a label")
        if not 0.0 <= self.confidence <= 1.0:
            raise DomainValidationError("confidence must be between 0.0 and 1.0")
        for name, value in (("x", self.x), ("y", self.y)):
            if not 0.0 <= value <= 1.0:
                raise DomainValidationError(f"{name} must be normalised between 0 and 1")
        for name, value in (("width", self.width), ("height", self.height)):
            if not 0.0 < value <= 1.0:
                raise DomainValidationError(f"{name} must be in (0, 1]")

    @property
    def area(self) -> float:
        return self.width * self.height

    def is_person(self) -> bool:
        return self.label.lower() == "person"
