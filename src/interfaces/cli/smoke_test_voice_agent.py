"""Smoke test: place a live interactive emergency-helpline call.

Dials a real phone (default: the requested cell +19255491150) via the
ElevenLabs Conversational AI agent bridged over Twilio. The agent treats the
callee as an emergency helpline, briefs them with the supplied description,
and answers their questions interactively with low latency.

The emergency description is editable so different scenarios / questions can
be tried immediately:

    # Use the built-in default scenario, call the default number:
    python -m src.interfaces.cli.smoke_test_voice_agent

    # Provide a custom scenario inline:
    python -m src.interfaces.cli.smoke_test_voice_agent \
        --description "Kitchen fire on the 2nd floor, two people evacuating."

    # Type/paste a multi-line description interactively:
    python -m src.interfaces.cli.smoke_test_voice_agent --edit

    # Call a different number:
    python -m src.interfaces.cli.smoke_test_voice_agent --to +14155550123

Requires these env vars (see .env.example): ELEVENLABS_API_KEY,
ELEVENLABS_AGENT_ID, ELEVENLABS_PHONE_NUMBER_ID.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

# The cell phone we want to call by default (requested in the task).
DEFAULT_TO_NUMBER = "+19255491150"

DEFAULT_DESCRIPTION = (
    "A motion sensor in the armed warehouse zone triggered at 2:14 AM. "
    "Camera 3 shows a single intruder near the loading dock carrying what "
    "appears to be a crowbar. No staff are scheduled on site. The nearest "
    "exit is the east gate. Police have not yet been dispatched."
)


def _build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Open Guard voice-agent smoke test (places a real call)."
    )
    parser.add_argument(
        "--to",
        default=DEFAULT_TO_NUMBER,
        help=f"Phone number to call (default: {DEFAULT_TO_NUMBER}).",
    )
    parser.add_argument(
        "--description",
        default=None,
        help="Emergency briefing the agent uses to answer questions.",
    )
    parser.add_argument(
        "--edit",
        action="store_true",
        help="Type/paste the description interactively (end with Ctrl-D).",
    )
    parser.add_argument(
        "--first-message",
        default=None,
        help="Optional override for the agent's opening line.",
    )
    return parser.parse_args()


def _resolve_description(args: argparse.Namespace) -> str:
    if args.description:
        return args.description
    if args.edit:
        print("Enter the emergency description, then press Ctrl-D:\n")
        text = sys.stdin.read().strip()
        return text or DEFAULT_DESCRIPTION
    return DEFAULT_DESCRIPTION


async def _run(args: argparse.Namespace) -> None:
    # Imported locally so --help works without env/credentials configured.
    from src.application.dtos.voice_agent_dtos import (  # noqa: PLC0415
        PlaceEmergencyCallInputDTO,
    )
    from src.infrastructure.container import Container  # noqa: PLC0415

    description = _resolve_description(args)
    container = Container()
    use_case = container.place_emergency_call_use_case()

    print(f"\nPlacing call to {args.to} ...")
    print(f"Briefing: {description}\n")

    result = await use_case.execute(
        PlaceEmergencyCallInputDTO(
            description=description,
            to_number=args.to,
            first_message=args.first_message,
        )
    )

    print("Call placed.")
    print(f"  to_number       : {result.to_number}")
    print(f"  provider_call_id: {result.provider_call_id}")
    print(f"  conversation_id : {result.conversation_id}")


def main() -> None:
    args = _build_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
