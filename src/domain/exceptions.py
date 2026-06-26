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
