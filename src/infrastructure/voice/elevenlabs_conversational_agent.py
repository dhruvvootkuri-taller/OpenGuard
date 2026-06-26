"""ElevenLabs Conversational AI implementation of the voice-agent port.

Uses ElevenLabs Conversational AI bridged over Twilio to run a low-latency,
full-duplex phone conversation. The emergency description is injected at call
time as a dynamic prompt override so the same provisioned agent can handle
any scenario without reconfiguration.

Provisioning (done once, out of band):
  * Create a Conversational AI *agent* in the ElevenLabs dashboard
    -> ``ELEVENLABS_AGENT_ID``.
  * Import the Twilio number into ElevenLabs (Phone Numbers)
    -> ``ELEVENLABS_PHONE_NUMBER_ID``.

Reference: https://elevenlabs.io/docs/conversational-ai/api-reference/twilio/outbound-call
"""

from __future__ import annotations

import httpx

from src.application.ports.voice_agent_port import (
    ConversationalVoiceAgentPort,
    EmergencyCallRequest,
    EmergencyCallResult,
)

_OUTBOUND_CALL_URL = (
    "https://api.elevenlabs.io/v1/convai/twilio/outbound-call"
)

_SYSTEM_PROMPT = (
    "You are an Open Guard emergency helpline operator speaking on a live "
    "phone call. Stay calm, clear, and concise. You are briefing the person "
    "you called about an active emergency and answering their questions. "
    "Answer ONLY from the emergency briefing below. If asked something the "
    "briefing does not cover, say you do not have that information yet and "
    "will follow up. Keep replies short so the conversation flows naturally.\n\n"
    "EMERGENCY BRIEFING:\n{description}"
)


class ElevenLabsConversationalAgent(ConversationalVoiceAgentPort):
    def __init__(
        self,
        api_key: str,
        agent_id: str,
        phone_number_id: str,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._agent_id = agent_id
        self._phone_number_id = phone_number_id
        self._timeout = timeout

    async def place_emergency_call(
        self, request: EmergencyCallRequest
    ) -> EmergencyCallResult:
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        prompt = _SYSTEM_PROMPT.format(description=request.description)
        body: dict[str, object] = {
            "agent_id": self._agent_id,
            "agent_phone_number_id": self._phone_number_id,
            "to_number": request.to_number,
            # Inject the editable briefing without re-provisioning the agent.
            "conversation_initiation_client_data": {
                "conversation_config_override": {
                    "agent": {
                        "prompt": {"prompt": prompt},
                        "first_message": request.first_message or "",
                    }
                }
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    _OUTBOUND_CALL_URL, headers=headers, json=body
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"ElevenLabs outbound call failed: {exc}"
            ) from exc

        call_id = (
            data.get("callSid")
            or data.get("call_sid")
            or data.get("conversation_id")
            or ""
        )
        return EmergencyCallResult(
            provider_call_id=str(call_id),
            conversation_id=data.get("conversation_id"),
        )
