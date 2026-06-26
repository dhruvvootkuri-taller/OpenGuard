"""Redis implementation of the SecurityEventRepository domain interface.

Maps Redis hashes/sorted-sets <-> domain SecurityEvent entities.
Contains NO business logic — only persistence concerns.
"""

from __future__ import annotations

import json
from datetime import datetime

import redis.asyncio as redis

from src.domain.entities.security_event import SecurityEvent, SecurityEventStatus
from src.domain.repositories.security_event_repository import (
    SecurityEventRepository,
)
from src.domain.value_objects.detection_box import DetectionBox
from src.domain.value_objects.threat_level import ThreatLevel, ThreatSeverity

_EVENT_KEY = "open_guard:event:{event_id}"
_RECENT_KEY = "open_guard:events:recent"


class RedisSecurityEventRepository(SecurityEventRepository):
    """Stores security events as JSON blobs indexed by a sorted set."""

    def __init__(self, client: "redis.Redis") -> None:
        self._client = client

    async def save(self, event: SecurityEvent) -> None:
        payload = json.dumps(self._to_record(event))
        key = _EVENT_KEY.format(event_id=event.id)
        await self._client.set(key, payload)
        await self._client.zadd(
            _RECENT_KEY, {event.id: event.detected_at.timestamp()}
        )

    async def get_by_id(self, event_id: str) -> SecurityEvent | None:
        raw = await self._client.get(_EVENT_KEY.format(event_id=event_id))
        if raw is None:
            return None
        return self._to_entity(json.loads(raw))

    async def list_recent(self, limit: int = 50) -> list[SecurityEvent]:
        ids = await self._client.zrevrange(_RECENT_KEY, 0, max(0, limit - 1))
        events: list[SecurityEvent] = []
        for event_id in ids:
            decoded = event_id.decode() if isinstance(event_id, bytes) else event_id
            event = await self.get_by_id(decoded)
            if event is not None:
                events.append(event)
        return events

    # --- mapping helpers --------------------------------------------------

    @staticmethod
    def _to_record(event: SecurityEvent) -> dict:
        return {
            "id": event.id,
            "camera_id": event.camera_id,
            "status": event.status.value,
            "description": event.description,
            "detected_at": event.detected_at.isoformat(),
            "acknowledged_by": event.acknowledged_by,
            "threat": {
                "severity": event.threat_level.severity.name,
                "confidence": event.threat_level.confidence,
            },
            "detections": [
                {
                    "label": d.label,
                    "confidence": d.confidence,
                    "x": d.x,
                    "y": d.y,
                    "width": d.width,
                    "height": d.height,
                }
                for d in event.detections
            ],
        }

    @staticmethod
    def _to_entity(record: dict) -> SecurityEvent:
        threat = ThreatLevel(
            severity=ThreatSeverity[record["threat"]["severity"]],
            confidence=record["threat"]["confidence"],
        )
        detections = [
            DetectionBox(
                label=d["label"],
                confidence=d["confidence"],
                x=d["x"],
                y=d["y"],
                width=d["width"],
                height=d["height"],
            )
            for d in record["detections"]
        ]
        event = SecurityEvent(
            camera_id=record["camera_id"],
            threat_level=threat,
            detections=detections,
            description=record["description"],
            id=record["id"],
            detected_at=datetime.fromisoformat(record["detected_at"]),
        )
        # Restore persisted lifecycle state directly (bypassing transitions).
        event.status = SecurityEventStatus(record["status"])
        event.acknowledged_by = record.get("acknowledged_by")
        return event
