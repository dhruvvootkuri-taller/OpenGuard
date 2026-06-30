"""Ports for outbound notifications (voice + telephony).

Implemented in infrastructure by ElevenLabs (voice synthesis) and
Twilio (calls / SMS).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class VoiceMessage:
    text: str
    audio_url: str | None = None


class CallOutcome(str, Enum):
    """Provider-reported outcome of an outbound call.

    Used by the escalation logic to decide whether a contact was reached or the
    call must be retried / fall back to the next contact.
    """

    # Still in flight — keep polling.
    PENDING = "pending"
    # Reached a human / conversation under way or finished normally.
    ANSWERED = "answered"
    # Terminal "not reached" states that warrant a retry / fallback.
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    FAILED = "failed"

    def is_terminal(self) -> bool:
        """True once the provider will report nothing further for this call."""
        return self is not CallOutcome.PENDING

    def reached(self) -> bool:
        """True when a human was reached and no retry is needed."""
        return self is CallOutcome.ANSWERED


class VoiceSynthesisPort(ABC):
    """Abstraction over a text-to-speech provider (ElevenLabs)."""

    @abstractmethod
    async def synthesize(self, text: str) -> VoiceMessage:
        """Convert text into a playable voice message."""
        raise NotImplementedError


class TelephonyPort(ABC):
    """Abstraction over a telephony provider (Twilio)."""

    @abstractmethod
    async def place_call(self, to_number: str, message: VoiceMessage) -> str:
        """Place an outbound call. Returns a provider call id."""
        raise NotImplementedError

    @abstractmethod
    async def poll_call_status(self, provider_call_id: str) -> CallOutcome:
        """Return the current outcome of a previously placed call.

        Implementations map the provider's call status onto a CallOutcome.
        Returns ``CallOutcome.PENDING`` while the call is still ringing /
        queued so the caller can keep polling until a terminal outcome.
        """
        raise NotImplementedError

    @abstractmethod
    async def send_sms(self, to_number: str, body: str) -> str:
        """Send an SMS. Returns a provider message id."""
        raise NotImplementedError
