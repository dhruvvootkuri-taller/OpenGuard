"""ElevenLabs implementation of VoiceSynthesisPort.

Wraps the ElevenLabs text-to-speech API behind the application port.
"""

from __future__ import annotations

import base64

import httpx

from src.application.ports.notification_port import VoiceMessage, VoiceSynthesisPort

_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


class ElevenLabsVoiceClient(VoiceSynthesisPort):
    def __init__(self, api_key: str, voice_id: str) -> None:
        self._api_key = api_key
        self._voice_id = voice_id

    async def synthesize(self, text: str) -> VoiceMessage:
        url = _TTS_URL.format(voice_id=self._voice_id)
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        body = {
            "text": text,
            "model_id": "eleven_turbo_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=body)
                response.raise_for_status()
                audio_b64 = base64.b64encode(response.content).decode("ascii")
                return VoiceMessage(
                    text=text, audio_url=f"data:audio/mpeg;base64,{audio_b64}"
                )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"ElevenLabs synthesis failed: {exc}") from exc
