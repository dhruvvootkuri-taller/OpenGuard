"""Tests for the CallRecord entity and its Redis repository mapping."""

import pytest

from src.domain.entities.call_record import CallRecord, CallStatus
from src.domain.exceptions import DomainValidationError
from src.infrastructure.persistence.redis_call_record_repository import (
    RedisCallRecordRepository,
)
from tests.infrastructure.fake_redis import FakeRedis


def _call(**overrides) -> CallRecord:
    params = dict(
        to_number="+15555550111",
        transcript="Open Guard alert. Intruder detected at the loading dock.",
        event_id="evt-1",
        service_id="svc-1",
    )
    params.update(overrides)
    return CallRecord(**params)


def test_requires_transcript():
    with pytest.raises(DomainValidationError):
        _call(transcript="")


def test_lifecycle_complete():
    call = _call()
    call.mark_in_progress(provider_call_id="CA123")
    call.complete(duration_seconds=42.0)
    assert call.status is CallStatus.COMPLETED
    assert call.provider_call_id == "CA123"
    assert call.duration_seconds == 42.0
    assert call.ended_at is not None


def test_invalid_transition_rejected():
    call = _call()
    call.fail()
    with pytest.raises(DomainValidationError):
        call.mark_in_progress()


def test_fail_requires_valid_reason():
    call = _call()
    with pytest.raises(DomainValidationError):
        call.fail(CallStatus.COMPLETED)


@pytest.mark.asyncio
async def test_redis_round_trip_and_event_index():
    repo = RedisCallRecordRepository(FakeRedis())
    call = _call()
    call.mark_in_progress()
    call.complete(duration_seconds=12.5)
    await repo.save(call)

    loaded = await repo.get_by_id(call.id)
    assert loaded is not None
    assert loaded.status is CallStatus.COMPLETED
    assert loaded.duration_seconds == 12.5
    assert loaded.ended_at is not None

    for_event = await repo.get_by_event_id("evt-1")
    assert [c.id for c in for_event] == [call.id]

    recent = await repo.list_recent()
    assert recent[0].id == call.id
