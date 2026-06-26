"""Value Object: FeedDescriptionSegment.

Immutable description of what is happening in a camera feed at a specific
offset within a recorded clip. The voice agent uses the timeline of these
segments to narrate the *exact* description of what is going on at a given
moment when it places an emergency call.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.exceptions import DomainValidationError


@dataclass(frozen=True)
class FeedDescriptionSegment:
    """A timestamped natural-language description of feed activity.

    `offset_seconds` is relative to the start of the owning clip so a clip
    is self-contained and resolution/wall-clock independent.
    """

    offset_seconds: float
    description: str

    def __post_init__(self) -> None:
        if self.offset_seconds < 0:
            raise DomainValidationError("offset_seconds must be non-negative")
        if not self.description or not self.description.strip():
            raise DomainValidationError(
                "FeedDescriptionSegment requires a non-empty description"
            )

    def covers(self, at_seconds: float, until_seconds: float) -> bool:
        """True if this segment is the active description at `at_seconds`.

        A segment is active from its own offset until the next segment's
        offset (`until_seconds`), which the caller supplies.
        """
        return self.offset_seconds <= at_seconds < until_seconds
