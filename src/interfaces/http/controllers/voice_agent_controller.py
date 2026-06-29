"""HTTP controller for the emergency voice agent.

Thin: validate input -> call use case -> serialize output. Imports only from
the application layer (use case + DTOs) and the web framework.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.application.dtos.voice_agent_dtos import PlaceEmergencyCallInputDTO
from src.application.use_cases.place_emergency_call_use_case import (
    PlaceEmergencyCallUseCase,
)
from src.interfaces.http.auth import Authenticator
from src.interfaces.http.schemas import (
    EmergencyCallRequest,
    EmergencyCallResponse,
)


class VoiceAgentController:
    """Wires the emergency-call use case into FastAPI routes."""

    def __init__(
        self,
        place_emergency_call: PlaceEmergencyCallUseCase,
        authenticator: Authenticator,
    ) -> None:
        self._place_emergency_call = place_emergency_call
        self._authenticator = authenticator
        self.router = APIRouter(prefix="/api/voice", tags=["voice"])
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            "/calls",
            self.place_call,
            methods=["POST"],
            response_model=EmergencyCallResponse,
            status_code=201,
            # Placing a REAL outbound phone call always requires auth.
            dependencies=[Depends(self._authenticator.dependency())],
        )

    async def place_call(
        self, request: EmergencyCallRequest
    ) -> EmergencyCallResponse:
        try:
            result = await self._place_emergency_call.execute(
                PlaceEmergencyCallInputDTO(
                    description=request.description,
                    to_number=request.to_number,
                    first_message=request.first_message,
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return EmergencyCallResponse(
            to_number=result.to_number,
            provider_call_id=result.provider_call_id,
            conversation_id=result.conversation_id,
        )
