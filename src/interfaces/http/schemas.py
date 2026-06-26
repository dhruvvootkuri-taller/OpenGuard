"""Pydantic request/response schemas (presentation-layer validation only).

Schema validation lives here; business rules are enforced in the domain.
"""

from __future__ import annotations

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
