from __future__ import annotations

import logging
import sys

from .logging_config import setup_logging
from .database import init_db
from .agents.chief import ChiefAgent
from .niches import build_niche_catalog, choose_pilot_niches
from .redis_client import get_redis

log = logging.getLogger(__name__)


def main() -> None:
    setup_logging()
    log.info("=== AI Media Service starting ===")

    log.info("Initializing DB...")
    init_db()

    log.info("Checking Redis...")
    try:
        get_redis().ping()
        log.info("Redis: OK")
    except Exception as e:
        log.warning("Redis unavailable: %s — continuing without cache", e)

    catalog = build_niche_catalog()
    pilots = choose_pilot_niches()
    goals = [
        "рост подписчиков с нуля",
        "высокий охват и вовлечённость",
        "монетизация через партнёрки, рекламу и инфопродукты",
        "узнаваемость в нише",
    ]
    week = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    log.info("Pilot niches: %s | Week: %d | Goals: %s", pilots, week, goals)

    chief = ChiefAgent()
    results: dict[str, str] = {}

    for niche_key in pilots:
        log.info("=" * 60)
        log.info("Niche: %s (%s)", catalog[niche_key].title, niche_key)
        log.info("=" * 60)
        summary = chief.run_week(week=week, niche_key=niche_key, business_goals=goals)
        results[niche_key] = summary

    log.info("\n=== CHIEF AGENT WEEKLY SUMMARIES ===")
    for niche_key, summary in results.items():
        log.info("\n--- %s ---\n%s", niche_key, summary)


if __name__ == "__main__":
    main()
