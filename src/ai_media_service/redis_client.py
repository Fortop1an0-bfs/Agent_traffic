from __future__ import annotations

import json
from typing import Any

import redis

from .config import settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


# ── Task queue ────────────────────────────────────────────────────────────────

TASK_QUEUE = "agent:task_queue"


def enqueue_task(task: dict[str, Any]) -> None:
    get_redis().rpush(TASK_QUEUE, json.dumps(task))


def dequeue_task() -> dict[str, Any] | None:
    raw = get_redis().lpop(TASK_QUEUE)
    return json.loads(raw) if raw else None


# ── Dashboard cache ───────────────────────────────────────────────────────────

DASHBOARD_KEY = "agent:dashboard"
DASHBOARD_TTL = 3600  # 1 hour


def cache_dashboard(data: dict[str, Any]) -> None:
    get_redis().set(DASHBOARD_KEY, json.dumps(data), ex=DASHBOARD_TTL)


def get_cached_dashboard() -> dict[str, Any] | None:
    raw = get_redis().get(DASHBOARD_KEY)
    return json.loads(raw) if raw else None


# ── Agent result cache ────────────────────────────────────────────────────────

def cache_agent_result(task_id: int, result: str, ttl: int = 86400) -> None:
    get_redis().set(f"agent:result:{task_id}", result, ex=ttl)


def get_agent_result(task_id: int) -> str | None:
    return get_redis().get(f"agent:result:{task_id}")


# ── API rate-limit state (per-provider) ───────────────────────────────────────

_RL_KEY = "api:rate_limit:{provider}"
_PROVIDERS = ["groq", "google", "mistral", "openrouter"]


def _rl_key(provider: str) -> str:
    return _RL_KEY.format(provider=provider)


def set_rate_limit_hit(agent_name: str, wait_seconds: int, raw_error: str, provider: str = "groq") -> None:
    """Called on 429. Stores per-provider state with auto-expiry."""
    import time as _t
    data = {
        "status": "limited",
        "provider": provider,
        "agent": agent_name,
        "wait_seconds": wait_seconds,
        "reset_at": int(_t.time()) + wait_seconds,
        "triggered_at": int(_t.time()),
        "error": raw_error[:300],
    }
    get_redis().set(_rl_key(provider), json.dumps(data), ex=wait_seconds + 60)


def set_rate_limit_ok(agent_name: str, provider: str = "groq") -> None:
    """Called on successful call. Marks provider as available."""
    import time as _t
    # Don't overwrite a fresh "limited" state set by another concurrent agent
    existing_raw = get_redis().get(_rl_key(provider))
    if existing_raw:
        existing = json.loads(existing_raw)
        if existing.get("status") == "limited":
            return
    data = {
        "status": "ok",
        "provider": provider,
        "agent": agent_name,
        "reset_at": 0,
        "wait_seconds": 0,
        "triggered_at": int(_t.time()),
        "error": "",
    }
    get_redis().set(_rl_key(provider), json.dumps(data), ex=3600)


def get_rate_limit_status(provider: str = "groq") -> dict:
    raw = get_redis().get(_rl_key(provider))
    if raw:
        return json.loads(raw)
    return {"status": "unknown", "provider": provider, "agent": "", "reset_at": 0, "wait_seconds": 0, "error": ""}


def get_all_rate_limits() -> dict[str, dict]:
    """Return status for all tracked providers."""
    return {p: get_rate_limit_status(p) for p in _PROVIDERS}
