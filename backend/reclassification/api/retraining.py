"""FastAPI retraining route registration helpers."""
from __future__ import annotations


def register_retraining_routes(app, service) -> None:
    """Register retraining routes."""
    @app.get("/api/admin/retraining/status")
    async def status():
        return service.retraining_status()
