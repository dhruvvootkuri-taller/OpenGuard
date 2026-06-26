"""Domain entity: CallRecord.

A log of an outbound call placed by the voice agent (via the telephony
provider). Records who was called, why, what was said, the linked event /
service, and the outcome — forming the call history that the dashboard and
audits read from.

This module imports NOTHING outside the domain layer.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from src.domain.exceptions import DomainValidationError


class CallStatus(str, Enum):
    """Lifecycle status of an outbound call."""

    INITIATED = "initiated"
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no_answer"


@dataclass
class CallRecord:
    """A single outbound call placed by the voice agent.

    Invariants:
      - to_number must be present.
      - transcript holds what the voice agent said / the message played.
    """

    to_number: str
    transcript: str
    event_id: str | None = None
    service_id: str | None = None
    provider_call_id: str | None = None
    status: CallStatus = CallStatus.INITIATED
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
    duration_seconds: float | None = None

    def __post_init__(self) -> None:
        if not self.to_number or not self.to_number.strip():
            raise DomainValidationError("CallRecord requires a non-empty to_number")
        if not self.transcript or not self.transcript.strip():
            raise DomainValidationError("CallRecord requires a transcript")

    # --- Behaviour / invariant-protecting methods -------------------------

    def mark_in_progress(self, provider_call_id: str | None = None) -> None:
        self._transition(
            CallStatus.IN_PROGRESS,
            {CallStatus.INITIATED, CallStatus.RINGING},
        )
        if provider_call_id:
            self.provider_call_id = provider_call_id

    def mark_ringing(self) -> None:
        self._transition(CallStatus.RINGING, {CallStatus.INITIATED})

    def complete(self, duration_seconds: float) -> None:
        if duration_seconds < 0:
            raise DomainValidationError("duration_seconds must be non-negative")
        self._transition(
            CallStatus.COMPLETED,
            {CallStatus.IN_PROGRESS, CallStatus.RINGING, CallStatus.INITIATED},
        )
        self.duration_seconds = duration_seconds
        self.ended_at = datetime.now(timezone.utc)

    def fail(self, reason: CallStatus = CallStatus.FAILED) -> None:
        if reason not in (CallStatus.FAILED, CallStatus.NO_ANSWER):
            raise DomainValidationError("fail reason must be FAILED or NO_ANSWER")
        self.status = reason
        self.ended_at = datetime.now(timezone.utc)

    def _transition(
        self, new_status: CallStatus, allowed_from: set[CallStatus]
    ) -> None:
        if self.status not in allowed_from:
            raise DomainValidationError(
                f"Cannot transition from {self.status.value} to {new_status.value}"
            )
        self.status = new_status
