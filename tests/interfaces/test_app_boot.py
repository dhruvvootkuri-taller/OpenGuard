"""App-boot regression tests.

These lock in the Python 3.9 fix: the previous ``schemas.py`` used a quoted
union ``"SecurityEventResponse | None"`` resolved via ``model_rebuild()``,
which raises ``TypeError`` on Python 3.9. We now use ``Optional[...]``.

If a future change reintroduces a forward-ref/PEP 604 union that does not
resolve on 3.9, importing the schemas or building the app fails here in CI —
before anyone tries (and fails) to ``uvicorn src.main:app`` on 3.9.
"""

from fastapi.testclient import TestClient

from src.main import build_app


def test_schemas_resolve_on_python_39():
    """AnalyzeFrameResponse must fully resolve (no model_rebuild TypeError)."""
    from src.interfaces.http.schemas import AnalyzeFrameResponse

    # Building a model with a nested optional event proves the forward ref
    # resolved. On 3.9 a quoted PEP-604 union would have raised at class /
    # rebuild time and we'd never get here.
    payload = AnalyzeFrameResponse(
        camera_id="CAM-01",
        is_emergency=False,
        label="all clear",
        summary="No emergency detected.",
        event=None,
    )
    assert payload.event is None
    assert payload.is_emergency is False


def test_app_boots_and_health_is_200():
    """uvicorn src.main:app must boot and expose a healthy /health."""
    app = build_app()
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_feeds_frame_route_is_registered():
    """The MP4 feed-frame endpoint must be wired into the app."""
    app = build_app()
    paths = {route.path for route in app.routes}
    assert "/api/feeds/{camera_id}/frame" in paths
