"""Redis implementation of the EmergencyServiceRepository domain interface.

Stores each service as a JSON blob, with a set index for fast enumeration.
Contains NO business logic — only persistence concerns.
"""

from __future__ import annotations

import json
from datetime import datetime

import redis.asyncio as redis

from src.domain.entities.emergency_service import (
    EmergencyService,
    EmergencyServiceCategory,
)
from src.domain.repositories.emergency_service_repository import (
    EmergencyServiceRepository,
)

_SERVICE_KEY = "open_guard:service:{service_id}"
_INDEX_KEY = "open_guard:services:index"


class RedisEmergencyServiceRepository(EmergencyServiceRepository):
    """Stores emergency services as JSON blobs indexed by a set."""

    def __init__(self, client: "redis.Redis") -> None:
        self._client = client

    async def save(self, service: EmergencyService) -> None:
        payload = json.dumps(self._to_record(service))
        await self._client.set(_SERVICE_KEY.format(service_id=service.id), payload)
        await self._client.sadd(_INDEX_KEY, service.id)

    async def get_by_id(self, service_id: str) -> EmergencyService | None:
        raw = await self._client.get(_SERVICE_KEY.format(service_id=service_id))
        if raw is None:
            return None
        return self._to_entity(json.loads(raw))

    async def list_all(self) -> list[EmergencyService]:
        ids = await self._client.smembers(_INDEX_KEY)
        services: list[EmergencyService] = []
        for service_id in ids:
            decoded = (
                service_id.decode() if isinstance(service_id, bytes) else service_id
            )
            service = await self.get_by_id(decoded)
            if service is not None:
                services.append(service)
        services.sort(key=lambda s: (s.priority, s.name.lower()))
        return services

    async def list_active(self) -> list[EmergencyService]:
        return [s for s in await self.list_all() if s.is_active]

    async def delete(self, service_id: str) -> None:
        await self._client.delete(_SERVICE_KEY.format(service_id=service_id))
        await self._client.srem(_INDEX_KEY, service_id)

    # --- mapping helpers --------------------------------------------------

    @staticmethod
    def _to_record(service: EmergencyService) -> dict:
        return {
            "id": service.id,
            "name": service.name,
            "phone_number": service.phone_number,
            "description": service.description,
            "category": service.category.value,
            "priority": service.priority,
            "is_active": service.is_active,
            "created_at": service.created_at.isoformat(),
        }

    @staticmethod
    def _to_entity(record: dict) -> EmergencyService:
        return EmergencyService(
            id=record["id"],
            name=record["name"],
            phone_number=record["phone_number"],
            description=record["description"],
            category=EmergencyServiceCategory(record["category"]),
            priority=record["priority"],
            is_active=record["is_active"],
            created_at=datetime.fromisoformat(record["created_at"]),
        )
