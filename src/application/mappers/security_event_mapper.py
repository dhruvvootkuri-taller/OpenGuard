"""Mapper: domain SecurityEvent <-> DTOs.

Keeps translation logic out of use cases and controllers.
"""

from __future__ import annotations

from src.application.dtos.detection_dtos import DetectionBoxDTO, SecurityEventDTO
from src.domain.entities.security_event import SecurityEvent


class SecurityEventMapper:
    @staticmethod
    def to_dto(event: SecurityEvent) -> SecurityEventDTO:
        return SecurityEventDTO(
            id=event.id,
            camera_id=event.camera_id,
            status=event.status.value,
            threat_severity=event.threat_level.severity.name,
            threat_confidence=event.threat_level.confidence,
            description=event.description,
            detected_at=event.detected_at.isoformat(),
            escalated=event.requires_human_escalation(),
            detections=[
                DetectionBoxDTO(
                    label=d.label,
                    confidence=d.confidence,
                    x=d.x,
                    y=d.y,
                    width=d.width,
                    height=d.height,
                )
                for d in event.detections
            ],
        )
