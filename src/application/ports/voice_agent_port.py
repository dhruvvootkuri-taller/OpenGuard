"""Port for an interactive, conversational voice agent.

Unlike :class:`TelephonyPort` (which plays a one-shot, non-interactive
message), this port models a *two-way* phone conversation: the callee can
speak, ask questions, and the agent answers with low latency based on a
supplied emergency briefing.

Implemented in infrastructure by ElevenLabs Conversational AI bridged over
Twilio. Defined in the application layer so use cases stay provider-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class EmergencyCallRequest:
    """Everything the agent needs to brief the callee about an emergency.

    ``description`` is the free-form briefing the agent treats as ground
    truth when answering questions. ``first_message`` is what the agent says
    immediately after the callee picks up.
    """

    to_number: str
    description: str
    first_message: str | None = None


@dataclass(frozen=True)
class EmergencyCallResult:
    """Outcome of placing a conversational call."""

    provider_call_id: str
    conversation_id: str | None = None


class ConversationalVoiceAgentPort(ABC):
    """Abstraction over an interactive voice-agent provider."""

    @abstractmethod
    async def place_emergency_call(
        self, request: EmergencyCallRequest
    ) -> EmergencyCallResult:
        """Dial the callee and start an interactive emergency conversation."""
        raise NotImplementedError
