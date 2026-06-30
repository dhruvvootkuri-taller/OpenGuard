"""API authentication tests for the HTTP interface.

Covers authorized + unauthorized access for every PROTECTED route, plus the
fail-closed posture when no keys are configured. Use cases are replaced with
lightweight fakes so the tests need no Redis / ElevenLabs / Twilio creds.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.application.dtos.detection_dtos import (
    AnalyzeFrameOutputDTO,
    ClearResolvedOutputDTO,
    SecurityEventDTO,
)
from src.application.dtos.voice_agent_dtos import PlaceEmergencyCallOutputDTO
from src.interfaces.http.app import create_app
from src.interfaces.http.auth import Authenticator
from src.interfaces.http.controllers.security_event_controller import (
    SecurityEventController,
)
from src.interfaces.http.controllers.voice_agent_controller import (
    VoiceAgentController,
)

API_KEY = "test-secret-key"


# --- fakes ----------------------------------------------------------------


def _fake_event() -> SecurityEventDTO:
    return SecurityEventDTO(
        id="evt-1",
        camera_id="CAM-01",
        status="active",
        threat_severity="high",
        threat_confidence=0.9,
        description="Test event",
        detected_at="2026-01-01T00:00:00Z",
        escalated=False,
        detections=[],
    )


class _Async:
    """Wrap a sync return value behind an awaitable ``execute``."""

    def __init__(self, value):
        self._value = value

    async def execute(self, *args, **kwargs):
        return self._value


class _AsyncList(_Async):
    async def execute(self, *args, **kwargs):
        return list(self._value)


def _build_client(api_keys) -> TestClient:
    authenticator = Authenticator(api_keys)

    event = _fake_event()
    analyze_result = AnalyzeFrameOutputDTO(
        camera_id="CAM-01",
        is_emergency=False,
        label="all clear",
        summary="No emergency.",
        event=None,
    )
    call_result = PlaceEmergencyCallOutputDTO(
        to_number="+15555550199",
        provider_call_id="CA123",
        conversation_id="conv-1",
    )

    security_controller = SecurityEventController(
        process_detection=_Async(event),
        acknowledge_event=_Async(event),
        list_recent_events=_AsyncList([event]),
        analyze_feed_frame=_Async(analyze_result),
        resolve_event=_Async(event),
        dismiss_event=_Async(event),
        clear_resolved_events=_Async(ClearResolvedOutputDTO(cleared=0)),
        authenticator=authenticator,
    )
    voice_controller = VoiceAgentController(
        place_emergency_call=_Async(call_result),
        authenticator=authenticator,
    )
    app = create_app(
        security_event_controller=security_controller,
        voice_agent_controller=voice_controller,
    )
    return TestClient(app)


# Each entry: (method, path, json body)
PROTECTED_ROUTES = [
    (
        "post",
        "/api/events",
        {
            "camera_id": "CAM-01",
            "detections": [
                {
                    "label": "person",
                    "confidence": 0.9,
                    "x": 0.1,
                    "y": 0.1,
                    "width": 0.2,
                    "height": 0.2,
                }
            ],
        },
    ),
    ("post", "/api/events/evt-1/acknowledge", {"operator_id": "op-1"}),
    ("post", "/api/events/evt-1/resolve", None),
    ("post", "/api/events/evt-1/dismiss", None),
    ("post", "/api/events/clear-resolved", {}),
    (
        "post",
        "/api/feeds/CAM-01/frame",
        {"image_base64": "AAAA", "media_type": "image/jpeg"},
    ),
    (
        "post",
        "/api/voice/calls",
        {"description": "Fire on the 2nd floor."},
    ),
]


@pytest.fixture
def client() -> TestClient:
    return _build_client([API_KEY])


@pytest.mark.parametrize("method,path,body", PROTECTED_ROUTES)
def test_protected_route_rejects_missing_credentials(method, path, body, client):
    response = getattr(client, method)(path, json=body)
    assert response.status_code == 401


@pytest.mark.parametrize("method,path,body", PROTECTED_ROUTES)
def test_protected_route_rejects_invalid_token(method, path, body, client):
    response = getattr(client, method)(
        path, json=body, headers={"Authorization": "Bearer wrong-key"}
    )
    assert response.status_code == 401


@pytest.mark.parametrize("method,path,body", PROTECTED_ROUTES)
def test_protected_route_allows_valid_bearer_token(method, path, body, client):
    response = getattr(client, method)(
        path, json=body, headers={"Authorization": f"Bearer {API_KEY}"}
    )
    assert response.status_code != 401


@pytest.mark.parametrize("method,path,body", PROTECTED_ROUTES)
def test_protected_route_allows_valid_x_api_key(method, path, body, client):
    response = getattr(client, method)(
        path, json=body, headers={"X-API-Key": API_KEY}
    )
    assert response.status_code != 401


def test_voice_call_requires_auth(client):
    """Placing a REAL outbound phone call must require auth (401 without)."""
    unauth = client.post(
        "/api/voice/calls", json={"description": "Intruder detected."}
    )
    assert unauth.status_code == 401

    ok = client.post(
        "/api/voice/calls",
        json={"description": "Intruder detected."},
        headers={"Authorization": f"Bearer {API_KEY}"},
    )
    assert ok.status_code == 201


def test_health_is_public(client):
    assert client.get("/health").status_code == 200


def test_fails_closed_when_no_keys_configured():
    """No configured keys => every protected request is denied (fail closed)."""
    closed = _build_client([])
    # Even with a plausible-looking token, deny because nothing is configured.
    response = closed.post(
        "/api/voice/calls",
        json={"description": "Fire."},
        headers={"Authorization": "Bearer anything"},
    )
    assert response.status_code == 401
    # Health stays public even when auth is unconfigured.
    assert closed.get("/health").status_code == 200
