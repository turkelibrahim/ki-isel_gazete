"""System monitoring, health-check and application metrics service."""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, ModerationQueue, NewspaperEdition, Source, User, UserBookmark, UserEvent

logger = logging.getLogger(__name__)


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _project_root() -> Path:
    return _backend_root().parent


class MonitoringService:
    """Collect infrastructure and app-level health information.

    Every check is isolated: Redis, DB, psutil or filesystem failures are returned
    as structured status objects and never crash the whole health endpoint.
    """

    async def check_database(self, db: AsyncSession | None) -> dict[str, Any]:
        """Run a low-cost SELECT 1 latency check."""
        if db is None:
            return {"status": "error", "message": "database session unavailable"}
        started = time.perf_counter()
        try:
            await db.execute(text("SELECT 1"))
            latency_ms = (time.perf_counter() - started) * 1000
            return {"status": "ok", "latency_ms": round(latency_ms, 2)}
        except Exception as exc:  # pragma: no cover - depends on DB availability
            logger.exception("Database health check failed")
            return {"status": "error", "message": str(exc)}

    async def check_redis(self) -> dict[str, Any]:
        """Ping Redis when REDIS_URL is configured; otherwise report disabled."""
        redis_url = (os.getenv("REDIS_URL") or "").strip()
        if not redis_url:
            return {"status": "disabled"}
        try:
            import redis.asyncio as redis_async
        except Exception as exc:  # pragma: no cover - optional dependency
            logger.warning("redis-py is not installed; Redis monitoring disabled: %s", exc)
            return {"status": "disabled", "message": "redis package not installed"}

        started = time.perf_counter()
        client = None
        try:
            client = redis_async.from_url(redis_url, decode_responses=True)
            pong = await client.ping()
            latency_ms = (time.perf_counter() - started) * 1000
            return {"status": "ok" if pong else "error", "latency_ms": round(latency_ms, 2)}
        except Exception as exc:  # pragma: no cover - depends on Redis availability
            logger.exception("Redis health check failed")
            return {"status": "error", "message": str(exc)}
        finally:
            if client is not None:
                try:
                    await client.aclose()
                except Exception:
                    pass

    def check_disk_usage(self) -> dict[str, Any]:
        """Return disk usage for root filesystem."""
        try:
            psutil = _import_psutil()
            usage = psutil.disk_usage("/")
            return {
                "status": "ok",
                "path": "/",
                "percent": float(usage.percent),
                "used_bytes": int(usage.used),
                "total_bytes": int(usage.total),
                "free_bytes": int(usage.free),
            }
        except Exception as exc:  # pragma: no cover - optional dependency/system
            logger.exception("Disk usage check failed")
            return {"status": "error", "message": str(exc)}

    def check_memory_usage(self) -> dict[str, Any]:
        """Return RAM usage metrics."""
        try:
            psutil = _import_psutil()
            memory = psutil.virtual_memory()
            return {
                "status": "ok",
                "percent": float(memory.percent),
                "used_bytes": int(memory.used),
                "total_bytes": int(memory.total),
                "available_bytes": int(memory.available),
            }
        except Exception as exc:  # pragma: no cover
            logger.exception("Memory usage check failed")
            return {"status": "error", "message": str(exc)}

    def check_cpu_usage(self) -> dict[str, Any]:
        """Return CPU percent and core count."""
        try:
            psutil = _import_psutil()
            return {
                "status": "ok",
                "percent": float(psutil.cpu_percent(interval=0.1)),
                "logical_cores": int(psutil.cpu_count(logical=True) or 0),
                "physical_cores": int(psutil.cpu_count(logical=False) or 0),
            }
        except Exception as exc:  # pragma: no cover
            logger.exception("CPU usage check failed")
            return {"status": "error", "message": str(exc)}

    def check_model_files(self) -> dict[str, Any]:
        """Inspect recommender/topic/model directories without failing health."""
        paths = [
            _backend_root() / "models" / "recommenders",
            _backend_root() / "models" / "topics",
            _project_root() / "models",
        ]
        directories: list[dict[str, Any]] = []
        total_files = 0
        for directory in paths:
            entry: dict[str, Any] = {
                "path": str(directory.relative_to(_project_root()) if directory.exists() else directory),
                "exists": directory.exists(),
                "files": [],
            }
            if directory.exists() and directory.is_dir():
                for file_path in sorted(directory.glob("**/*")):
                    if not file_path.is_file() or file_path.name == ".gitkeep":
                        continue
                    stat = file_path.stat()
                    entry["files"].append(
                        {
                            "name": str(file_path.relative_to(directory)),
                            "size_bytes": int(stat.st_size),
                            "modified_at": _dt_to_iso(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)),
                        }
                    )
                total_files += len(entry["files"])
            directories.append(entry)
        return {
            "status": "ok" if total_files else "warning",
            "message": None if total_files else "No model files found yet; train recommender/topic models to create them.",
            "total_files": total_files,
            "directories": directories,
        }

    async def get_system_health(self, db: AsyncSession | None) -> dict[str, Any]:
        """Return full health object for DB, Redis, host metrics and model files."""
        database = await self.check_database(db)
        redis = await self.check_redis()
        disk = self.check_disk_usage()
        memory = self.check_memory_usage()
        cpu = self.check_cpu_usage()
        model_files = self.check_model_files()

        component_statuses = [database, redis, disk, memory, cpu, model_files]
        status = "ok"
        if any(item.get("status") == "error" for item in component_statuses):
            # Redis error is non-fatal for the overall app; DB/host errors matter more.
            hard_errors = [database, disk, memory, cpu]
            status = "degraded" if any(item.get("status") == "error" for item in hard_errors) else "ok"
        return {
            "status": status,
            "checked_at": _dt_to_iso(datetime.now(timezone.utc)),
            "database": database,
            "redis": redis,
            "cpu": cpu,
            "memory": memory,
            "disk": disk,
            "model_files": model_files,
        }

    async def get_application_metrics(self, db: AsyncSession) -> dict[str, Any]:
        """Return admin-dashboard application totals from SQL tables."""
        return {
            "generated_at": _dt_to_iso(datetime.now(timezone.utc)),
            "total_users": await _count(db, User.id),
            "total_articles": await _count(db, Article.id),
            "total_sources": await _count(db, Source.id),
            "active_sources": await _count(db, Source.id, Source.is_active.is_(True)),
            "total_events": await _count(db, UserEvent.id),
            "pending_moderation_count": await _count(db, ModerationQueue.id, ModerationQueue.status == "pending"),
            "total_editions": await _count(db, NewspaperEdition.id),
            "total_bookmarks": await _count(db, UserBookmark.id),
        }


def _import_psutil():
    try:
        import psutil
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("psutil package is required for system metrics. Install with: pip install psutil") from exc
    return psutil


async def _count(db: AsyncSession, column: Any, *where_clauses: Any) -> int:
    stmt = select(func.count(column))
    if where_clauses:
        stmt = stmt.where(*where_clauses)
    value = (await db.execute(stmt)).scalar_one()
    return int(value or 0)


def _dt_to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
