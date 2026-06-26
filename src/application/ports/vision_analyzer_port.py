"""Port (abstraction) for an emergency vision analyser.

Defined in the application layer so use cases can ask "is there an emergency
in this frame?" without knowing that **Anthropic Claude vision** sits
underneath. Infrastructure implements it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.value_objects.emergency_assessment import EmergencyAssessment


class VisionAnalyzerPort(ABC):
    """Abstraction over a vision model that detects emergencies in a frame."""

    @abstractmethod
    async def analyze_frame(
        self, image_base64: str, media_type: str = "image/jpeg", context: str = ""
    ) -> EmergencyAssessment:
        """Inspect a single camera frame and return an EmergencyAssessment.

        ``image_base64`` is the raw (un-prefixed) base64 of the frame image.
        ``context`` is optional free text about the camera/zone the frame
        came from. Implementations must never raise on a model/parse error —
        they return ``EmergencyAssessment.none()`` instead so a live feed is
        never interrupted.
        """
        raise NotImplementedError
