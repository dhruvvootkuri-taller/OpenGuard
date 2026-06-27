"""Environment configuration.

Per the infrastructure CLAUDE.md, environment variables live here only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(key: str, default: str | None = None) -> str:
    value = os.getenv(key, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


@dataclass(frozen=True)
class Settings:
    # Redis
    redis_url: str

    # Celery (broker + result backend, both Redis-backed)
    celery_broker_url: str
    celery_result_backend: str

    # Anthropic / Claude Haiku
    anthropic_api_key: str
    anthropic_model: str
    # Anthropic / Claude vision (MP4 feed-frame analysis)
    anthropic_vision_model: str

    # ElevenLabs
    elevenlabs_api_key: str
    elevenlabs_voice_id: str
    # Conversational AI (interactive voice agent over Twilio)
    elevenlabs_agent_id: str
    elevenlabs_phone_number_id: str

    # Twilio
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str
    on_call_number: str

    # Event lifecycle
    # An active event with no new frames/detections for this many seconds is
    # auto-resolved so the dashboard reflects current activity, not a backlog.
    event_inactivity_ttl_seconds: int

    # App
    app_host: str
    app_port: int

    @classmethod
    def from_env(cls) -> "Settings":
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        return cls(
            redis_url=redis_url,
            celery_broker_url=os.getenv("CELERY_BROKER_URL", redis_url),
            celery_result_backend=os.getenv(
                "CELERY_RESULT_BACKEND", "redis://localhost:6379/1"
            ),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307"),
            # claude-3-5-sonnet-20241022 was retired 2025-10-28; default to a
            # current vision model so feed frames don't 404.
            anthropic_vision_model=os.getenv(
                "ANTHROPIC_VISION_MODEL", "claude-opus-4-8"
            ),
            elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY", ""),
            elevenlabs_voice_id=os.getenv("ELEVENLABS_VOICE_ID", "Rachel"),
            elevenlabs_agent_id=os.getenv("ELEVENLABS_AGENT_ID", ""),
            elevenlabs_phone_number_id=os.getenv(
                "ELEVENLABS_PHONE_NUMBER_ID", ""
            ),
            twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
            twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
            twilio_from_number=os.getenv("TWILIO_FROM_NUMBER", ""),
            on_call_number=os.getenv("ON_CALL_NUMBER", ""),
            event_inactivity_ttl_seconds=int(
                os.getenv("EVENT_INACTIVITY_TTL_SECONDS", "300")
            ),
            app_host=os.getenv("APP_HOST", "0.0.0.0"),
            app_port=int(os.getenv("APP_PORT", "8000")),
        )
