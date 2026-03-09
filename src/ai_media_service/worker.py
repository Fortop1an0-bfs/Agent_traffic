"""
Celery app + tasks.

Worker start:
    celery -A src.ai_media_service.worker worker --loglevel=info

Beat scheduler (weekly cron):
    celery -A src.ai_media_service.worker beat --loglevel=info
"""
from __future__ import annotations

import logging

from celery import Celery
from celery.schedules import crontab

from .config import settings
from .logging_config import setup_logging

setup_logging()
log = logging.getLogger(__name__)

# Redis as broker AND result backend
app = Celery(
    "agent_traffic",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Moscow",
    enable_utc=True,
    # Weekly Monday 09:00 Moscow — run week N automatically
    beat_schedule={
        "weekly-content-run": {
            "task": "src.ai_media_service.worker.run_weekly_content",
            "schedule": crontab(hour=9, minute=0, day_of_week="monday"),
            "args": [],
        },
    },
)


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_weekly_content(self, week: int | None = None) -> dict[str, str]:  # type: ignore[type-arg]
    """
    Main weekly task: Chief Agent runs for all pilot niches.
    Called automatically by Celery Beat every Monday, or manually:
        celery -A src.ai_media_service.worker call run_weekly_content
    """
    from .database import init_db
    from .agents.chief import ChiefAgent
    from .niches import build_niche_catalog, choose_pilot_niches
    from .redis_client import get_redis

    init_db()

    # Determine week number from Redis counter
    r = get_redis()
    if week is None:
        week = int(r.incr("agent:current_week"))
        log.info("Auto-incremented week → %d", week)

    pilots = choose_pilot_niches()
    catalog = build_niche_catalog()
    goals = [
        "рост подписчиков с нуля",
        "высокий охват и вовлечённость",
        "монетизация через партнёрки, рекламу и инфопродукты",
        "узнаваемость в нише",
    ]
    chief = ChiefAgent()

    results: dict[str, str] = {}
    for niche_key in pilots:
        log.info("Running week %d for niche '%s' (%s)", week, niche_key, catalog[niche_key].title)
        try:
            summary = chief.run_week(week=week, niche_key=niche_key, business_goals=goals)
            results[niche_key] = summary
        except Exception as exc:
            log.error("Niche %s failed: %s", niche_key, exc)
            self.retry(exc=exc)

    log.info("Weekly run complete: week=%d, niches=%s", week, list(results.keys()))
    return results


@app.task
def run_single_niche(niche_key: str, week: int, goals: list[str] | None = None) -> str:
    """Run Chief Agent for a single niche. Useful for manual reruns."""
    from .database import init_db
    from .agents.chief import ChiefAgent

    init_db()
    if goals is None:
        goals = ["growth", "leads"]
    chief = ChiefAgent()
    return chief.run_week(week=week, niche_key=niche_key, business_goals=goals)
