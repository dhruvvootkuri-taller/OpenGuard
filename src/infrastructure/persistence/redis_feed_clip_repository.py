"""Redis implementation of the FeedClipRepository domain interface.

Stores each clip as a JSON blob, indexed by a recency sorted-set and a
per-event set so all clips for an event can be retrieved.
Contains NO business logic — only persistence concerns.
"""

from __future__ import annotations

import json
from datetime import datetime

import redis.asyncio as redis

from src.domain.entities.feed_clip import FeedClip
from src.domain.repositories.feed_clip_repository import FeedClipRepository
from src.domain.value_objects.feed_segment import FeedDescriptionSegment

_CLIP_KEY = "open_guard:clip:{clip_id}"
_RECENT_KEY = "open_guard:clips:recent"
_EVENT_INDEX_KEY = "open_guard:clips:event:{event_id}"


class RedisFeedClipRepository(FeedClipRepository):
    """Stores feed clips as JSON blobs indexed by recency and event."""

    def __init__(self, client: "redis.Redis") -> None:
        self._client = client

    async def save(self, clip: FeedClip) -> None:
        payload = json.dumps(self._to_record(clip))
        await self._client.set(_CLIP_KEY.format(clip_id=clip.id), payload)
        await self._client.zadd(_RECENT_KEY, {clip.id: clip.recorded_at.timestamp()})
        if clip.event_id:
            await self._client.sadd(
                _EVENT_INDEX_KEY.format(event_id=clip.event_id), clip.id
            )

    async def get_by_id(self, clip_id: str) -> FeedClip | None:
        raw = await self._client.get(_CLIP_KEY.format(clip_id=clip_id))
        if raw is None:
            return None
        return self._to_entity(json.loads(raw))

    async def get_by_event_id(self, event_id: str) -> list[FeedClip]:
        ids = await self._client.smembers(
            _EVENT_INDEX_KEY.format(event_id=event_id)
        )
        clips: list[FeedClip] = []
        for clip_id in ids:
            decoded = clip_id.decode() if isinstance(clip_id, bytes) else clip_id
            clip = await self.get_by_id(decoded)
            if clip is not None:
                clips.append(clip)
        clips.sort(key=lambda c: c.recorded_at)
        return clips

    async def list_recent(self, limit: int = 50) -> list[FeedClip]:
        ids = await self._client.zrevrange(_RECENT_KEY, 0, max(0, limit - 1))
        clips: list[FeedClip] = []
        for clip_id in ids:
            decoded = clip_id.decode() if isinstance(clip_id, bytes) else clip_id
            clip = await self.get_by_id(decoded)
            if clip is not None:
                clips.append(clip)
        return clips

    # --- mapping helpers --------------------------------------------------

    @staticmethod
    def _to_record(clip: FeedClip) -> dict:
        return {
            "id": clip.id,
            "camera_id": clip.camera_id,
            "video_url": clip.video_url,
            "emergency_description": clip.emergency_description,
            "duration_seconds": clip.duration_seconds,
            "event_id": clip.event_id,
            "recorded_at": clip.recorded_at.isoformat(),
            "segments": [
                {
                    "offset_seconds": s.offset_seconds,
                    "description": s.description,
                }
                for s in clip.segments
            ],
        }

    @staticmethod
    def _to_entity(record: dict) -> FeedClip:
        segments = [
            FeedDescriptionSegment(
                offset_seconds=s["offset_seconds"],
                description=s["description"],
            )
            for s in record.get("segments", [])
        ]
        return FeedClip(
            id=record["id"],
            camera_id=record["camera_id"],
            video_url=record["video_url"],
            emergency_description=record["emergency_description"],
            duration_seconds=record["duration_seconds"],
            event_id=record.get("event_id"),
            segments=segments,
            recorded_at=datetime.fromisoformat(record["recorded_at"]),
        )
