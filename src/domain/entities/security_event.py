"""Domain entity: SecurityEvent.

Represents a detected security event in the Open Guard system.
Entities have identity and protect their own invariants.

This module imports NOTHING outside the domain layer.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from src.domain.value_objects.threat_level import ThreatLevel
from src.domain.value_objects.detection_box import DetectionBox
from src.domain.exceptions import DomainValidationError


class SecurityEventStatus(str, Enum):
    """Lifecycle status of a security event."""

    DETECTED = "detected"
    ANALYZING = "analyzing"
    ALERTING = "alerting"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


@dataclass
class SecurityEvent:
    """A security event raised by the camera/vision subsystem.

    Invariants:
      - A camera_id must always be present.
      - At least one detection box must exist.
      - threat_level must be a valid ThreatLevel value object.
    """

    camera_id: str
    threat_level: ThreatLevel
    detections: list[DetectionBox]
    description: str = ""
    status: SecurityEventStatus = SecurityEventStatus.DETECTED
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_by: str | None = None

    def __post_init__(self) -> None:
        if not self.camera_id or not self.camera_id.strip():
            raise DomainValidationError("SecurityEvent requires a non-empty camera_id")
        if not self.detections:
            raise DomainValidationError(
                "SecurityEvent requires at least one detection box"
            )
        if not isinstance(self.threat_level, ThreatLevel):
            raise DomainValidationError("threat_level must be a ThreatLevel value object")

    # --- Behaviour / invariant-protecting methods -------------------------

    def requires_human_escalation(self) -> bool:
        """Business rule: high/critical threats always escalate to a human."""
        return self.threat_level.is_at_least_high()

    def mark_analyzing(self) -> None:
        self._transition(SecurityEventStatus.ANALYZING, {SecurityEventStatus.DETECTED})

    def mark_alerting(self) -> None:
        self._transition(
            SecurityEventStatus.ALERTING,
            {SecurityEventStatus.DETECTED, SecurityEventStatus.ANALYZING},
        )

    def acknowledge(self, operator_id: str) -> None:
        if not operator_id or not operator_id.strip():
            raise DomainValidationError("operator_id is required to acknowledge an event")
        self._transition(
            SecurityEventStatus.ACKNOWLEDGED,
            {SecurityEventStatus.ALERTING, SecurityEventStatus.ANALYZING},
        )
        self.acknowledged_by = operator_id

    def resolve(self) -> None:
        self._transition(
            SecurityEventStatus.RESOLVED,
            {SecurityEventStatus.ACKNOWLEDGED, SecurityEventStatus.ALERTING},
        )

    def dismiss(self) -> None:
        self._transition(
            SecurityEventStatus.DISMISSED,
            {
                SecurityEventStatus.DETECTED,
                SecurityEventStatus.ANALYZING,
                SecurityEventStatus.ACKNOWLEDGED,
            },
        )

    def _transition(
        self, new_status: SecurityEventStatus, allowed_from: set[SecurityEventStatus]
    ) -> None:
        if self.status not in allowed_from:
            raise DomainValidationError(
                f"Cannot transition from {self.status.value} to {new_status.value}"
            )
        self.status = new_status
