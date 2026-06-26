"""Tests for the FeedClip entity and its Redis repository mapping."""

import pytest

from src.domain.entities.feed_clip import FeedClip
from src.domain.exceptions import DomainValidationError
from src.domain.value_objects.feed_segment import FeedDescriptionSegment
from src.infrastructure.persistence.redis_feed_clip_repository import (
    RedisFeedClipRepository,
)
from tests.infrastructure.fake_redis import FakeRedis


def _clip(**overrides) -> FeedClip:
    params = dict(
        camera_id="cam-1",
        video_url="s3://clips/cam-1/abc.mp4",
        emergency_description="Person forcing the back door.",
        duration_seconds=30.0,
        event_id="evt-1",
        segments=[
            FeedDescriptionSegment(offset_seconds=10.0, description="Door is forced open."),
            FeedDescriptionSegment(offset_seconds=0.0, description="Person approaches door."),
        ],
    )
    params.update(overrides)
    return FeedClip(**params)


def test_requires_video_url():
    with pytest.raises(DomainValidationError):
        _clip(video_url="")


def test_segments_are_sorted_on_construction():
    clip = _clip()
    assert [s.offset_seconds for s in clip.timeline()] == [0.0, 10.0]


def test_description_at_picks_active_segment():
    clip = _clip()
    assert clip.description_at(2.0) == "Person approaches door."
    assert clip.description_at(15.0) == "Door is forced open."


def test_description_at_falls_back_to_emergency_description():
    clip = _clip(segments=[])
    assert clip.description_at(5.0) == "Person forcing the back door."


def test_add_segment_beyond_duration_rejected():
    clip = _clip()
    with pytest.raises(DomainValidationError):
        clip.add_segment(
            FeedDescriptionSegment(offset_seconds=999.0, description="late")
        )


@pytest.mark.asyncio
async def test_redis_round_trip_and_event_index():
    repo = RedisFeedClipRepository(FakeRedis())
    clip = _clip()
    await repo.save(clip)

    loaded = await repo.get_by_id(clip.id)
    assert loaded is not None
    assert loaded.video_url == clip.video_url
    assert [s.offset_seconds for s in loaded.timeline()] == [0.0, 10.0]

    for_event = await repo.get_by_event_id("evt-1")
    assert [c.id for c in for_event] == [clip.id]

    recent = await repo.list_recent()
    assert recent[0].id == clip.id
