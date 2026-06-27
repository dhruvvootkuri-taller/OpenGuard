"""DTOs for use case input/output.

DTOs are plain data contracts. Use cases accept input DTOs and return
output DTOs — never raw domain entities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class DetectionBoxDTO:
    label: str
    confidence: float
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class ProcessDetectionInputDTO:
    """Input contract for the ProcessDetectionUseCase."""

    camera_id: str
    detections: list[DetectionBoxDTO]
    is_armed_zone: bool = False
    description: str = ""


@dataclass(frozen=True)
class SecurityEventDTO:
    """Output contract representing a security event."""

    id: str
    camera_id: str
    status: str
    threat_severity: str
    threat_confidence: float
    description: str
    detected_at: str
    escalated: bool
    detections: list[DetectionBoxDTO] = field(default_factory=list)


@dataclass(frozen=True)
class AcknowledgeEventInputDTO:
    event_id: str
    operator_id: str


@dataclass(frozen=True)
class AnalyzeFrameInputDTO:
    """Input contract for the AnalyzeFeedFrameUseCase.

    ``image_base64`` is raw base64-encoded image bytes (no ``data:`` prefix).
    """

    camera_id: str
    image_base64: str
    media_type: str = "image/jpeg"
    is_armed_zone: bool = False
    zone: str = ""


@dataclass(frozen=True)
class AnalyzeFrameOutputDTO:
    """Output contract for a single analysed frame.

    ``event`` is populated only when the vision model confirms an emergency
    and a SecurityEvent was created; otherwise it is ``None``.
    """

    camera_id: str
    is_emergency: bool
    label: str
    summary: str
    event: Optional[SecurityEventDTO] = None
