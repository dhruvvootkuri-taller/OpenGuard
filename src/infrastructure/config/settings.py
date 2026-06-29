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
class CameraConfig:
    """A single configured camera feed.

    These are operator-configured real cameras — there are NO baked-in demo
    cameras. An unset/empty ``CAMERAS`` env yields an empty list and the
    dashboard renders its 'No cameras configured' empty state.
    """

    id: str
    zone: str
    armed: bool


def _parse_cameras(raw: str) -> tuple[CameraConfig, ...]:
    """Parse the ``CAMERAS`` env value into camera configs.

    Format: semicolon-separated entries, each ``id|zone|armed`` where ``armed``
    is an optional truthy flag (``true``/``1``/``yes``/``armed``). Whitespace is
    trimmed; blank/malformed entries (missing id) are skipped. An empty string
    yields an empty tuple — i.e. no cameras configured.
    """
    cameras: list[CameraConfig] = []
    for entry in raw.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        parts = [p.strip() for p in entry.split("|")]
        cam_id = parts[0] if parts else ""
        if not cam_id:
            continue
        zone = parts[1] if len(parts) > 1 and parts[1] else cam_id
        armed_token = parts[2].lower() if len(parts) > 2 else ""
        armed = armed_token in {"true", "1", "yes", "armed", "on"}
        cameras.append(CameraConfig(id=cam_id, zone=zone, armed=armed))
    return tuple(cameras)


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

    # Detection gating (cut false alarms on the stochastic MP4 vision feed)
    detection_min_confidence: float
    detection_min_threat_score: float
    detection_confirmation_window: int
    detection_confirmation_required: int

    # Emergency de-duplication: collapse repeated emergency frames from the
    # same camera into a single incident for this many seconds (cooldown).
    emergency_dedup_window_seconds: int

    # Camera feeds (operator-configured; empty = no cameras configured).
    cameras: tuple[CameraConfig, ...]

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
            # Detection gating: a flagged frame must clear BOTH thresholds to
            # count, and the same emergency must recur across the confirmation
            # window before it becomes an event/escalation.
            detection_min_confidence=float(
                os.getenv("DETECTION_MIN_CONFIDENCE", "0.6")
            ),
            detection_min_threat_score=float(
                os.getenv("DETECTION_MIN_THREAT_SCORE", "0.4")
            ),
            detection_confirmation_window=int(
                os.getenv("DETECTION_CONFIRMATION_WINDOW", "3")
            ),
            detection_confirmation_required=int(
                os.getenv("DETECTION_CONFIRMATION_REQUIRED", "2")
            ),
            emergency_dedup_window_seconds=int(
                os.getenv("EMERGENCY_DEDUP_WINDOW_SECONDS", "60")
            ),
            # No baked-in demo cameras: default to an empty list so the
            # dashboard shows its empty state until real cameras are configured.
            cameras=_parse_cameras(os.getenv("CAMERAS", "")),
            app_host=os.getenv("APP_HOST", "0.0.0.0"),
            app_port=int(os.getenv("APP_PORT", "8000")),
        )