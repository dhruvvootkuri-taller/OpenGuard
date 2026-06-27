"""Pydantic request/response schemas (presentation-layer validation only).

Schema validation lives here; business rules are enforced in the domain.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class DetectionBoxSchema(BaseModel):
    label: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    width: float = Field(..., gt=0.0, le=1.0)
    height: float = Field(..., gt=0.0, le=1.0)


class ProcessDetectionRequest(BaseModel):
    camera_id: str = Field(..., min_length=1)
    detections: list[DetectionBoxSchema] = Field(..., min_length=1)
    is_armed_zone: bool = False
    description: str = ""


class AcknowledgeRequest(BaseModel):
    operator_id: str = Field(..., min_length=1)


class EmergencyCallRequest(BaseModel):
    """Request to place an interactive emergency-helpline call.

    ``description`` is editable per call so different scenarios can be tested.
    ``to_number`` defaults to the configured on-call number when omitted.
    """

    description: str = Field(..., min_length=1)
    to_number: Optional[str] = None
    first_message: Optional[str] = None


class EmergencyCallResponse(BaseModel):
    to_number: str
    provider_call_id: str
    conversation_id: Optional[str] = None


class DetectionBoxResponse(BaseModel):
    label: str
    confidence: float
    x: float
    y: float
    width: float
    height: float


class SecurityEventResponse(BaseModel):
    id: str
    camera_id: str
    status: str
    threat_severity: str
    threat_confidence: float
    description: str
    detected_at: str
    escalated: bool
    detections: list[DetectionBoxResponse]


class AnalyzeFrameRequest(BaseModel):
    """A single frame captured from a playing MP4 feed.

    ``image_base64`` is raw base64-encoded JPEG bytes (no ``data:`` prefix).
    """

    image_base64: str = Field(..., min_length=1)
    media_type: str = "image/jpeg"
    is_armed_zone: bool = False
    zone: str = ""


class AnalyzeFrameResponse(BaseModel):
    camera_id: str
    is_emergency: bool
    label: str
    summary: str
    # NOTE: use Optional[...] (never a quoted union + model_rebuild) so the
    # schema resolves on Python 3.9 — a quoted "SecurityEventResponse | None"
    # raises TypeError at model_rebuild() time there.
    event: Optional[SecurityEventResponse] = None
    # A candidate is a flagged-but-gated detection (below threshold or not yet
    # confirmed across frames). The UI may show it as a low-severity watch
    # signal; it never created an event and never placed a call.
    is_candidate: bool = False
    candidate_reason: str = ""
