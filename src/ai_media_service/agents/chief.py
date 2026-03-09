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
from ..integrations.telegram_bot import notify_admin
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
    task = json.dumps(args, ensure_ascii=False)
    result = agent.run(task)

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

    sections = raw.split("===")
    for i, section in enumerate(sections):
        tag = section.strip().upper()
        if tag == "ARTICLE" and i + 1 < len(sections):
            article = sections[i + 1].strip()
        elif tag == "TELEGRAM" and i + 1 < len(sections):
            blocks = [b.strip() for b in sections[i + 1].strip().split("\n\n") if b.strip()]
            telegram = blocks
        elif tag == "SHORTS" and i + 1 < len(sections):
            blocks = [b.strip() for b in sections[i + 1].strip().split("\n\n") if b.strip()]
            shorts = blocks

    item = ContentItemDB(
        niche_key=args.get("niche_key", "unknown"),
        source_idea=args.get("topic", ""),
        website_article=article or raw,
        telegram_posts=telegram or [raw[:200]],
        short_video_scripts=shorts or [raw[:200]],
        qa_status="pending",
    )
    session.add(item)


# ── Chief Agent ────────────────────────────────────────────────────────────────

class ChiefAgent:
    """
    Chief agent that uses Grok function-calling to delegate work to sub-agents.
    Runs an agentic loop: plan → delegate → collect → synthesize.
    """

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
        self.client = OpenAI(
            api_key=settings.GROK_API_KEY,
            base_url=settings.GROK_BASE_URL,
        )

    def run_week(self, week: int, niche_key: str, business_goals: list[str]) -> str:
        """
        Main agentic loop.
        Sends task to Grok → gets tool_calls → dispatches sub-agents → loops back.
        """
        log.info("Starting week %d for niche '%s'", week, niche_key)

        goal_text = ", ".join(business_goals)
        user_message = (
            f"Week: {week}\n"
            f"Niche: {niche_key}\n"
            f"Business goals: {goal_text}\n\n"
            "Please coordinate all sub-agents to produce this week's content plan and assets."
        )

        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        # Agentic loop: keep calling until no more tool_calls
        for iteration in range(10):  # safety cap
            try:
                response = self.client.chat.completions.create(
                    model=settings.GROK_MODEL,
                    messages=messages,
                    tools=CHIEF_TOOLS,
                    tool_choice="auto",
                    parallel_tool_calls=False,
                    max_tokens=2048,
                )
            except Exception as exc:
                exc_str = str(exc)
                # Auto-retry on rate limit
                if "rate_limit_exceeded" in exc_str or "429" in exc_str:
                    wait = 60  # default
                    m = re.search(r"try again in (\d+)m(\d+)", exc_str)
                    if m:
                        wait = int(m.group(1)) * 60 + int(m.group(2)) + 5
                    else:
                        m2 = re.search(r"try again in ([\d.]+)s", exc_str)
                        if m2:
                            wait = int(float(m2.group(1))) + 5
                    log.warning("Rate limit — sleeping %ds before retry...", wait)
                    set_rate_limit_hit("ChiefAgent", wait, exc_str)
                    time.sleep(wait)
                    set_rate_limit_ok("ChiefAgent")
                    continue  # retry same iteration
                log.error("Chief API call failed at iteration %d: %s", iteration, exc)
                break

            assistant_msg = response.choices[0].message

            # Build assistant dict preserving tool_calls correctly
            asst_dict: dict[str, Any] = {"role": "assistant", "content": assistant_msg.content or ""}
            if assistant_msg.tool_calls:
                asst_dict["tool_calls"] = [tc.model_dump() for tc in assistant_msg.tool_calls]
            messages.append(asst_dict)  # type: ignore[arg-type]

            # No more tool calls → final answer
            if not assistant_msg.tool_calls:
                log.info("Loop finished after %d iteration(s)", iteration + 1)
                return assistant_msg.content or "(no summary)"

            # Dispatch each tool call
            for tc in assistant_msg.tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments)
                log.info("→ delegating to %s(%s)", fn_name, list(fn_args.keys()))

                try:
                    result = _dispatch(fn_name, fn_args, week=week)
                except Exception as exc:
                    log.error("Sub-agent %s failed: %s", fn_name, exc)
                    result = f"ERROR: {exc}"

                # Feed result back as tool message
                messages.append({  # type: ignore[arg-type]
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result[:3000],  # trim if huge
                })

        return "(chief loop limit reached)"
