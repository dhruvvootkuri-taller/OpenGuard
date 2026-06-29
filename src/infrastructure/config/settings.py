"""Environment configuration.

Per the infrastructure CLAUDE.md, environment variables live here only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _csv(value: str) -> tuple[str, ...]:
    """Parse a comma-separated env value into an ordered tuple, trimming
    whitespace and dropping empties while preserving order."""
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _parse_api_keys(raw: str) -> frozenset[str]:
    """Parse a comma-separated list of API keys into a set.

    Blank/whitespace-only entries are ignored. An empty/unset value yields an
    empty set, which makes the auth layer FAIL CLOSED (deny everything).
    """
    return frozenset(k.strip() for k in raw.split(",") if k.strip())


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

    # Escalation reliability: ordered on-call contact list + retry/fallback.
    # When an escalation call is not answered we retry the same contact up to
    # ``escalation_max_retries_per_contact`` times, then fall back to the next
    # contact. The event is marked UNREACHABLE only after every contact is
    # exhausted. Polling captures the provider call outcome.
    escalation_on_call_numbers: tuple[str, ...]
    escalation_max_retries_per_contact: int
    escalation_answer_timeout_seconds: int
    escalation_poll_interval_seconds: float

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

    # Vision cost controls / rate limiting (protect Anthropic spend + DoS).
    # Per-camera minimum interval between ANALYSED frames (seconds); excess
    # frames are skipped server-side. Global caps on concurrent in-flight calls
    # and calls-per-minute. Daily call budget acts as a kill switch that halts
    # analysis when exceeded. Any limit set to 0 disables that specific limit.
    vision_per_camera_min_interval_seconds: float
    vision_max_concurrent_calls: int
    vision_max_calls_per_minute: int
    vision_daily_budget_calls: int

    # API authentication
    # Set of accepted API keys / bearer tokens. Requests to protected
    # endpoints must present one of these via `Authorization: Bearer <key>`
    # or `X-API-Key: <key>`. An EMPTY set means auth is unconfigured, which
    # makes the auth layer FAIL CLOSED — every protected request is denied.
    api_keys: frozenset[str]

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
            # Ordered on-call list. Defaults to the single ON_CALL_NUMBER so
            # existing single-contact setups keep working unchanged.
            escalation_on_call_numbers=(
                _csv(os.getenv("ESCALATION_ON_CALL_NUMBERS", ""))
                or _csv(os.getenv("ON_CALL_NUMBER", ""))
            ),
            escalation_max_retries_per_contact=int(
                os.getenv("ESCALATION_MAX_RETRIES_PER_CONTACT", "1")
            ),
            escalation_answer_timeout_seconds=int(
                os.getenv("ESCALATION_ANSWER_TIMEOUT_SECONDS", "30")
            ),
            escalation_poll_interval_seconds=float(
                os.getenv("ESCALATION_POLL_INTERVAL_SECONDS", "2")
            ),
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
            # Vision cost controls. Sane defaults: analyse at most one frame per
            # camera every 2s, at most 4 concurrent and 60 calls/minute globally,
            # and stop after 5000 calls/day (kill switch). Set any to 0 to
            # disable that limit.
            vision_per_camera_min_interval_seconds=float(
                os.getenv("VISION_PER_CAMERA_MIN_INTERVAL_SECONDS", "2.0")
            ),
            vision_max_concurrent_calls=int(
                os.getenv("VISION_MAX_CONCURRENT_CALLS", "4")
            ),
            vision_max_calls_per_minute=int(
                os.getenv("VISION_MAX_CALLS_PER_MINUTE", "60")
            ),
            vision_daily_budget_calls=int(
                os.getenv("VISION_DAILY_BUDGET_CALLS", "5000")
            ),
            # Never hardcode keys. Unset -> empty set -> auth fails closed.
            api_keys=_parse_api_keys(os.getenv("OPEN_GUARD_API_KEYS", "")),
            app_host=os.getenv("APP_HOST", "0.0.0.0"),
            app_port=int(os.getenv("APP_PORT", "8000")),
        )