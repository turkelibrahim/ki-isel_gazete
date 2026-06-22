"""FastAPI verification route registration helpers."""
from __future__ import annotations


def register_verify_routes(app, service) -> None:
    """Register verification routes."""
    @app.post("/api/admin/verify/{record_id}")
    async def verify(record_id: int, body: dict):
        return service.verify(record_id, body)
