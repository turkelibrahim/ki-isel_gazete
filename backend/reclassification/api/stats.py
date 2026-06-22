"""FastAPI stats route registration helpers."""
from __future__ import annotations


def register_stats_routes(app, service) -> None:
    """Register stats routes."""
    @app.get("/api/admin/stats/feedback")
    async def feedback_stats():
        return service.feedback_stats()
