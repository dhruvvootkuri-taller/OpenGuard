"""Tests for the EmergencyService entity and its Redis repository mapping."""

import pytest

from src.domain.entities.emergency_service import (
    EmergencyService,
    EmergencyServiceCategory,
)
from src.domain.exceptions import DomainValidationError
from src.infrastructure.persistence.redis_emergency_service_repository import (
    RedisEmergencyServiceRepository,
)
from tests.infrastructure.fake_redis import FakeRedis


def _service(**overrides) -> EmergencyService:
    params = dict(
        name="City Police",
        phone_number="+15555550111",
        description="Call for break-ins, intruders and violent crime.",
        category=EmergencyServiceCategory.POLICE,
        priority=10,
    )
    params.update(overrides)
    return EmergencyService(**params)


def test_requires_description():
    with pytest.raises(DomainValidationError):
        _service(description="  ")


def test_requires_positive_priority():
    with pytest.raises(DomainValidationError):
        _service(priority=0)


def test_deactivate_and_reactivate():
    service = _service()
    service.deactivate()
    assert service.is_active is False
    service.reactivate()
    assert service.is_active is True


def test_matches_keyword_against_description():
    service = _service()
    assert service.matches("intruders")
    assert service.matches("police")  # category
    assert not service.matches("flood")


@pytest.mark.asyncio
async def test_redis_round_trip_and_active_filter():
    repo = RedisEmergencyServiceRepository(FakeRedis())
    active = _service(name="City Police", priority=10)
    inactive = _service(
        name="Old Hotline", phone_number="+15555550999", priority=99
    )
    inactive.deactivate()

    await repo.save(active)
    await repo.save(inactive)

    loaded = await repo.get_by_id(active.id)
    assert loaded is not None
    assert loaded.name == "City Police"
    assert loaded.category is EmergencyServiceCategory.POLICE

    all_services = await repo.list_all()
    assert [s.priority for s in all_services] == [10, 99]  # sorted by priority

    active_only = await repo.list_active()
    assert [s.id for s in active_only] == [active.id]


@pytest.mark.asyncio
async def test_redis_delete():
    repo = RedisEmergencyServiceRepository(FakeRedis())
    service = _service()
    await repo.save(service)
    await repo.delete(service.id)
    assert await repo.get_by_id(service.id) is None
    assert await repo.list_all() == []
