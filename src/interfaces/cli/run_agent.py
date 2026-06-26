"""CLI entry point to run the live guard monitoring agent.

Usage:
    python -m src.interfaces.cli.run_agent --camera-id front-door --source 0
"""

from __future__ import annotations

import argparse
import asyncio

from src.interfaces.agent.guard_agent import GuardAgent


def _build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open Guard monitoring agent")
    parser.add_argument("--camera-id", required=True, help="Logical camera id")
    parser.add_argument(
        "--source", default="0", help="Video source (device index or path/URL)"
    )
    parser.add_argument("--armed-zone", action="store_true")
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    # Imports kept local so the CLI can be parsed even without heavy deps.
    import cv2  # noqa: PLC0415

    from src.infrastructure.container import Container  # noqa: PLC0415
    from src.infrastructure.vision.opencv_detector import (  # noqa: PLC0415
        OpenCVDetector,
        OpenCVDetectorConfig,
    )

    container = Container()
    source: object = int(args.source) if args.source.isdigit() else args.source
    capture = cv2.VideoCapture(source)

    detector = OpenCVDetector(
        OpenCVDetectorConfig(
            model_path="models/yolov4.weights",
            config_path="models/yolov4.cfg",
            class_names=["person", "weapon", "knife", "gun", "vehicle"],
        )
    )

    agent = GuardAgent(
        camera_id=args.camera_id,
        detector=detector,
        frame_source=capture,
        process_detection=container.process_detection_use_case(),
        is_armed_zone=args.armed_zone,
    )

    try:
        await agent.run()
    finally:
        capture.release()


def main() -> None:
    args = _build_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
