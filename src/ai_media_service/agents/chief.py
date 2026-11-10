from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from typing import Any

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

log = logging.getLogger(__name__)

from ..config import settings
from ..database import get_session
from ..db_models import AgentTaskDB, ContentItemDB, WeeklyDecisionDB
from ..redis_client import cache_agent_result, enqueue_task, set_rate_limit_hit, set_rate_limit_ok
from .base import _parse_wait
from ..integrations.telegram_bot import notify_admin
from ..search import search_niche_news
from .sub_agents import (
    ContentGeneratorAgent,
    GrowthMetricsAgent,
    NicheAnalystAgent,
    QABrandSafetyAgent,
    SeoAgent,
    ContentStrategyAgent,
)

# ── Tool definitions for Grok function calling ─────────────────────────────────

CHIEF_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "analyze_niche_trends",
            "description": (
                "Delegate to NicheAnalystAgent: research trends, competitors, "
                "and audience demand for a specific niche."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "niche_key": {"type": "string", "description": "Niche identifier, e.g. ai_business"},
                    "focus_question": {"type": "string", "description": "Specific research question"},
                },
                "required": ["niche_key", "focus_question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_content_strategy",
            "description": (
                "Delegate to ContentStrategyAgent: build weekly content plan "
                "based on niche analysis insights."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "niche_key": {"type": "string"},
                    "insights": {"type": "string", "description": "Output from niche analysis"},
                    "week": {"type": "integer", "description": "Week number in the sprint"},
                },
                "required": ["niche_key", "insights", "week"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_content",
            "description": (
                "Delegate to ContentGeneratorAgent: generate article, Telegram posts, "
                "and short-video scripts for a given topic."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "niche_key": {"type": "string"},
                    "topic": {"type": "string", "description": "Тема контента на русском языке кириллицей, например: 'Как ИИ меняет малый бизнес в России'. ОБЯЗАТЕЛЬНО на кириллице, не транслит."},
                    "strategy_brief": {"type": "string", "description": "Context from content strategy"},
                },
                "required": ["niche_key", "topic", "strategy_brief"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_qa_review",
            "description": (
                "Delegate to QABrandSafetyAgent: review content for factual accuracy, "
                "brand safety, and quality before publishing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content_summary": {"type": "string", "description": "Content snippet to review"},
                    "content_type": {
                        "type": "string",
                        "enum": ["article", "telegram", "shorts"],
                    },
                },
                "required": ["content_summary", "content_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_metrics",
            "description": (
                "Delegate to GrowthMetricsAgent: analyze weekly KPIs and produce "
                "decisions for next week."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "niche_key": {"type": "string"},
                    "metrics_json": {
                        "type": "string",
                        "description": "JSON string with views, retention, CTR, engagement, subs, leads",
                    },
                    "week": {"type": "integer"},
                },
                "required": ["niche_key", "metrics_json", "week"],
            },
        },
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_duplicate_topic(session: Any, niche_key: str, topic: str) -> bool:
    """Return True if a similar topic was already generated in the last 7 days."""
    from datetime import timedelta
    if not topic:
        return False
    cutoff = datetime.utcnow() - timedelta(days=7)
    # Normalize: lowercase + strip
    topic_norm = topic.lower().strip()
    recent = (
        session.query(ContentItemDB)
        .filter(
            ContentItemDB.niche_key == niche_key,
            ContentItemDB.created_at >= cutoff,
        )
        .all()
    )
    for item in recent:
        existing = (item.source_idea or "").lower().strip()
        # Simple overlap check: if >60% of words match, consider duplicate
        words_new = set(topic_norm.split())
        words_old = set(existing.split())
        if not words_new:
            continue
        overlap = len(words_new & words_old) / len(words_new)
        if overlap > 0.6:
            log.info("Duplicate topic detected: '%s' ≈ '%s' (overlap=%.0f%%)", topic, item.source_idea, overlap * 100)
            return True
    return False


# ── Sub-agent dispatcher ───────────────────────────────────────────────────────

def _dispatch(tool_name: str, args: dict[str, Any], week: int) -> str:
    """Execute the sub-agent for a given tool call and persist the task in DB."""
    agent_map = {
        "analyze_niche_trends": NicheAnalystAgent,
        "create_content_strategy": ContentStrategyAgent,
        "generate_content": ContentGeneratorAgent,
        "run_qa_review": QABrandSafetyAgent,
        "analyze_metrics": GrowthMetricsAgent,
    }

    AgentClass = agent_map[tool_name]
    agent = AgentClass()

    # Build a natural-language task from args
    if tool_name == "generate_content":
        topic = args.get("topic", "")
        brief = args.get("strategy_brief", "")
        niche = args.get("niche_key", "")
        task = (
            f"Напиши контент для Telegram-канала по нише «{niche}».\n\n"
            f"ТЕМА: {topic}\n\n"
            f"БРИФ ОТ СТРАТЕГА:\n{brief}\n\n"
            "Создай все три блока согласно инструкции: ARTICLE, TELEGRAM, SHORTS."
        )
    else:
        task = json.dumps(args, ensure_ascii=False)

    # For niche analysis — enrich with live web search results
    extra_context = ""
    if tool_name == "analyze_niche_trends":
        niche_key = args.get("niche_key", "")
        focus = args.get("focus_question", "")
        extra_context = search_niche_news(niche_key, focus_question=focus)
        if extra_context:
            log.info("Tavily: инжектим веб-контекст для NicheAnalystAgent (%d chars)", len(extra_context))

    result = agent.run(task, extra_context=extra_context)

    # Persist in PostgreSQL
    with get_session() as session:
        db_task = AgentTaskDB(
            week=week,
            assigned_by="ChiefAgent",
            assigned_to=agent.name,
            task_description=task,
            result=result,
            status="completed",
            completed_at=datetime.utcnow(),
        )
        session.add(db_task)
        session.commit()
        session.refresh(db_task)
        cache_agent_result(db_task.id, result)

        # If content was generated, save it and notify admin for approval
        if tool_name == "generate_content":
            if _is_duplicate_topic(session, args.get("niche_key", ""), args.get("topic", "")):
                log.warning("generate_content: тема уже есть в БД за последние 7 дней, пропускаем")
                return "SKIPPED_DUPLICATE"
            _save_content_item(session, args, result)
            session.commit()  # commit content item
            # Fetch the new item's id to notify admin
            saved = (
                session.query(ContentItemDB)
                .filter_by(niche_key=args.get("niche_key", ""), source_idea=args.get("topic", ""))
                .order_by(ContentItemDB.id.desc())
                .first()
            )
            if saved:
                notify_admin(
                    content_id=saved.id,
                    niche_key=args.get("niche_key", ""),
                    topic=args.get("topic", ""),
                    preview=saved.website_article[:600],
                )

    log.info("[%s] done (%d chars)", agent.name, len(result))
    return result


def _save_content_item(session: Any, args: dict[str, Any], raw: str) -> None:
    """Parse content generator output and store as ContentItemDB."""
    article, telegram, shorts = "", [], []

    # Flexible split: handles === ARTICLE ===, ===ARTICLE===, == ARTICLE ==, etc.
    parts = re.split(r"={2,}\s*(ARTICLE|TELEGRAM|SHORTS)\s*=*", raw, flags=re.IGNORECASE)
    for i, part in enumerate(parts):
        tag = part.strip().upper()
        if tag == "ARTICLE" and i + 1 < len(parts):
            article = parts[i + 1].strip()
        elif tag == "TELEGRAM" and i + 1 < len(parts):
            raw_tg = parts[i + 1].strip()
            # Один большой пост — храним как список из одного элемента
            if raw_tg:
                telegram = [raw_tg]
        elif tag == "SHORTS" and i + 1 < len(parts):
            blocks = [b.strip() for b in parts[i + 1].strip().split("\n\n") if b.strip()]
            shorts = blocks

    if not telegram:
        log.warning("_save_content_item: секция TELEGRAM не найдена (%d chars raw)", len(raw))

    item = ContentItemDB(
        niche_key=args.get("niche_key", "unknown"),
        source_idea=args.get("topic", ""),
        website_article=article or raw,
        telegram_posts=telegram,
        short_video_scripts=shorts,
        qa_status="pending",
    )
    session.add(item)


# ── Chief Agent ────────────────────────────────────────────────────────────────

class ChiefAgent:
    """
    Chief agent: agentic loop с function calling.
    Провайдеры: Groq → Gemini → Mistral (мгновенный переход на 429, без sleep).
    Sleep только если все провайдеры исчерпаны.
    """

    # Цепочка провайдеров для ChiefAgent (все поддерживают function calling)
    _PROVIDER_CHAIN = [
        ("groq",    "GROK_API_KEY",    "GROK_BASE_URL",    "GROK_MODEL"),
        ("google",  "GOOGLE_API_KEY",  "GOOGLE_BASE_URL",  "GOOGLE_MODEL"),
        ("mistral", "MISTRAL_API_KEY", "MISTRAL_BASE_URL", "MISTRAL_MODEL"),
    ]

    SYSTEM_PROMPT = (
        "Ты ChiefAgentOrchestrator — главный координатор AI-медиасервиса для российского рынка. "
        "Цель: с нуля вырастить медиа-присутствие в нишах AI-инструменты, Личный бренд, Финансы. "
        "Платформы: Telegram-канал + сайт/блог (SEO) + Reels/Shorts/TikTok. "
        "Контент переиспользуется: одна идея → статья на сайт → посты в Telegram → сценарии Shorts. "
        "Монетизация — через всё что работает: партнёрки, реклама, инфопродукты, услуги. "
        "Язык всего контента: русский (кириллица). Аудитория: Россия и СНГ. "
        "ВАЖНО: все аргументы инструментов (topic, focus_question, insights и др.) пиши ТОЛЬКО кириллицей — никакого транслита и латиницы.\n\n"
        "Рабочий процесс на каждую нишу:\n"
        "1. analyze_niche_trends — понять рынок и боли аудитории прямо сейчас\n"
        "2. create_content_strategy — составить план из 4 тем на неделю\n"
        "3. generate_content — создать SEO-статью на сайт + Telegram-посты + сценарии Shorts\n"
        "4. run_qa_review — проверить контент перед публикацией\n"
        "5. analyze_metrics — если есть данные, проанализировать и дать рекомендации\n\n"
        "После всех tool_calls напиши краткое резюме на русском: что сделано, что ожидать, "
        "ключевой фокус следующей недели."
    )

    def __init__(self) -> None:
        # Собираем список провайдеров у которых есть ключ
        self._providers: list[tuple[str, str, str, str]] = []
        for pname, key_attr, url_attr, model_attr in self._PROVIDER_CHAIN:
            key = getattr(settings, key_attr, "")
            if key:
                self._providers.append((
                    pname, key,
                    getattr(settings, url_attr, ""),
                    getattr(settings, model_attr, ""),
                ))

    def _try_provider(
        self,
        provider_name: str,
        api_key: str,
        base_url: str,
        model: str,
        initial_messages: list[ChatCompletionMessageParam],
        week: int,
    ) -> str | None:
        """
        Запускает agentic loop с одним провайдером.
        Возвращает результат или None если провайдер вернул 429.
        """
        client = OpenAI(api_key=api_key, base_url=base_url)
        messages = list(initial_messages)  # копия, чтобы не мутировать оригинал

        for iteration in range(10):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=CHIEF_TOOLS,
                    tool_choice="auto",
                    max_tokens=2048,
                )
            except Exception as exc:
                exc_str = str(exc)
                if "rate_limit_exceeded" in exc_str or "429" in exc_str:
                    wait = _parse_wait(exc_str)
                    log.warning(
                        "ChiefAgent [%s] rate limit — переключаемся на следующий провайдер (ждать %ds)",
                        provider_name, wait,
                    )
                    set_rate_limit_hit("ChiefAgent", wait, exc_str, provider=provider_name)
                    return None  # сигнал: переключиться на следующий провайдер
                if "tool_use_failed" in exc_str or "failed_generation" in exc_str:
                    log.warning(
                        "ChiefAgent [%s] tool_call failure — переключаемся на следующий провайдер",
                        provider_name,
                    )
                    return None
                log.error("ChiefAgent [%s] ошибка на итерации %d: %s", provider_name, iteration, exc)
                raise

            assistant_msg = response.choices[0].message

            asst_dict: dict[str, Any] = {"role": "assistant", "content": assistant_msg.content or ""}
            if assistant_msg.tool_calls:
                asst_dict["tool_calls"] = [tc.model_dump() for tc in assistant_msg.tool_calls]
            messages.append(asst_dict)  # type: ignore[arg-type]

            if not assistant_msg.tool_calls:
                set_rate_limit_ok("ChiefAgent", provider=provider_name)
                if provider_name != self._providers[0][0]:
                    log.info("ChiefAgent использует фаллбек-провайдер: %s", provider_name)
                log.info("ChiefAgent loop завершён за %d итераций (%s)", iteration + 1, provider_name)
                return assistant_msg.content or "(no summary)"

            for tc in assistant_msg.tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments)
                log.info("→ delegating to %s(%s)", fn_name, list(fn_args.keys()))
                try:
                    result = _dispatch(fn_name, fn_args, week=week)
                except Exception as exc:
                    log.error("Sub-agent %s failed: %s", fn_name, exc)
                    result = f"ERROR: {exc}"
                messages.append({  # type: ignore[arg-type]
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result[:3000],
                })

        return "(chief loop limit reached)"

    def run_week(self, week: int, niche_key: str, business_goals: list[str]) -> str:
        log.info("Starting week %d for niche '%s'", week, niche_key)

        goal_text = ", ".join(business_goals)
        initial_messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"Week: {week}\nNiche: {niche_key}\nBusiness goals: {goal_text}\n\n"
                "Please coordinate all sub-agents to produce this week's content plan and assets."
            )},
        ]

        for attempt in range(5):
            for provider_name, api_key, base_url, model in self._providers:
                result = self._try_provider(
                    provider_name, api_key, base_url, model, initial_messages, week
                )
                if result is not None:
                    return result
                # rate limit — пробуем следующий провайдер

            # Все провайдеры исчерпаны — ждём сброса
            log.warning("ChiefAgent: все провайдеры в лимите, ждём 60с (попытка %d/5)...", attempt + 1)
            time.sleep(60)

        raise RuntimeError("ChiefAgent: все провайдеры исчерпали лимит после 5 попыток")
