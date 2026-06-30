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


class EscalationOutcome(str, Enum):
    """Final outcome of trying to reach an on-call human for an event.

    ``PENDING`` means escalation has not run or is still in flight.
    ``REACHED`` means a contact answered the escalation call.
    ``UNREACHABLE`` means every configured contact was tried (with retries) and
    none answered — the dashboard must surface this so help can be summoned by
    other means.
    """

    PENDING = "pending"
    REACHED = "reached"
    UNREACHABLE = "unreachable"


# Statuses that take an event out of the active views permanently.
_TERMINAL_STATUSES = frozenset(
    {SecurityEventStatus.RESOLVED, SecurityEventStatus.DISMISSED}
)


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
    last_seen_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    acknowledged_by: str | None = None
    escalation_outcome: EscalationOutcome = EscalationOutcome.PENDING
    # The contact (phone number) actually reached, when REACHED.
    escalation_reached_contact: str | None = None
    # How many distinct contacts were attempted during escalation.
    escalation_attempts: int = 0

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

    def record_escalation_reached(self, contact: str, *, attempts: int) -> None:
        """Record that escalation reached a human on ``contact``."""
        if not contact or not contact.strip():
            raise DomainValidationError("contact is required to record a reach")
        if attempts < 1:
            raise DomainValidationError("attempts must be at least 1")
        self.escalation_outcome = EscalationOutcome.REACHED
        self.escalation_reached_contact = contact
        self.escalation_attempts = attempts

    def record_escalation_unreachable(self, *, attempts: int) -> None:
        """Record that escalation exhausted every contact without an answer."""
        if attempts < 1:
            raise DomainValidationError("attempts must be at least 1")
        self.escalation_outcome = EscalationOutcome.UNREACHABLE
        self.escalation_reached_contact = None
        self.escalation_attempts = attempts

    def acknowledge(self, operator_id: str) -> None:
        if not operator_id or not operator_id.strip():
            raise DomainValidationError("operator_id is required to acknowledge an event")
        self._transition(
            SecurityEventStatus.ACKNOWLEDGED,
            {SecurityEventStatus.ALERTING, SecurityEventStatus.ANALYZING},
        )
        self.acknowledged_by = operator_id

    def resolve(self) -> None:
        """Operator marks the incident handled. Allowed from any active state.

        Resolving a never-seen-again event is the normal way to clear a one-off
        detection from the active views; escalated events stay visible in Call
        History as an audit trail.
        """
        if self.status in _TERMINAL_STATUSES:
            raise DomainValidationError(
                f"Cannot resolve an event that is already {self.status.value}"
            )
        self.status = SecurityEventStatus.RESOLVED

    def dismiss(self) -> None:
        """Operator dismisses a non-incident. Allowed from any active state."""
        if self.status in _TERMINAL_STATUSES:
            raise DomainValidationError(
                f"Cannot dismiss an event that is already {self.status.value}"
            )
        self.status = SecurityEventStatus.DISMISSED

    def touch(self, when: datetime | None = None) -> None:
        """Record fresh activity (a new frame/detection) on this incident.

        Keeps the event 'active' so the inactivity-based auto-expiry does not
        resolve an incident that is still producing frames.
        """
        self.last_seen_at = when or datetime.now(timezone.utc)

    def is_terminal(self) -> bool:
        """True once the event has been resolved or dismissed."""
        return self.status in _TERMINAL_STATUSES

    def is_active(self) -> bool:
        """True while the event still belongs in the live/active views."""
        return not self.is_terminal()

    def is_stale(self, *, now: datetime, ttl_seconds: float) -> bool:
        """True if no new activity has been seen for longer than ``ttl_seconds``.

        Terminal events are never stale (they are already off the active views).
        """
        if self.is_terminal() or ttl_seconds <= 0:
            return False
        return (now - self.last_seen_at).total_seconds() >= ttl_seconds

    def expire(self) -> None:
        """Auto-resolve a stale active event (no operator involved)."""
        if self.is_terminal():
            return
        self.status = SecurityEventStatus.RESOLVED

    def _transition(
        self, new_status: SecurityEventStatus, allowed_from: set[SecurityEventStatus]
    ) -> None:
        if self.status not in allowed_from:
            raise DomainValidationError(
                f"Cannot transition from {self.status.value} to {new_status.value}"
            )
        self.status = new_status
