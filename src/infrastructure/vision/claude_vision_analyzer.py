"""Claude vision implementation of the VisionAnalyzerPort.

Sends a single camera frame to Anthropic Claude vision and asks for a strict
JSON emergency assessment. Failures (bad API key, retired model, malformed
response) are logged and re-raised as ``VisionAnalyzerError`` so they surface
to the caller — a provider error must never be silently treated as "all clear".
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from anthropic import AsyncAnthropic

from src.application.ports.vision_analyzer_port import (
    VisionAnalyzerError,
    VisionAnalyzerPort,
)
from src.domain.value_objects.detection_box import DetectionBox
from src.domain.value_objects.emergency_assessment import EmergencyAssessment

logger = logging.getLogger(__name__)

# A current, non-retired Claude vision model. The previous default
# (claude-3-5-sonnet-20241022) was retired 2025-10-28 and every frame 404'd.
DEFAULT_VISION_MODEL = "claude-opus-4-8"

_SYSTEM_PROMPT = (
    "You are Open Guard, a security vision analyst. You are shown a single "
    "frame from a camera feed. Decide whether the frame shows an EMERGENCY "
    "(violence, weapons, intrusion, fire, smoke, a person collapsed/injured, "
    "an active break-in, or similar). Mundane activity, empty scenes, normal "
    "pedestrians or vehicles are NOT emergencies.\n\n"
    "Respond with ONLY a single JSON object, no markdown, with this shape:\n"
    "{\n"
    '  "is_emergency": boolean,\n'
    '  "threat_score": number,   // 0.0 (calm) .. 1.0 (critical)\n'
    '  "confidence": number,     // 0.0 .. 1.0\n'
    '  "label": string,          // short tag, e.g. "weapon", "all clear"\n'
    '  "summary": string,        // one concise sentence\n'
    '  "box": null | {           // region of interest, normalized 0..1\n'
    '    "x": number, "y": number, "width": number, "height": number\n'
    "  }\n"
    "}"
)


class ClaudeVisionAnalyzer(VisionAnalyzerPort):
    def __init__(self, api_key: str, model: str = DEFAULT_VISION_MODEL) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def assess_frame(
        self,
        image_base64: str,
        media_type: str,
        is_armed_zone: bool,
        zone: str,
    ) -> EmergencyAssessment:
        context = (
            f"Camera zone: {zone or 'unknown'}. "
            f"Armed/restricted zone: {'yes' if is_armed_zone else 'no'}."
        )
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=300,
                system=_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_base64,
                                },
                            },
                            {"type": "text", "text": context},
                        ],
                    }
                ],
            )
        except Exception as exc:  # noqa: BLE001 - surface, never swallow
            logger.error("Claude vision request failed (model=%s): %s", self._model, exc)
            raise VisionAnalyzerError(
                f"Claude vision request failed (model={self._model}): {exc}"
            ) from exc

        text = " ".join(
            block.text for block in response.content if block.type == "text"
        ).strip()
        try:
            return self._parse(text)
        except (ValueError, KeyError, TypeError) as exc:
            logger.error("Failed to parse Claude vision response %r: %s", text, exc)
            raise VisionAnalyzerError(
                f"Could not parse Claude vision response: {exc}"
            ) from exc

    @staticmethod
    def _parse(text: str) -> EmergencyAssessment:
        payload = _extract_json(text)
        box_data = payload.get("box")
        box: Optional[DetectionBox] = None
        is_emergency = bool(payload["is_emergency"])
        threat_score = _clamp(float(payload.get("threat_score", 0.0)))
        confidence = _clamp(float(payload.get("confidence", 0.0)))
        label = str(payload.get("label") or ("emergency" if is_emergency else "all clear"))
        summary = str(payload.get("summary") or "")

        if is_emergency and isinstance(box_data, dict):
            box = DetectionBox(
                label=label,
                confidence=confidence,
                x=_clamp(float(box_data.get("x", 0.0))),
                y=_clamp(float(box_data.get("y", 0.0))),
                width=_clamp_size(float(box_data.get("width", 1.0))),
                height=_clamp_size(float(box_data.get("height", 1.0))),
            )

        return EmergencyAssessment(
            is_emergency=is_emergency,
            threat_score=threat_score,
            confidence=confidence,
            label=label,
            summary=summary or ("Emergency detected." if is_emergency else "No emergency detected."),
            box=box,
        )


def _extract_json(text: str) -> dict:
    """Tolerate JSON wrapped in markdown fences or prose."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in response")
    return json.loads(cleaned[start : end + 1])


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _clamp_size(value: float) -> float:
    # width/height must be in (0, 1]
    return max(0.01, min(1.0, value))
