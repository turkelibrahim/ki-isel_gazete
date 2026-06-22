"""Optional FastAPI entrypoint for the reclassification service."""
from __future__ import annotations

try:
    from fastapi import FastAPI
except Exception:  # pragma: no cover
    FastAPI = None


def create_app(service=None):
    """Create a FastAPI app when FastAPI is installed."""
    if FastAPI is None:
        raise RuntimeError("FastAPI yüklü değil. Node adapter mevcut sistemi çalıştırmaya devam eder.")
    app = FastAPI(title="SmartNewspaper Reclassification API")
    return app
