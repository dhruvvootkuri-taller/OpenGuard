"""Camera-configuration endpoint + 'no demo cameras' guard tests.

The dashboard's video wall is now config-driven via GET /api/cameras (sourced
from the CAMERAS env var). These tests lock in two invariants:

1. With no cameras configured the endpoint returns an empty list (no baked-in
   demo cameras like CAM-01/CAM-02/CAM-03/CAM-04).
2. Configured cameras round-trip through Settings -> controller -> HTTP.
3. The frontend App no longer hardcodes a demo FEEDS array — the camera list is
   fetched from the backend.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from src.infrastructure.config.settings import _parse_cameras
from src.interfaces.http.app import create_app
from src.interfaces.http.auth import Authenticator
from src.interfaces.http.controllers.security_event_controller import (
    SecurityEventController,
)
from src.interfaces.http.controllers.voice_agent_controller import (
    VoiceAgentController,
)
from src.interfaces.http.schemas import CameraResponse


def _build_controller(cameras: list[CameraResponse]) -> SecurityEventController:
    # Use cases are never invoked by the cameras route, so None stand-ins are
    # fine here — we only exercise GET /api/cameras (a public read endpoint).
    return SecurityEventController(
        process_detection=None,  # type: ignore[arg-type]
        acknowledge_event=None,  # type: ignore[arg-type]
        list_recent_events=None,  # type: ignore[arg-type]
        analyze_feed_frame=None,  # type: ignore[arg-type]
        resolve_event=None,  # type: ignore[arg-type]
        dismiss_event=None,  # type: ignore[arg-type]
        clear_resolved_events=None,  # type: ignore[arg-type]
        authenticator=Authenticator(api_keys=()),
        cameras=cameras,
    )


def _client(cameras: list[CameraResponse]) -> TestClient:
    controller = _build_controller(cameras)
    voice = VoiceAgentController(
        place_emergency_call=None,  # type: ignore[arg-type]
        authenticator=Authenticator(api_keys=()),
    )
    app = create_app(
        security_event_controller=controller,
        voice_agent_controller=voice,
    )
    return TestClient(app)


def test_no_cameras_configured_returns_empty_list():
    client = _client([])
    response = client.get("/api/cameras")
    assert response.status_code == 200
    assert response.json() == []


def test_configured_cameras_round_trip():
    cameras = [
        CameraResponse(id="lobby-1", zone="Lobby", armed=True),
        CameraResponse(id="dock-2", zone="Dock", armed=False),
    ]
    client = _client(cameras)
    response = client.get("/api/cameras")
    assert response.status_code == 200
    assert response.json() == [
        {"id": "lobby-1", "zone": "Lobby", "armed": True},
        {"id": "dock-2", "zone": "Dock", "armed": False},
    ]


def test_parse_cameras_empty_yields_no_cameras():
    assert _parse_cameras("") == ()
    assert _parse_cameras("   ;  ;") == ()


def test_parse_cameras_parses_id_zone_armed():
    cams = _parse_cameras("CAM-A|Lobby|true; CAM-B|Dock|0 ; CAM-C")
    assert [(c.id, c.zone, c.armed) for c in cams] == [
        ("CAM-A", "Lobby", True),
        ("CAM-B", "Dock", False),
        # Zone defaults to id when omitted.
        ("CAM-C", "CAM-C", False),
    ]


def test_frontend_app_has_no_hardcoded_demo_feeds():
    """The hardcoded FEEDS array (CAM-01..CAM-04) must be gone from App.tsx."""
    app_tsx = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    # The baked-in demo array declaration must not exist.
    assert "const FEEDS" not in app_tsx
    # None of the demo camera ids / zone literals may remain.
    for literal in (
        "CAM-01",
        "CAM-02",
        "CAM-03",
        "CAM-04",
        "Main Entrance",
        "Parking Structure",
        "Secure Perimeter",
        "Loading Dock",
    ):
        assert literal not in app_tsx, f"demo literal still present: {literal}"

    # The list must be sourced from the backend.
    assert "fetchCameras" in app_tsx


def test_no_demo_camera_literals_in_frontend_src():
    """No demo camera id/zone string literals anywhere under frontend/src."""
    demo_literals = [
        "Main Entrance",
        "Parking Structure",
        "Secure Perimeter",
        "Loading Dock",
    ]
    cam_id_pattern = re.compile(r"CAM-0[1-4]")
    for path in Path("frontend/src").rglob("*.ts*"):
        text = path.read_text(encoding="utf-8")
        for literal in demo_literals:
            assert literal not in text, f"{path}: {literal}"
        assert not cam_id_pattern.search(text), f"{path}: demo CAM id literal"
