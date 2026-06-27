"""Port (abstraction) for a vision model that assesses camera frames.

Defined in the application layer so the feed use case can depend on it
without knowing it is Claude vision underneath. Infrastructure implements it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.value_objects.emergency_assessment import EmergencyAssessment


class VisionAnalyzerError(RuntimeError):
    """Raised when the vision provider fails to assess a frame.

    The feed use case lets this propagate rather than treating a provider
    failure as a silent "all clear" — a bad API key or retired model must be
    visible, not hidden.
    """


class VisionAnalyzerPort(ABC):
    """Abstraction over a vision model used to assess a single frame."""

    @abstractmethod
    async def assess_frame(
        self,
        image_base64: str,
        media_type: str,
        is_armed_zone: bool,
        zone: str,
    ) -> EmergencyAssessment:
        """Assess one frame and return an EmergencyAssessment.

        Args:
            image_base64: Raw base64-encoded image bytes (no ``data:`` prefix).
            media_type: The image MIME type, e.g. ``image/jpeg``.
            is_armed_zone: Whether the camera watches an armed/restricted zone.
            zone: Human-readable zone label for context.

        Raises:
            VisionAnalyzerError: If the provider call fails.
        """
        raise NotImplementedError
