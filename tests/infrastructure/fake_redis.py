"""A tiny in-memory async fake of the redis.asyncio client.

Only implements the subset of commands used by the persistence layer
(set/get/delete, sadd/srem/smembers, zadd/zrevrange) so repository mapping
can be exercised without a live Redis server.
"""

from __future__ import annotations


class FakeRedis:
    def __init__(self) -> None:
        self._strings: dict[str, str] = {}
        self._sets: dict[str, set[str]] = {}
        self._zsets: dict[str, dict[str, float]] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        # TTL (``ex``) is accepted for API parity with redis but not enforced
        # in this in-memory fake; tests drive expiry explicitly via delete.
        self._strings[key] = value

    async def get(self, key: str):
        return self._strings.get(key)

    async def delete(self, key: str) -> None:
        self._strings.pop(key, None)

    async def sadd(self, key: str, *members: str) -> None:
        self._sets.setdefault(key, set()).update(members)

    async def srem(self, key: str, *members: str) -> None:
        self._sets.get(key, set()).difference_update(members)

    async def smembers(self, key: str) -> set[str]:
        return set(self._sets.get(key, set()))

    async def zadd(self, key: str, mapping: dict[str, float]) -> None:
        self._zsets.setdefault(key, {}).update(mapping)

    async def zrem(self, key: str, *members: str) -> None:
        zset = self._zsets.get(key, {})
        for member in members:
            zset.pop(member, None)

    async def zrevrange(self, key: str, start: int, end: int) -> list[str]:
        items = sorted(
            self._zsets.get(key, {}).items(), key=lambda kv: kv[1], reverse=True
        )
        ids = [member for member, _ in items]
        if end == -1:
            return ids[start:]
        return ids[start : end + 1]
