"""Celery implementation of the application ``TaskQueuePort``.

This adapter is the boundary between the application layer (which knows only
about ``TaskQueuePort``) and Celery. It simply forwards intent to enqueue a
job onto the broker — it contains no business logic.
"""

from __future__ import annotations

from celery import Celery

from src.application.ports.task_queue_port import TaskQueuePort


class CeleryTaskQueue(TaskQueuePort):
    """Enqueues background jobs onto the Celery broker (Redis)."""

    def __init__(self, celery_app: Celery) -> None:
        self._celery = celery_app

    def enqueue_escalation(self, event_id: str) -> str:
        # Send by name to avoid importing task functions here (prevents a
        # circular import between the queue and the tasks module).
        async_result = self._celery.send_task(
            "open_guard.escalate_event", args=[event_id]
        )
        return async_result.id
