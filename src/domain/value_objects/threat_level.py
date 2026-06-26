"""Value Object: ThreatLevel.

Immutable, compared by value. Encapsulates the rules around how
serious a detected security event is.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from src.domain.exceptions import DomainValidationError


class ThreatSeverity(IntEnum):
    """Ordered severity. Higher int == more severe."""

    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(frozen=True)
class ThreatLevel:
    """A value object describing the severity of a threat.

    Equality is by value (frozen dataclass), and the object is immutable.
    """

    severity: ThreatSeverity
    confidence: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise DomainValidationError("confidence must be between 0.0 and 1.0")

    def is_at_least_high(self) -> bool:
        return self.severity >= ThreatSeverity.HIGH

    def is_actionable(self) -> bool:
        """A threat is actionable when severity >= MEDIUM and confident enough."""
        return self.severity >= ThreatSeverity.MEDIUM and self.confidence >= 0.6

    @classmethod
    def from_score(cls, score: float, confidence: float) -> "ThreatLevel":
        """Factory mapping a 0..1 threat score onto a discrete severity."""
        if not 0.0 <= score <= 1.0:
            raise DomainValidationError("score must be between 0.0 and 1.0")
        if score >= 0.9:
            severity = ThreatSeverity.CRITICAL
        elif score >= 0.7:
            severity = ThreatSeverity.HIGH
        elif score >= 0.4:
            severity = ThreatSeverity.MEDIUM
        elif score >= 0.15:
            severity = ThreatSeverity.LOW
        else:
            severity = ThreatSeverity.INFO
        return cls(severity=severity, confidence=confidence)

    def __str__(self) -> str:
        return f"{self.severity.name} ({self.confidence:.0%})"
