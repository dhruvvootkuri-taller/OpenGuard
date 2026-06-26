"""Celery worker entry point (interfaces adapter).

The canonical composition root for the worker is ``src/worker.py`` (which, like
``src/main.py``, lives OUTSIDE the architecture layers and is allowed to wire
infrastructure). This module simply re-exposes the configured ``celery_app`` so
the worker can be discovered consistently alongside the other interface entry
points.

Run the worker (either target works):

    celery -A src.worker:celery_app worker --loglevel=info
    celery -A src.interfaces.worker.celery_worker:celery_app worker --loglevel=info
"""

from __future__ import annotations

from src.worker import celery_app

__all__ = ["celery_app"]
