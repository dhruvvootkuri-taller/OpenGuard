"""Domain-level exceptions.

These are pure domain concepts and must not reference any framework,
HTTP status, or infrastructure detail.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain errors."""


class DomainValidationError(DomainError):
    """Raised when a domain invariant is violated."""


class SecurityEventNotFoundError(DomainError):
    """Raised when a requested security event does not exist."""

    def __init__(self, event_id: str) -> None:
        super().__init__(f"Security event '{event_id}' was not found")
        self.event_id = event_id


class EmergencyServiceNotFoundError(DomainError):
    """Raised when a requested emergency service does not exist."""

    def __init__(self, service_id: str) -> None:
        super().__init__(f"Emergency service '{service_id}' was not found")
        self.service_id = service_id


class FeedClipNotFoundError(DomainError):
    """Raised when a requested feed clip does not exist."""

    def __init__(self, clip_id: str) -> None:
        super().__init__(f"Feed clip '{clip_id}' was not found")
        self.clip_id = clip_id


class CallRecordNotFoundError(DomainError):
    """Raised when a requested call record does not exist."""

    def __init__(self, call_id: str) -> None:
        super().__init__(f"Call record '{call_id}' was not found")
        self.call_id = call_id
