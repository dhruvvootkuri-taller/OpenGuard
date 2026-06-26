"""Redis pub/sub implementation of EventPublisherPort."""

from __future__ import annotations

import dataclasses
import json

import redis.asyncio as redis

from src.application.dtos.detection_dtos import SecurityEventDTO
from src.application.ports.event_publisher_port import EventPublisherPort

_CHANNEL = "open_guard:events"


class RedisEventPublisher(EventPublisherPort):
    def __init__(self, client: "redis.Redis") -> None:
        self._client = client

    async def publish_event(self, event: SecurityEventDTO) -> None:
        payload = json.dumps(dataclasses.asdict(event))
        await self._client.publish(_CHANNEL, payload)
