"""Tests for PlaceEmergencyCallUseCase.

Uses an in-memory fake voice-agent port, proving the use case depends only on
the abstraction (no ElevenLabs/Twilio credentials required).
"""

import pytest

from src.application.dtos.voice_agent_dtos import PlaceEmergencyCallInputDTO
from src.application.ports.voice_agent_port import (
    ConversationalVoiceAgentPort,
    EmergencyCallRequest,
    EmergencyCallResult,
)
from src.application.use_cases.place_emergency_call_use_case import (
    PlaceEmergencyCallUseCase,
)


class FakeVoiceAgent(ConversationalVoiceAgentPort):
    def __init__(self):
        self.requests: list[EmergencyCallRequest] = []

    async def place_emergency_call(
        self, request: EmergencyCallRequest
    ) -> EmergencyCallResult:
        self.requests.append(request)
        return EmergencyCallResult(
            provider_call_id="CA123", conversation_id="conv-1"
        )


@pytest.mark.asyncio
async def test_places_call_with_editable_description():
    agent = FakeVoiceAgent()
    use_case = PlaceEmergencyCallUseCase(
        voice_agent=agent, default_to_number="+15555550199"
    )

    result = await use_case.execute(
        PlaceEmergencyCallInputDTO(
            description="Fire on the 2nd floor.", to_number="9255491150"
        )
    )

    assert len(agent.requests) == 1
    assert agent.requests[0].description == "Fire on the 2nd floor."
    # Bare US number is normalized to E.164.
    assert agent.requests[0].to_number == "+19255491150"
    assert result.to_number == "+19255491150"
    assert result.provider_call_id == "CA123"
    assert result.conversation_id == "conv-1"


@pytest.mark.asyncio
async def test_falls_back_to_default_number():
    agent = FakeVoiceAgent()
    use_case = PlaceEmergencyCallUseCase(
        voice_agent=agent, default_to_number="+19255491150"
    )

    await use_case.execute(
        PlaceEmergencyCallInputDTO(description="Intruder detected.")
    )

    assert agent.requests[0].to_number == "+19255491150"


@pytest.mark.asyncio
async def test_default_first_message_is_supplied():
    agent = FakeVoiceAgent()
    use_case = PlaceEmergencyCallUseCase(
        voice_agent=agent, default_to_number="+19255491150"
    )

    await use_case.execute(
        PlaceEmergencyCallInputDTO(description="Gas leak reported.")
    )

    assert agent.requests[0].first_message
    assert "emergency line" in agent.requests[0].first_message.lower()


@pytest.mark.asyncio
async def test_empty_description_rejected():
    use_case = PlaceEmergencyCallUseCase(
        voice_agent=FakeVoiceAgent(), default_to_number="+19255491150"
    )

    with pytest.raises(ValueError):
        await use_case.execute(PlaceEmergencyCallInputDTO(description="   "))


@pytest.mark.asyncio
async def test_already_e164_number_unchanged():
    agent = FakeVoiceAgent()
    use_case = PlaceEmergencyCallUseCase(
        voice_agent=agent, default_to_number="+15555550199"
    )

    await use_case.execute(
        PlaceEmergencyCallInputDTO(
            description="Alarm triggered.", to_number="+447700900123"
        )
    )

    assert agent.requests[0].to_number == "+447700900123"
