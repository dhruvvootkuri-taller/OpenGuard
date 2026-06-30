"""Twilio implementation of TelephonyPort.

Places outbound voice calls and SMS messages via the Twilio REST API and maps
Twilio's call status onto the provider-agnostic CallOutcome the escalation
logic reasons about.
"""

from __future__ import annotations

from twilio.rest import Client as TwilioClient

from src.application.ports.notification_port import (
    CallOutcome,
    TelephonyPort,
    VoiceMessage,
)

# Twilio call.status -> provider-agnostic CallOutcome.
# https://www.twilio.com/docs/voice/api/call-resource#call-status-values
_STATUS_MAP = {
    "queued": CallOutcome.PENDING,
    "initiated": CallOutcome.PENDING,
    "ringing": CallOutcome.PENDING,
    "in-progress": CallOutcome.ANSWERED,
    "completed": CallOutcome.ANSWERED,
    "busy": CallOutcome.BUSY,
    "no-answer": CallOutcome.NO_ANSWER,
    "failed": CallOutcome.FAILED,
    "canceled": CallOutcome.FAILED,
}


class TwilioTelephonyClient(TelephonyPort):
    def __init__(self, account_sid: str, auth_token: str, from_number: str) -> None:
        self._client = TwilioClient(account_sid, auth_token)
        self._from_number = from_number

    async def place_call(self, to_number: str, message: VoiceMessage) -> str:
        try:
            twiml = f"<Response><Say>{self._escape(message.text)}</Say></Response>"
            call = self._client.calls.create(
                to=to_number, from_=self._from_number, twiml=twiml
            )
            return call.sid
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Twilio call failed: {exc}") from exc

    async def poll_call_status(self, provider_call_id: str) -> CallOutcome:
        try:
            call = self._client.calls(provider_call_id).fetch()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Twilio status fetch failed: {exc}") from exc
        return _STATUS_MAP.get(call.status, CallOutcome.PENDING)

    async def send_sms(self, to_number: str, body: str) -> str:
        try:
            msg = self._client.messages.create(
                to=to_number, from_=self._from_number, body=body
            )
            return msg.sid
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Twilio SMS failed: {exc}") from exc

    @staticmethod
    def _escape(text: str) -> str:
        return (
            text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
