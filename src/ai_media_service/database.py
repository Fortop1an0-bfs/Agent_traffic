from __future__ import annotations

import logging
import time

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .db_models import Base

log = logging.getLogger(__name__)

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def wait_for_db(retries: int = 15, delay: float = 2.0) -> None:
    """Block until PostgreSQL is reachable (important for Docker startup order)."""
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            log.info("PostgreSQL ready.")
            return
        except Exception as exc:
            log.warning("DB not ready (attempt %d/%d): %s", attempt, retries, exc)
            time.sleep(delay)
    raise RuntimeError("PostgreSQL did not become ready in time.")


def init_db() -> None:
    """Wait for DB, then create all tables."""
    wait_for_db()
    Base.metadata.create_all(engine)
    log.info("DB tables created/verified.")


def get_session() -> Session:
    return SessionLocal()
