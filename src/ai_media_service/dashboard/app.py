"""
FastAPI dashboard.
Endpoints:
  GET  /              → HTML summary page
  GET  /api/tasks     → recent agent tasks JSON
  GET  /api/content   → content items with qa_status
  GET  /api/metrics   → weekly metrics
  POST /api/content/{id}/approve  → approve content
  POST /api/content/{id}/reject   → reject content
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import desc

from ..database import get_session, init_db
from ..db_models import AgentTaskDB, ContentItemDB, WeeklyMetricsDB
from ..integrations.telegram_bot import publish_to_channel
from ..logging_config import setup_logging
from ..redis_client import get_all_rate_limits

setup_logging()
init_db()

app = FastAPI(title="AI Media Service Dashboard", version="1.0.0")

_STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC), name="static")


# ── API endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/tasks")
def get_tasks(limit: int = 50) -> list[dict]:
    with get_session() as session:
        rows = (
            session.query(AgentTaskDB)
            .order_by(desc(AgentTaskDB.created_at))
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "week": r.week,
                "assigned_to": r.assigned_to,
                "status": r.status,
                "task": r.task_description[:120],
                "result_preview": (r.result or "")[:200],
                "created_at": str(r.created_at),
            }
            for r in rows
        ]


@app.get("/api/content")
def get_content(status: str | None = None, limit: int = 30) -> list[dict]:
    with get_session() as session:
        q = session.query(ContentItemDB).order_by(desc(ContentItemDB.created_at))
        if status:
            q = q.filter(ContentItemDB.qa_status == status)
        rows = q.limit(limit).all()
        return [
            {
                "id": r.id,
                "niche_key": r.niche_key,
                "topic": r.source_idea,
                "qa_status": r.qa_status,
                "article_preview": r.website_article[:300],
                "telegram_posts": r.telegram_posts,
                "shorts_count": len(r.short_video_scripts or []),
                "created_at": str(r.created_at),
            }
            for r in rows
        ]


@app.get("/api/metrics")
def get_metrics(limit: int = 20) -> list[dict]:
    with get_session() as session:
        rows = (
            session.query(WeeklyMetricsDB)
            .order_by(desc(WeeklyMetricsDB.recorded_at))
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "niche_key": r.niche_key,
                "week": r.week,
                "views": r.views,
                "retention_pct": r.retention_pct,
                "ctr_pct": r.ctr_pct,
                "engagement_rate_pct": r.engagement_rate_pct,
                "subscribers_delta": r.subscribers_delta,
                "leads": r.leads,
            }
            for r in rows
        ]


@app.get("/api/rate-limit")
def rate_limit_status() -> dict:
    """Returns rate limit state for all providers."""
    try:
        return get_all_rate_limits()
    except Exception:
        return {}


@app.post("/api/content/{content_id}/approve")
def approve_content(content_id: int) -> dict:
    with get_session() as session:
        item = session.get(ContentItemDB, content_id)
        if not item:
            raise HTTPException(status_code=404, detail="Content not found")
        item.qa_status = "approved"
        session.commit()
    publish_to_channel(content_id)
    return {"status": "approved", "content_id": content_id}


@app.post("/api/content/{content_id}/reject")
def reject_content(content_id: int) -> dict:
    with get_session() as session:
        item = session.get(ContentItemDB, content_id)
        if not item:
            raise HTTPException(status_code=404, detail="Content not found")
        item.qa_status = "rejected"
        session.commit()
    return {"status": "rejected", "content_id": content_id}


# ── HTML dashboard ────────────────────────────────────────────────────────────

@app.get("/", response_class=FileResponse)
def dashboard() -> FileResponse:
    return FileResponse(_STATIC / "index.html")
