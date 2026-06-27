"""DTOs for the emergency voice-agent use case.

Plain data contracts: the use case accepts the input DTO and returns the
output DTO, never raw provider objects.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlaceEmergencyCallInputDTO:
    """Input contract for :class:`PlaceEmergencyCallUseCase`.

    ``description`` is editable per call so different emergency scenarios can
    be tried out. When ``to_number`` is omitted the configured default
    on-call number is used.
    """

    description: str
    to_number: str | None = None
    first_message: str | None = None


@dataclass(frozen=True)
class PlaceEmergencyCallOutputDTO:
    """Output contract describing the placed call."""

    to_number: str
    provider_call_id: str
    conversation_id: str | None = None
