"""Quick smoke-test: checks Grok API, PostgreSQL and Redis connections."""
from __future__ import annotations

import sys
import os

# Allow running from project root without installing package
sys.path.insert(0, os.path.dirname(__file__))

from src.ai_media_service.logging_config import setup_logging

setup_logging()

import logging
log = logging.getLogger("test_grok")


def test_grok() -> None:
    from openai import OpenAI
    from src.ai_media_service.config import settings

    log.info("Testing Grok API (%s)...", settings.GROK_BASE_URL)
    client = OpenAI(api_key=settings.GROK_API_KEY, base_url=settings.GROK_BASE_URL)
    resp = client.chat.completions.create(
        model=settings.GROK_MODEL,
        messages=[{"role": "user", "content": "Reply with exactly: GROK_OK"}],
        max_tokens=10,
    )
    answer = resp.choices[0].message.content
    assert answer and "GROK" in answer.upper(), f"Unexpected response: {answer}"
    log.info("Grok API: OK — '%s'", answer)


def test_db() -> None:
    from sqlalchemy import text
    from src.ai_media_service.database import engine

    log.info("Testing PostgreSQL...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()")).scalar()
    log.info("PostgreSQL: OK — %s", result)


def test_redis() -> None:
    from src.ai_media_service.redis_client import get_redis

    log.info("Testing Redis...")
    r = get_redis()
    r.set("_smoke_test", "ok", ex=10)
    val = r.get("_smoke_test")
    assert val == "ok", f"Redis returned: {val}"
    log.info("Redis: OK")


if __name__ == "__main__":
    errors: list[str] = []

    for name, fn in [("Grok", test_grok), ("PostgreSQL", test_db), ("Redis", test_redis)]:
        try:
            fn()
        except Exception as exc:
            log.error("%s FAILED: %s", name, exc)
            errors.append(name)

    if errors:
        log.error("Failed services: %s", ", ".join(errors))
        sys.exit(1)
    else:
        log.info("All checks passed!")
