"""Composition root for Open Guard.

This is the ONLY module allowed to know about every layer at once.
It wires the infrastructure Container into the interfaces controllers and
exposes the ASGI `app` object for uvicorn.

Run:
    uvicorn src.main:app --reload
"""

from __future__ import annotations

from src.infrastructure.container import Container
from src.interfaces.http.app import create_app
from src.interfaces.http.auth import Authenticator
from src.interfaces.http.controllers.security_event_controller import (
    SecurityEventController,
)
from src.interfaces.http.controllers.voice_agent_controller import (
    VoiceAgentController,
)


def build_app():
    container = Container()

    # Keys come from config (env). Empty set => auth fails closed (deny).
    authenticator = Authenticator(container.settings.api_keys)

    controller = SecurityEventController(
        process_detection=container.process_detection_use_case(),
        acknowledge_event=container.acknowledge_event_use_case(),
        list_recent_events=container.list_recent_events_use_case(),
        analyze_feed_frame=container.analyze_feed_frame_use_case(),
        resolve_event=container.resolve_event_use_case(),
        dismiss_event=container.dismiss_event_use_case(),
        clear_resolved_events=container.clear_resolved_events_use_case(),
        authenticator=authenticator,
    )

    voice_controller = VoiceAgentController(
        place_emergency_call=container.place_emergency_call_use_case(),
        authenticator=authenticator,
    )

    return create_app(
        security_event_controller=controller,
        voice_agent_controller=voice_controller,
    )


app = build_app()
