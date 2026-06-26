"""Domain entity: FeedClip.

A recorded MP4 segment of a camera feed that was captured because an
emergency was detected. It carries an overall emergency description plus a
timeline of timestamped descriptions of what is happening in the feed, so
the voice agent can pick up the *exact* description of what is going on at a
given moment when narrating an emergency call.

This module imports NOTHING outside the domain layer.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.domain.exceptions import DomainValidationError
from src.domain.value_objects.feed_segment import FeedDescriptionSegment


@dataclass
class FeedClip:
    """A stored MP4 clip with timed descriptions of feed activity.

    Invariants:
      - camera_id and video_url (location of the MP4) must be present.
      - duration_seconds must be positive.
      - emergency_description summarises the whole clip.
    """

    camera_id: str
    video_url: str
    emergency_description: str
    duration_seconds: float
    event_id: str | None = None
    segments: list[FeedDescriptionSegment] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.camera_id or not self.camera_id.strip():
            raise DomainValidationError("FeedClip requires a non-empty camera_id")
        if not self.video_url or not self.video_url.strip():
            raise DomainValidationError("FeedClip requires a non-empty video_url")
        if not self.emergency_description or not self.emergency_description.strip():
            raise DomainValidationError(
                "FeedClip requires a non-empty emergency_description"
            )
        if self.duration_seconds <= 0:
            raise DomainValidationError("duration_seconds must be positive")
        # Keep the timeline ordered so lookups are deterministic.
        self.segments = sorted(self.segments, key=lambda s: s.offset_seconds)

    # --- Behaviour / invariant-protecting methods -------------------------

    def add_segment(self, segment: FeedDescriptionSegment) -> None:
        """Append a timed description, keeping the timeline ordered."""
        if segment.offset_seconds > self.duration_seconds:
            raise DomainValidationError(
                "segment offset is beyond the clip duration"
            )
        self.segments.append(segment)
        self.segments.sort(key=lambda s: s.offset_seconds)

    def description_at(self, at_seconds: float) -> str:
        """Return the description active at `at_seconds`.

        This is what the voice agent calls to know exactly what is happening
        at a particular moment in the feed. Falls back to the overall
        emergency description when no segment covers the moment.
        """
        if at_seconds < 0:
            raise DomainValidationError("at_seconds must be non-negative")
        active = self.emergency_description
        for index, segment in enumerate(self.segments):
            until = (
                self.segments[index + 1].offset_seconds
                if index + 1 < len(self.segments)
                else self.duration_seconds + 1
            )
            if segment.covers(at_seconds, until):
                active = segment.description
                break
        return active

    def timeline(self) -> list[FeedDescriptionSegment]:
        """Ordered timeline of timed descriptions (defensive copy)."""
        return list(self.segments)
