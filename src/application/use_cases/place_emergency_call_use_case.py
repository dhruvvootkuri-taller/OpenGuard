"""Use Case: Place an interactive emergency-helpline call.

Orchestration only. It normalizes the destination number, builds the agent
briefing from the (editable) emergency description, and asks the
conversational voice-agent port to dial and start the conversation.

The agent is instructed to behave like an emergency helpline operator:
relaying the situation and answering the callee's questions strictly from
the supplied description.
"""

from __future__ import annotations

from src.application.dtos.voice_agent_dtos import (
    PlaceEmergencyCallInputDTO,
    PlaceEmergencyCallOutputDTO,
)
from src.application.ports.voice_agent_port import (
    ConversationalVoiceAgentPort,
    EmergencyCallRequest,
)


class PlaceEmergencyCallUseCase:
    """Dial a human and brief them via an interactive voice agent."""

    def __init__(
        self,
        voice_agent: ConversationalVoiceAgentPort,
        default_to_number: str,
    ) -> None:
        self._voice_agent = voice_agent
        self._default_to_number = default_to_number

    async def execute(
        self, input_dto: PlaceEmergencyCallInputDTO
    ) -> PlaceEmergencyCallOutputDTO:
        description = input_dto.description.strip()
        if not description:
            raise ValueError("Emergency description must not be empty")

        to_number = self._normalize(
            input_dto.to_number or self._default_to_number
        )
        if not to_number:
            raise ValueError("No destination number provided or configured")

        first_message = input_dto.first_message or (
            "Hello, this is the Open Guard emergency line. "
            "I'm calling about an active situation. How can I help you?"
        )

        result = await self._voice_agent.place_emergency_call(
            EmergencyCallRequest(
                to_number=to_number,
                description=description,
                first_message=first_message,
            )
        )

        return PlaceEmergencyCallOutputDTO(
            to_number=to_number,
            provider_call_id=result.provider_call_id,
            conversation_id=result.conversation_id,
        )

    @staticmethod
    def _normalize(number: str) -> str:
        """Best-effort E.164 normalization for US-style numbers."""
        cleaned = "".join(c for c in number if c.isdigit() or c == "+")
        if not cleaned:
            return ""
        if cleaned.startswith("+"):
            return cleaned
        if len(cleaned) == 10:  # bare US number
            return f"+1{cleaned}"
        return f"+{cleaned}"
