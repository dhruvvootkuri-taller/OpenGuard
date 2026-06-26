"""Celery application instance.

Celery is an infrastructure concern: it uses Redis as both broker and result
backend. The application/domain layers never import this module — they depend
only on the ``TaskQueuePort`` abstraction.
"""

from __future__ import annotations

from celery import Celery

from src.infrastructure.config.settings import Settings


def create_celery_app(settings: Settings | None = None) -> Celery:
    """Build a configured Celery app bound to Redis."""
    settings = settings or Settings.from_env()

    app = Celery(
        "open_guard",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["src.infrastructure.tasks.escalation_tasks"],
    )

    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        task_track_started=True,
        worker_prefetch_multiplier=1,
        result_expires=3600,
    )
    return app


# Module-level instance discovered by the Celery CLI:
#   celery -A src.infrastructure.tasks.celery_app:celery_app worker
celery_app = create_celery_app()
