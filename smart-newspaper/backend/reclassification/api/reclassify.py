"""FastAPI reclassification route registration helpers."""
from __future__ import annotations


def register_reclassify_routes(app, service) -> None:
    """Register correction routes for a separate FastAPI deployment."""
    @app.post("/api/admin/reclassify")
    async def reclassify(body: dict):
        return service.reclassify(body)

    @app.get("/api/admin/reclassify/queue")
    async def queue():
        return service.queue()
