"""
Celery app + tasks.

Worker start:
    celery -A src.ai_media_service.worker worker --loglevel=info

Beat scheduler:
    celery -A src.ai_media_service.worker beat --loglevel=info

Schedule:
  - Пн-Пт 08:30 — generate_daily_content (одна ниша в день по ротации)
  - Ежедневно 10:00, 15:00, 19:00 — publish_next_post (публикует следующий одобренный пост)
  - Понедельник 07:00 — run_weekly_content (полный недельный прогон всех ниш)
"""
from __future__ import annotations

import logging
from datetime import datetime

from celery import Celery
from celery.schedules import crontab

from .config import settings
from .logging_config import setup_logging

setup_logging()
log = logging.getLogger(__name__)

# Ротация ниш по дням недели (0=пн, 1=вт, 2=ср, 3=чт, 4=пт, 5=сб, 6=вс)
_NICHE_BY_WEEKDAY = {
    0: "ai_business",
    1: "personal_brand",
    2: "finance",
    3: "ai_business",
    4: "personal_brand",
    5: "finance",
    6: "ai_business",
}

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
    beat_schedule={
        # Генерация контента: пн-пт 08:30 (одна ниша в день)
        "daily-content-generation": {
            "task": "src.ai_media_service.worker.generate_daily_content",
            "schedule": crontab(hour=8, minute=30, day_of_week="1-5"),
            "args": [],
        },
        # Публикация: три слота в день
        "publish-morning": {
            "task": "src.ai_media_service.worker.publish_next_post",
            "schedule": crontab(hour=10, minute=0),
            "args": [],
        },
        "publish-afternoon": {
            "task": "src.ai_media_service.worker.publish_next_post",
            "schedule": crontab(hour=15, minute=0),
            "args": [],
        },
        "publish-evening": {
            "task": "src.ai_media_service.worker.publish_next_post",
            "schedule": crontab(hour=19, minute=0),
            "args": [],
        },
        # Полный недельный прогон: понедельник 07:00
        "weekly-full-run": {
            "task": "src.ai_media_service.worker.run_weekly_content",
            "schedule": crontab(hour=7, minute=0, day_of_week="monday"),
            "args": [],
        },
    },
)


@app.task(bind=True, max_retries=3, default_retry_delay=300)
def generate_daily_content(self) -> dict[str, str]:  # type: ignore[type-arg]
    """
    Ежедневная генерация контента для одной ниши (по ротации).
    Запускается автоматически пн-пт 08:30 или вручную:
        celery -A src.ai_media_service.worker call generate_daily_content
    """
    from .database import init_db
    from .agents.chief import ChiefAgent
    from .redis_client import get_redis

    init_db()

    weekday = datetime.now().weekday()
    niche_key = _NICHE_BY_WEEKDAY.get(weekday, "ai_business")

    r = get_redis()
    run_num = int(r.incr(f"agent:daily_run:{niche_key}"))

    goals = [
        "рост подписчиков с нуля",
        "высокий охват и вовлечённость",
        "монетизация через партнёрки и рекламу",
    ]

    log.info("Daily content generation: niche=%s run=%d", niche_key, run_num)
    chief = ChiefAgent()
    try:
        summary = chief.run_week(week=run_num, niche_key=niche_key, business_goals=goals)
        log.info("Daily generation done for niche=%s", niche_key)
        return {niche_key: summary}
    except Exception as exc:
        log.error("Daily generation failed for niche=%s: %s", niche_key, exc)
        self.retry(exc=exc)


@app.task
def publish_next_post() -> str:
    """
    Публикует следующий одобренный и ещё не опубликованный пост из БД.
    Запускается 3 раза в день (10:00, 15:00, 19:00) или вручную.
    """
    from .database import init_db, get_session
    from .db_models import ContentItemDB
    from .integrations.telegram_bot import publish_to_channel

    init_db()

    with get_session() as session:
        item = (
            session.query(ContentItemDB)
            .filter(
                ContentItemDB.qa_status == "approved",
                ContentItemDB.published_at.is_(None),
            )
            .order_by(ContentItemDB.created_at.asc())
            .first()
        )
        if not item:
            log.info("publish_next_post: нет одобренных постов для публикации")
            return "no_approved_posts"
        content_id = item.id
        niche_key = item.niche_key

    posted = publish_to_channel(content_id)
    if posted:
        log.info("publish_next_post: опубликован content_id=%d (ниша=%s)", content_id, niche_key)
        return f"published:{content_id}"
    else:
        log.warning("publish_next_post: не удалось опубликовать content_id=%d", content_id)
        return f"failed:{content_id}"


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_weekly_content(self, week: int | None = None) -> dict[str, str]:  # type: ignore[type-arg]
    """
    Полный недельный прогон: ChiefAgent генерирует контент для всех ниш.
    Запускается автоматически каждый понедельник 07:00 или вручную:
        celery -A src.ai_media_service.worker call run_weekly_content
    """
    from .database import init_db
    from .agents.chief import ChiefAgent
    from .niches import build_niche_catalog, choose_pilot_niches
    from .redis_client import get_redis

    init_db()

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
        log.info("Weekly run: week=%d niche='%s' (%s)", week, niche_key, catalog[niche_key].title)
        try:
            summary = chief.run_week(week=week, niche_key=niche_key, business_goals=goals)
            results[niche_key] = summary
        except Exception as exc:
            log.error("Niche %s failed: %s", niche_key, exc)
            self.retry(exc=exc)

    log.info("Weekly run complete: week=%d niches=%s", week, list(results.keys()))
    return results


@app.task
def run_single_niche(niche_key: str, week: int, goals: list[str] | None = None) -> str:
    """Run Chief Agent for a single niche. Useful for manual reruns."""
    from .database import init_db
    from .agents.chief import ChiefAgent

    init_db()
    if goals is None:
        goals = ["рост подписчиков", "вовлечённость"]
    chief = ChiefAgent()
    return chief.run_week(week=week, niche_key=niche_key, business_goals=goals)
