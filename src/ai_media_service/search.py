"""
Tavily web search utility for NicheAnalystAgent.

Searches for recent news/articles in a niche and returns formatted context
that gets injected into NicheAnalystAgent's prompt.

Free tier: 1000 requests/month → https://app.tavily.com
If TAVILY_API_KEY is not set, returns "" and the agent runs without search context.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

# Russian search queries per niche key
_NICHE_QUERIES: dict[str, str] = {
    "ai_business":    "нейросети ИИ автоматизация бизнес Россия 2025 2026 кейсы инструменты",
    "personal_brand": "личный бренд Telegram монетизация блогер аудитория рост 2025",
    "finance":        "личные финансы инвестиции накопления вклады Россия 2025 2026",
    "career":         "карьера работа рынок труда Россия 2025 смена профессии",
    "habits":         "привычки продуктивность психология поведение саморазвитие",
    "education":      "онлайн образование курсы навыки Россия 2025",
}


def search_niche_news(niche_key: str, focus_question: str = "", max_results: int = 5) -> str:
    """
    Search recent news for a niche using Tavily.
    Returns a formatted string ready to inject as extra_context into an agent prompt.
    Returns "" if Tavily is not configured or request fails.
    """
    try:
        from tavily import TavilyClient  # type: ignore[import]
        from .config import settings

        api_key = settings.TAVILY_API_KEY
        if not api_key:
            log.debug("TAVILY_API_KEY не задан — пропускаем веб-поиск")
            return ""

        base_query = _NICHE_QUERIES.get(niche_key, niche_key)
        query = f"{base_query} {focus_question}".strip() if focus_question else base_query

        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
            include_answer=True,
        )

        results: list[dict] = response.get("results", [])
        if not results:
            log.info("Tavily: нет результатов для '%s'", query)
            return ""

        lines = [
            "=== АКТУАЛЬНЫЕ ДАННЫЕ ИЗ ИНТЕРНЕТА ===",
            "Используй эти материалы для конкретики — реальные факты, цифры, события:",
        ]

        answer = response.get("answer", "")
        if answer:
            lines.append(f"\n📌 Краткий ответ: {answer}")

        for r in results:
            title = r.get("title", "без заголовка")
            content = (r.get("content") or "")[:350].strip()
            url = r.get("url", "")
            published = r.get("published_date", "")
            date_str = f" [{published}]" if published else ""
            lines.append(f"\n— {title}{date_str}\n  {content}\n  Источник: {url}")

        lines.append("\n=== КОНЕЦ АКТУАЛЬНЫХ ДАННЫХ ===")
        result_str = "\n".join(lines)
        log.info("Tavily: получено %d результатов для ниши '%s'", len(results), niche_key)
        return result_str

    except Exception as exc:
        log.warning("Tavily search failed for niche '%s': %s", niche_key, exc)
        return ""
