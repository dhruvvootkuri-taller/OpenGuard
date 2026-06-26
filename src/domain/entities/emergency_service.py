"""Domain entity: EmergencyService.

A helpline / emergency service the system can call. Users maintain this
catalogue (adding their local police, fire, medical, private security, etc.)
and the voice agent pulls from it — matching the situation against each
service's `description` — to decide who to call.

This module imports NOTHING outside the domain layer.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from src.domain.exceptions import DomainValidationError


class EmergencyServiceCategory(str, Enum):
    """High-level category of an emergency service."""

    POLICE = "police"
    FIRE = "fire"
    MEDICAL = "medical"
    SECURITY = "security"
    UTILITY = "utility"
    OTHER = "other"


@dataclass
class EmergencyService:
    """A callable emergency service / helpline.

    Invariants:
      - name and phone_number must be present.
      - description must be present (the voice agent matches against it).
      - priority is a positive ordering hint (lower == try first).
    """

    name: str
    phone_number: str
    description: str
    category: EmergencyServiceCategory = EmergencyServiceCategory.OTHER
    priority: int = 100
    is_active: bool = True
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise DomainValidationError("EmergencyService requires a non-empty name")
        if not self.phone_number or not self.phone_number.strip():
            raise DomainValidationError(
                "EmergencyService requires a non-empty phone_number"
            )
        if not self.description or not self.description.strip():
            raise DomainValidationError(
                "EmergencyService requires a description for the voice agent to match"
            )
        if self.priority <= 0:
            raise DomainValidationError("priority must be a positive integer")

    # --- Behaviour / invariant-protecting methods -------------------------

    def deactivate(self) -> None:
        """Soft-disable so it is never called without losing its history."""
        self.is_active = False

    def reactivate(self) -> None:
        self.is_active = True

    def update_description(self, description: str) -> None:
        if not description or not description.strip():
            raise DomainValidationError("description cannot be empty")
        self.description = description

    def matches(self, keyword: str) -> bool:
        """Cheap text match used by the voice agent to shortlist services."""
        needle = keyword.lower().strip()
        if not needle:
            return False
        return (
            needle in self.name.lower()
            or needle in self.description.lower()
            or needle == self.category.value
        )
