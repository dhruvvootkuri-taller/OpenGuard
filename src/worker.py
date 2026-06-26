"""Composition root for the Open Guard Celery worker.

Mirrors ``src/main.py``: this module sits OUTSIDE the four architecture layers
and is therefore permitted to know about infrastructure. It exposes the
configured ``celery_app`` (with all tasks registered) for the Celery CLI.

Run the worker:

    celery -A src.worker:celery_app worker --loglevel=info
"""

from __future__ import annotations

# Importing the tasks module registers the task functions on the Celery app.
from src.infrastructure.tasks import escalation_tasks  # noqa: F401
from src.infrastructure.tasks.celery_app import celery_app

__all__ = ["celery_app"]
