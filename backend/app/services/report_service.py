"""PDF and CSV reporting service built from analytics metrics."""

from __future__ import annotations

import csv
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ModerationQueue
from app.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)


class ReportService:
    """Generate downloadable admin reports from analytics aggregations.

    Matplotlib and pandas are imported lazily so the backend can still boot in
    minimal environments. The generate endpoint returns a controlled error when
    an optional report dependency is missing instead of crashing application
    import.
    """

    def __init__(self) -> None:
        self.reports_dir = _reports_dir()
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.analytics_service = AnalyticsService()

    async def generate_overview_report(self, db: AsyncSession, days: int = 30, format: str = "pdf") -> dict[str, Any]:
        """Build analytics data and write a PDF or CSV report file."""
        safe_days = _clamp_int(days, minimum=1, maximum=365, default=30)
        report_format = (format or "pdf").strip().lower()
        if report_format not in {"pdf", "csv"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="format must be pdf or csv")

        data = await self.build_report_data(db, days=safe_days)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = self.reports_dir / f"report_{timestamp}.{report_format}"

        if report_format == "pdf":
            path = self.generate_pdf_report(data, str(output_path))
        else:
            path = self.generate_csv_report(data, str(output_path))

        return {
            "status": "generated",
            "format": report_format,
            "path": path,
            "filename": Path(path).name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "days": safe_days,
        }

    async def build_report_data(self, db: AsyncSession, days: int = 30) -> dict[str, Any]:
        """Collect all analytics sections used by PDF/CSV exports."""
        safe_days = _clamp_int(days, minimum=1, maximum=365, default=30)
        generated_at = datetime.now(timezone.utc).isoformat()
        try:
            overview = await self.analytics_service.get_overview(db)
            daily_active_users = await self.analytics_service.get_daily_active_users(db, days=safe_days)
            top_articles = await self.analytics_service.get_top_articles(db, days=min(safe_days, 30), limit=20)
            category_reads = await self.analytics_service.get_category_reads(db, days=safe_days)
            source_performance = await self.analytics_service.get_source_performance(db, days=safe_days)
            moderation_summary = await self._get_moderation_summary(db, days=safe_days)
        except Exception as exc:
            logger.exception("Report analytics data collection failed")
            return {
                "status": "partial",
                "generated_at": generated_at,
                "days": safe_days,
                "overview": {"error": str(exc)},
                "daily_active_users": [],
                "top_articles": [],
                "category_reads": [],
                "source_performance": [],
                "moderation_summary": {"total": 0, "by_status": [], "error": str(exc)},
            }

        return {
            "status": "ok",
            "generated_at": generated_at,
            "days": safe_days,
            "overview": overview,
            "daily_active_users": daily_active_users,
            "top_articles": top_articles,
            "category_reads": category_reads,
            "source_performance": source_performance,
            "moderation_summary": moderation_summary,
        }

    def generate_pdf_report(self, data: dict[str, Any], output_path: str) -> str:
        """Generate a multi-page Matplotlib PDF report."""
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_pdf import PdfPages
        except Exception as exc:
            logger.exception("Matplotlib is required for PDF report generation")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="matplotlib is required for PDF report generation",
            ) from exc

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with PdfPages(path) as pdf:
            self._pdf_overview_page(plt, pdf, data)
            self._pdf_dau_page(plt, pdf, data.get("daily_active_users", []))
            self._pdf_category_page(plt, pdf, data.get("category_reads", []))
            self._pdf_table_page(plt, pdf, "Top Articles", data.get("top_articles", []), ["article_id", "title", "engagement_score", "read_count", "bookmark_count", "share_count"])
            self._pdf_table_page(plt, pdf, "Source Performance", data.get("source_performance", []), ["source_id", "source_name", "article_count", "total_views", "trust_score", "engagement_score"])
        return str(path)

    def generate_csv_report(self, data: dict[str, Any], output_path: str) -> str:
        """Generate a single flattened UTF-8-SIG CSV export."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = list(_flatten_report_rows(data))

        try:
            import pandas as pd

            frame = pd.DataFrame(rows, columns=["metric_type", "key", "value", "date"])
            frame.to_csv(path, index=False, encoding="utf-8-sig")
        except Exception:
            logger.warning("pandas CSV export failed; falling back to stdlib csv", exc_info=True)
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["metric_type", "key", "value", "date"])
                writer.writeheader()
                writer.writerows(rows)
        return str(path)

    def cleanup_old_reports(self, days: int = 30) -> dict[str, Any]:
        """Delete report files older than the configured retention window."""
        safe_days = _clamp_int(days, minimum=1, maximum=3650, default=30)
        cutoff = datetime.now(timezone.utc) - timedelta(days=safe_days)
        deleted: list[str] = []
        skipped: list[str] = []
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        for path in self.reports_dir.glob("report_*.*"):
            if path.suffix.lower() not in {".pdf", ".csv"}:
                skipped.append(path.name)
                continue
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if modified_at < cutoff:
                path.unlink(missing_ok=True)
                deleted.append(path.name)
        return {"status": "completed", "days": safe_days, "deleted": deleted, "deleted_count": len(deleted), "skipped": skipped}

    def list_reports(self) -> list[dict[str, Any]]:
        """List generated report files newest first."""
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        items: list[dict[str, Any]] = []
        for path in self.reports_dir.iterdir():
            if not path.is_file() or path.suffix.lower() not in {".pdf", ".csv"}:
                continue
            stat = path.stat()
            items.append(
                {
                    "filename": path.name,
                    "path": str(path),
                    "format": path.suffix.lower().lstrip("."),
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                }
            )
        return sorted(items, key=lambda item: item["modified_at"], reverse=True)

    async def _get_moderation_summary(self, db: AsyncSession, days: int = 30) -> dict[str, Any]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(ModerationQueue.status, func.count(ModerationQueue.id).label("count"))
            .where(ModerationQueue.created_at >= since)
            .group_by(ModerationQueue.status)
            .order_by(ModerationQueue.status)
        )
        rows = (await db.execute(stmt)).all()
        by_status = [{"status": row.status or "unknown", "count": int(row.count or 0)} for row in rows]
        return {"total": sum(item["count"] for item in by_status), "by_status": by_status, "days": days}

    def _pdf_overview_page(self, plt: Any, pdf: Any, data: dict[str, Any]) -> None:
        fig = plt.figure(figsize=(8.27, 11.69))
        ax = fig.add_subplot(111)
        ax.axis("off")
        overview = data.get("overview") or {}
        moderation = data.get("moderation_summary") or {}
        lines = [
            "Smart Personnel Newspaper — Analytics Report",
            "",
            f"Generated at: {data.get('generated_at', '-')}",
            f"Period: last {data.get('days', '-')} days",
            "",
            f"Total users: {overview.get('total_users', 0)}",
            f"Total articles: {overview.get('total_articles', 0)}",
            f"Total events: {overview.get('total_events', 0)}",
            f"Total bookmarks: {overview.get('total_bookmarks', 0)}",
            f"Active users 7d: {overview.get('active_users_7d', 0)}",
            "",
            f"Top category: {_safe_name(overview.get('top_category'))}",
            f"Top article: {_safe_name(overview.get('top_article'))}",
            "",
            f"Moderation total: {moderation.get('total', 0)}",
        ]
        for item in moderation.get("by_status", []):
            lines.append(f"- {item.get('status')}: {item.get('count')}")
        ax.text(0.06, 0.94, "\n".join(lines), va="top", ha="left", fontsize=12, wrap=True)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    def _pdf_dau_page(self, plt: Any, pdf: Any, rows: list[dict[str, Any]]) -> None:
        fig = plt.figure(figsize=(11.69, 8.27))
        ax = fig.add_subplot(111)
        ax.set_title("Daily Active Users")
        if rows:
            dates = [str(row.get("date", "")) for row in rows]
            values = [int(row.get("active_users") or 0) for row in rows]
            ax.plot(dates, values, marker="o")
            ax.set_xlabel("Date")
            ax.set_ylabel("Active users")
            ax.tick_params(axis="x", rotation=45)
        else:
            ax.text(0.5, 0.5, "No DAU data", ha="center", va="center")
            ax.axis("off")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    def _pdf_category_page(self, plt: Any, pdf: Any, rows: list[dict[str, Any]]) -> None:
        fig = plt.figure(figsize=(11.69, 8.27))
        ax = fig.add_subplot(111)
        ax.set_title("Category Reads")
        top_rows = rows[:20]
        if top_rows:
            labels = [str(row.get("category_name") or row.get("category_id") or "-")[:28] for row in top_rows]
            values = [float(row.get("engagement_score") or row.get("read_count") or 0.0) for row in top_rows]
            ax.bar(labels, values)
            ax.set_xlabel("Category")
            ax.set_ylabel("Engagement score")
            ax.tick_params(axis="x", rotation=45)
        else:
            ax.text(0.5, 0.5, "No category data", ha="center", va="center")
            ax.axis("off")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    def _pdf_table_page(self, plt: Any, pdf: Any, title: str, rows: list[dict[str, Any]], columns: list[str]) -> None:
        fig = plt.figure(figsize=(11.69, 8.27))
        ax = fig.add_subplot(111)
        ax.axis("off")
        ax.set_title(title)
        table_rows = rows[:20]
        if not table_rows:
            ax.text(0.5, 0.5, f"No {title.lower()} data", ha="center", va="center")
        else:
            cell_text = [[_truncate(row.get(column, ""), 60) for column in columns] for row in table_rows]
            table = ax.table(cellText=cell_text, colLabels=columns, loc="center")
            table.auto_set_font_size(False)
            table.set_fontsize(8)
            table.scale(1, 1.3)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)


def _reports_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "storage" / "reports"


def _clamp_int(value: int | str | None, minimum: int, maximum: int, default: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _flatten_report_rows(data: dict[str, Any]):
    generated_at = str(data.get("generated_at") or datetime.now(timezone.utc).isoformat())
    for key, value in (data.get("overview") or {}).items():
        yield {"metric_type": "overview", "key": str(key), "value": _csv_value(value), "date": generated_at}
    for section in ["daily_active_users", "top_articles", "category_reads", "source_performance"]:
        for index, row in enumerate(data.get(section) or []):
            if isinstance(row, dict):
                row_date = str(row.get("date") or row.get("published_at") or generated_at)
                for key, value in row.items():
                    yield {"metric_type": section, "key": f"{index}.{key}", "value": _csv_value(value), "date": row_date}
    moderation = data.get("moderation_summary") or {}
    for key, value in moderation.items():
        if key == "by_status" and isinstance(value, list):
            for index, item in enumerate(value):
                yield {"metric_type": "moderation_summary", "key": f"by_status.{index}", "value": _csv_value(item), "date": generated_at}
        else:
            yield {"metric_type": "moderation_summary", "key": str(key), "value": _csv_value(value), "date": generated_at}


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        import json

        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _safe_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("category_name") or value.get("title") or value.get("name") or value.get("id") or "-")
    return str(value or "-")


def _truncate(value: Any, length: int) -> str:
    text = _csv_value(value).replace("\n", " ")
    return text if len(text) <= length else text[: length - 1] + "…"
