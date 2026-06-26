"""Agent entry point: continuous camera monitoring loop.

Translates camera frames into ProcessDetectionUseCase invocations.
The detector and use case are injected — no infrastructure imports here.
"""

from __future__ import annotations

import asyncio
from typing import Protocol

from src.application.dtos.detection_dtos import (
    DetectionBoxDTO,
    ProcessDetectionInputDTO,
)
from src.application.use_cases.process_detection_use_case import (
    ProcessDetectionUseCase,
)


class FrameDetector(Protocol):
    """Structural type for any detector returning DetectionBoxDTOs."""

    def detect(self, frame: object) -> list[DetectionBoxDTO]:
        ...


class FrameSource(Protocol):
    """Structural type for anything yielding frames (camera, file, RTSP)."""

    def read(self) -> tuple[bool, object]:
        ...


class GuardAgent:
    def __init__(
        self,
        camera_id: str,
        detector: FrameDetector,
        frame_source: FrameSource,
        process_detection: ProcessDetectionUseCase,
        is_armed_zone: bool = False,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self._camera_id = camera_id
        self._detector = detector
        self._frame_source = frame_source
        self._process_detection = process_detection
        self._is_armed_zone = is_armed_zone
        self._poll_interval = poll_interval_seconds
        self._running = False

    async def run(self) -> None:
        self._running = True
        while self._running:
            ok, frame = self._frame_source.read()
            if not ok:
                await asyncio.sleep(self._poll_interval)
                continue

            detections = self._detector.detect(frame)
            if detections:
                await self._process_detection.execute(
                    ProcessDetectionInputDTO(
                        camera_id=self._camera_id,
                        detections=detections,
                        is_armed_zone=self._is_armed_zone,
                    )
                )
            await asyncio.sleep(self._poll_interval)

    def stop(self) -> None:
        self._running = False
