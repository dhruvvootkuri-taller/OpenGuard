"""Twilio implementation of TelephonyPort.

Places outbound voice calls and SMS messages via the Twilio REST API.
"""

from __future__ import annotations

from twilio.rest import Client as TwilioClient

from src.application.ports.notification_port import TelephonyPort, VoiceMessage


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
