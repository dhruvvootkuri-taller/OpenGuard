"""Redis implementation of the CallRecordRepository domain interface.

Stores each call as a JSON blob, indexed by a recency sorted-set and a
per-event set so the full call history for an event can be retrieved.
Contains NO business logic — only persistence concerns.
"""

from __future__ import annotations

import json
from datetime import datetime

import redis.asyncio as redis

from src.domain.entities.call_record import CallRecord, CallStatus
from src.domain.repositories.call_record_repository import CallRecordRepository

_CALL_KEY = "open_guard:call:{call_id}"
_RECENT_KEY = "open_guard:calls:recent"
_EVENT_INDEX_KEY = "open_guard:calls:event:{event_id}"


class RedisCallRecordRepository(CallRecordRepository):
    """Stores call records as JSON blobs indexed by recency and event."""

    def __init__(self, client: "redis.Redis") -> None:
        self._client = client

    async def save(self, call: CallRecord) -> None:
        payload = json.dumps(self._to_record(call))
        await self._client.set(_CALL_KEY.format(call_id=call.id), payload)
        await self._client.zadd(_RECENT_KEY, {call.id: call.started_at.timestamp()})
        if call.event_id:
            await self._client.sadd(
                _EVENT_INDEX_KEY.format(event_id=call.event_id), call.id
            )

    async def get_by_id(self, call_id: str) -> CallRecord | None:
        raw = await self._client.get(_CALL_KEY.format(call_id=call_id))
        if raw is None:
            return None
        return self._to_entity(json.loads(raw))

    async def get_by_event_id(self, event_id: str) -> list[CallRecord]:
        ids = await self._client.smembers(
            _EVENT_INDEX_KEY.format(event_id=event_id)
        )
        calls: list[CallRecord] = []
        for call_id in ids:
            decoded = call_id.decode() if isinstance(call_id, bytes) else call_id
            call = await self.get_by_id(decoded)
            if call is not None:
                calls.append(call)
        calls.sort(key=lambda c: c.started_at)
        return calls

    async def list_recent(self, limit: int = 50) -> list[CallRecord]:
        ids = await self._client.zrevrange(_RECENT_KEY, 0, max(0, limit - 1))
        calls: list[CallRecord] = []
        for call_id in ids:
            decoded = call_id.decode() if isinstance(call_id, bytes) else call_id
            call = await self.get_by_id(decoded)
            if call is not None:
                calls.append(call)
        return calls

    # --- mapping helpers --------------------------------------------------

    @staticmethod
    def _to_record(call: CallRecord) -> dict:
        return {
            "id": call.id,
            "to_number": call.to_number,
            "transcript": call.transcript,
            "event_id": call.event_id,
            "service_id": call.service_id,
            "provider_call_id": call.provider_call_id,
            "status": call.status.value,
            "started_at": call.started_at.isoformat(),
            "ended_at": call.ended_at.isoformat() if call.ended_at else None,
            "duration_seconds": call.duration_seconds,
        }

    @staticmethod
    def _to_entity(record: dict) -> CallRecord:
        ended_at = record.get("ended_at")
        call = CallRecord(
            id=record["id"],
            to_number=record["to_number"],
            transcript=record["transcript"],
            event_id=record.get("event_id"),
            service_id=record.get("service_id"),
            provider_call_id=record.get("provider_call_id"),
            started_at=datetime.fromisoformat(record["started_at"]),
            ended_at=datetime.fromisoformat(ended_at) if ended_at else None,
            duration_seconds=record.get("duration_seconds"),
        )
        # Restore persisted lifecycle state directly (bypassing transitions).
        call.status = CallStatus(record["status"])
        return call
