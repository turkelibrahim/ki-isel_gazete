"""FastAPI auth route registration helpers."""
from __future__ import annotations


def register_auth_routes(app, service) -> None:
    """Register auth routes when FastAPI is used as a separate service."""
    @app.post("/api/admin/auth/login")
    async def login(body: dict):
        return service.login(body.get("username", ""), body.get("password", ""))
