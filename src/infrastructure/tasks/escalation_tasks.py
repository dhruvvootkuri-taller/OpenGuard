"""Celery task definitions.

Tasks are thin infrastructure adapters: they build the DI container, resolve a
use case, and run it. All orchestration lives in the use case; all business
rules live in the domain. The task itself contains no logic beyond bridging
Celery's synchronous worker model to our async use cases.
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.infrastructure.tasks.celery_app import celery_app


def _run_async(coro: Any) -> Any:
    """Run an async use case inside a synchronous Celery worker."""
    return asyncio.run(coro)


@celery_app.task(
    name="open_guard.escalate_event",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def escalate_event_task(self: Any, event_id: str) -> dict[str, Any]:
    """Run the EscalateEventUseCase for a persisted event.

    Imports are local to keep the container (which touches every layer) out of
    module import time and to avoid circular imports with the Celery app.
    """
    from src.infrastructure.container import Container  # noqa: PLC0415

    container = Container()
    use_case = container.escalate_event_use_case()
    try:
        result = _run_async(use_case.execute(event_id))
    except Exception as exc:  # noqa: BLE001 - let Celery handle retry/backoff
        raise self.retry(exc=exc)
    return {"event_id": result.id, "status": result.status, "escalated": result.escalated}
