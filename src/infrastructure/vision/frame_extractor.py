"""Streaming MP4 frame extractor (OpenCV).

Decodes an MP4 and yields frames *as they are read*, so a consumer can start
analysing the feed immediately instead of waiting for the whole clip to be
processed. Frames are base64-encoded JPEGs ready to hand to a
``VisionAnalyzerPort``.

This is infrastructure: it knows about OpenCV. The application layer only ever
sees the base64 strings it produces.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Iterator

import cv2


@dataclass(frozen=True)
class ExtractedFrame:
    """A single decoded frame ready for analysis."""

    index: int
    timestamp_seconds: float
    image_base64: str
    media_type: str = "image/jpeg"


class FrameExtractor:
    """Yields base64 JPEG frames from an MP4, sampled at a target FPS.

    ``sample_fps`` controls how many frames per second of source video are
    surfaced for analysis (we rarely need every frame). Frames are yielded
    lazily so the consumer processes them in real time.
    """

    def __init__(self, sample_fps: float = 1.0, jpeg_quality: int = 80) -> None:
        if sample_fps <= 0:
            raise ValueError("sample_fps must be positive")
        self._sample_fps = sample_fps
        self._jpeg_quality = jpeg_quality

    def iter_frames(self, video_path: str) -> Iterator[ExtractedFrame]:
        capture = cv2.VideoCapture(video_path)
        if not capture.isOpened():
            raise RuntimeError(f"Could not open video: {video_path}")
        try:
            source_fps = capture.get(cv2.CAP_PROP_FPS) or self._sample_fps
            step = max(1, int(round(source_fps / self._sample_fps)))
            encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), self._jpeg_quality]

            frame_index = 0
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                if frame_index % step == 0:
                    success, buffer = cv2.imencode(".jpg", frame, encode_params)
                    if success:
                        yield ExtractedFrame(
                            index=frame_index,
                            timestamp_seconds=frame_index / source_fps,
                            image_base64=base64.b64encode(buffer).decode("ascii"),
                        )
                frame_index += 1
        finally:
            capture.release()
