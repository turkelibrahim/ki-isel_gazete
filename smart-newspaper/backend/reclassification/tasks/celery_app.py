"""Celery app factory with a no-dependency fallback for local tests."""
from __future__ import annotations

try:  # pragma: no cover - depends on optional Celery install.
    from celery import Celery
    celery_app = Celery("smartnewspaper_reclassification")
    celery_app.config_from_object("backend.reclassification.tasks.celeryconfig", silent=True)
except Exception:  # pragma: no cover
    class _EagerTask:
        def __init__(self, func):
            self.func = func
            self.delay = func
            self.apply_async = lambda args=None, kwargs=None: func(*(args or ()), **(kwargs or {}))
        def __call__(self, *args, **kwargs):
            return self.func(*args, **kwargs)

    class _EagerCelery:
        def task(self, *args, **kwargs):
            def decorator(func):
                return _EagerTask(func)
            return decorator

    celery_app = _EagerCelery()
