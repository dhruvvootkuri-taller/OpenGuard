"""Claude Haiku implementation of the LLMPort.

Wraps the Anthropic SDK behind the clean application-layer abstraction.
"""

from __future__ import annotations

from anthropic import AsyncAnthropic

from src.application.ports.llm_port import LLMPort


class ClaudeHaikuClient(LLMPort):
    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307") -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def summarize_incident(self, prompt: str) -> str:
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=120,
                system=(
                    "You are Open Guard, a concise security incident assistant. "
                    "Respond with a single clear sentence."
                ),
                messages=[{"role": "user", "content": prompt}],
            )
            parts = [block.text for block in response.content if block.type == "text"]
            return " ".join(parts).strip()
        except Exception as exc:  # noqa: BLE001 - re-raise as a clean error
            raise RuntimeError(f"Claude Haiku request failed: {exc}") from exc
