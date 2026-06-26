"""Port (abstraction) for offloading work to a background task queue.

Defined in the application layer so use cases can enqueue slow, side-effectful
work (LLM calls, voice synthesis, telephony) without knowing that **Celery**
sits underneath. Infrastructure provides the concrete implementation.

The application layer must never import Celery directly — it depends only on
this abstraction.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class TaskQueuePort(ABC):
    """Abstraction over an asynchronous task queue (implemented with Celery)."""

    @abstractmethod
    def enqueue_escalation(self, event_id: str) -> str:
        """Schedule escalation (summary + voice + call) for a persisted event.

        Returns an opaque task id that callers may use to track the job.
        """
        raise NotImplementedError
