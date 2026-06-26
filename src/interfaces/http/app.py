"""FastAPI application factory.

Receives already-constructed controllers (dependency injection from the
composition root). This file does NOT import infrastructure — keeping the
interfaces layer dependent only on application contracts.
"""

from __future__ import annotations

from fastapi import FastAPI

from src.interfaces.http.controllers.security_event_controller import (
    SecurityEventController,
)


def create_app(security_event_controller: SecurityEventController) -> FastAPI:
    app = FastAPI(
        title="Open Guard API",
        description="AI-powered security monitoring & alerting",
        version="0.1.0",
    )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "open-guard"}

    app.include_router(security_event_controller.router)
    return app
