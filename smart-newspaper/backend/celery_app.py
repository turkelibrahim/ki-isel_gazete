"""Celery application wiring for scheduled news ingestion tasks."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from celery import Celery

# Allow Celery workers launched from the project root with
# ``celery -A backend.celery_app ...`` to resolve the existing ``app`` package.
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "smart_personnel_newspaper",
    broker=REDIS_URL,
    backend=os.getenv("CELERY_RESULT_BACKEND", REDIS_URL),
)

celery_app.conf.update(
    timezone="Europe/Istanbul",
    enable_utc=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
)

celery_app.config_from_object("backend.celeryconfig")
celery_app.autodiscover_tasks(["app.tasks"])
