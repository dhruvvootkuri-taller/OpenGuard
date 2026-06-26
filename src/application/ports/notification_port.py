"""Ports for outbound notifications (voice + telephony).

Implemented in infrastructure by ElevenLabs (voice synthesis) and
Twilio (calls / SMS).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceMessage:
    text: str
    audio_url: str | None = None


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
    async def send_sms(self, to_number: str, body: str) -> str:
        """Send an SMS. Returns a provider message id."""
        raise NotImplementedError
