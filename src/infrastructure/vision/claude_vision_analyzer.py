"""Anthropic Claude implementation of the VisionAnalyzerPort.

Wraps the Anthropic vision API behind the clean application-layer
abstraction. Given a single base64 camera frame, Claude is asked to decide —
in strict JSON — whether an emergency is occurring, how severe it is, and
where in the frame it is happening.

This client never raises on a model or parse failure: it degrades to
``EmergencyAssessment.none()`` so a live MP4 feed is never interrupted by a
transient API hiccup or a malformed response.
"""

from __future__ import annotations

import json
import re

from anthropic import AsyncAnthropic

from src.application.ports.vision_analyzer_port import VisionAnalyzerPort
from src.domain.value_objects.emergency_assessment import EmergencyAssessment

_SYSTEM_PROMPT = (
    "You are Open Guard, a security vision analyst. You are shown a single "
    "frame from a surveillance camera. Decide whether a real emergency is "
    "occurring in the frame (fire, smoke, weapon, violence/assault, intruder "
    "in a restricted area, medical collapse, accident, break-in). Be "
    "conservative: ordinary, calm activity is NOT an emergency. "
    "Respond with ONLY a JSON object, no prose, of the form:\n"
    '{"is_emergency": bool, "label": string, "score": number 0..1, '
    '"confidence": number 0..1, "summary": string, '
    '"box": {"x": number, "y": number, "width": number, "height": number}}\n'
    "Coordinates are normalised 0..1 (top-left origin). 'score' is how severe "
    "/ dangerous the situation is; 'confidence' is how sure you are. When "
    "there is no emergency, set is_emergency false, label 'clear', score 0."
)


class ClaudeVisionAnalyzer(VisionAnalyzerPort):
    def __init__(
        self, api_key: str, model: str = "claude-3-5-sonnet-20241022"
    ) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def analyze_frame(
        self, image_base64: str, media_type: str = "image/jpeg", context: str = ""
    ) -> EmergencyAssessment:
        try:
            user_text = "Analyse this camera frame for an emergency."
            if context:
                user_text += f" Context: {context}."
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
                            {"type": "text", "text": user_text},
                        ],
                    }
                ],
            )
            text = " ".join(
                block.text for block in response.content if block.type == "text"
            ).strip()
            return self._parse(text)
        except Exception:  # noqa: BLE001 - a live feed must never crash on a frame
            return EmergencyAssessment.none()

    @staticmethod
    def _parse(text: str) -> EmergencyAssessment:
        """Parse the model's JSON verdict, degrading safely on any problem."""
        if not text:
            return EmergencyAssessment.none()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return EmergencyAssessment.none()
        try:
            data = json.loads(match.group(0))
        except (json.JSONDecodeError, ValueError):
            return EmergencyAssessment.none()

        is_emergency = bool(data.get("is_emergency", False))
        if not is_emergency:
            return EmergencyAssessment.none()

        box = data.get("box") or {}
        try:
            return EmergencyAssessment(
                is_emergency=True,
                label=str(data.get("label") or "emergency"),
                score=_unit(data.get("score"), default=0.8),
                confidence=_unit(data.get("confidence"), default=0.7),
                summary=str(data.get("summary") or "").strip(),
                x=_unit(box.get("x"), default=0.0),
                y=_unit(box.get("y"), default=0.0),
                width=_unit(box.get("width"), default=1.0, minimum=1e-6),
                height=_unit(box.get("height"), default=1.0, minimum=1e-6),
            )
        except Exception:  # noqa: BLE001 - invalid numbers -> no emergency
            return EmergencyAssessment.none()


def _unit(value: object, default: float, minimum: float = 0.0) -> float:
    """Coerce a value into a clamped 0..1 float with a fallback default."""
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(minimum, min(1.0, f))
