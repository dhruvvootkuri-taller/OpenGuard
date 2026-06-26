"""Port (abstraction) for an LLM provider.

Defined in the application layer so use cases can depend on it without
knowing it is Claude Haiku underneath. Infrastructure implements it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMPort(ABC):
    """Abstraction over a large language model used for incident summaries."""

    @abstractmethod
    async def summarize_incident(self, prompt: str) -> str:
        """Return a short, human-readable summary of a security incident."""
        raise NotImplementedError
