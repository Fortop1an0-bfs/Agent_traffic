from __future__ import annotations

import re
import time
import logging

from openai import OpenAI

from ..config import settings
from ..redis_client import set_rate_limit_hit, set_rate_limit_ok

log = logging.getLogger(__name__)

# Цепочка фаллбека для субагентов: Google → Mistral → Groq
# Формат: (provider_name, api_key_attr, base_url_attr, model_attr)
_FALLBACK_CHAIN = [
    ("mistral",  "MISTRAL_API_KEY",  "MISTRAL_BASE_URL",  "MISTRAL_MODEL"),
    ("groq",     "GROK_API_KEY",     "GROK_BASE_URL",     "GROK_MODEL"),
]


def _parse_wait(exc_str: str) -> int:
    """Извлечь время ожидания из сообщения об ошибке 429."""
    m = re.search(r"try again in (\d+)m(\d+)", exc_str)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2)) + 5
    m2 = re.search(r"try again in ([\d.]+)s", exc_str)
    if m2:
        return int(float(m2.group(1))) + 5
    return 60


def _make_client(api_key_attr: str, base_url_attr: str) -> tuple[OpenAI, str, str] | None:
    """Создать OpenAI-клиент по именам атрибутов settings. Вернуть None если ключ пуст."""
    api_key = getattr(settings, api_key_attr, "")
    base_url = getattr(settings, base_url_attr, "")
    if not api_key:
        return None
    return OpenAI(api_key=api_key, base_url=base_url)


class BaseAgent:
    """Base class for all agents.

    Sub-classes set class variables to select their primary provider:
        _api_key_attr  — settings attribute name for the API key
        _base_url_attr — settings attribute name for the base URL
        _model_attr    — settings attribute name for the model name
        _provider_name — short name for Redis rate-limit keys

    Fallback chain on 429: primary → Mistral → Groq (no sleep, instant switch).
    Sleep-and-retry only if ALL providers in the chain are rate-limited.
    """

    name: str = "BaseAgent"
    system_prompt: str = "You are a helpful AI agent."

    # Subclasses override these to use a different primary provider
    _api_key_attr: str = "GROK_API_KEY"
    _base_url_attr: str = "GROK_BASE_URL"
    _model_attr: str = "GROK_MODEL"
    _provider_name: str = "groq"

    def __init__(self) -> None:
        primary_key = getattr(settings, self._api_key_attr, "")

        if not primary_key:
            # Primary key missing — fall straight to Groq
            self._primary = ("groq", settings.GROK_API_KEY, settings.GROK_BASE_URL, settings.GROK_MODEL)
        else:
            self._primary = (
                self._provider_name,
                primary_key,
                getattr(settings, self._base_url_attr, ""),
                getattr(settings, self._model_attr, ""),
            )

        # Build the ordered provider list: primary first, then fallbacks
        self._providers = [self._primary]
        for pname, key_attr, url_attr, model_attr in _FALLBACK_CHAIN:
            if pname == self._primary[0]:
                continue  # skip if already primary
            key = getattr(settings, key_attr, "")
            if key:
                self._providers.append((
                    pname, key,
                    getattr(settings, url_attr, ""),
                    getattr(settings, model_attr, ""),
                ))

    def run(self, task: str, extra_context: str = "") -> str:
        system = self.system_prompt
        if extra_context:
            system += f"\n\nAdditional context:\n{extra_context}"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": task},
        ]

        # Try each provider in order; on 429 move to next; sleep only as last resort
        for attempt in range(5):
            for provider_name, api_key, base_url, model in self._providers:
                client = OpenAI(api_key=api_key, base_url=base_url)
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        max_tokens=2048,
                        temperature=0.7,
                    )
                    set_rate_limit_ok(self.name, provider=provider_name)
                    if provider_name != self._primary[0]:
                        log.info("%s используется фаллбек-провайдер: %s", self.name, provider_name)
                    return response.choices[0].message.content or ""

                except Exception as exc:
                    exc_str = str(exc)
                    if "rate_limit_exceeded" in exc_str or "429" in exc_str:
                        wait = _parse_wait(exc_str)
                        log.warning(
                            "%s [%s] rate limit — переключаемся на следующий провайдер (ждать %ds)",
                            self.name, provider_name, wait,
                        )
                        set_rate_limit_hit(self.name, wait, exc_str, provider=provider_name)
                        # Не спим — просто переходим к следующему провайдеру
                        continue
                    raise

            # Все провайдеры исчерпаны в этом цикле — ждём сброса самого быстрого
            log.warning("%s все провайдеры заняты, ждём 60с (попытка %d/5)...", self.name, attempt + 1)
            time.sleep(60)

        raise RuntimeError(f"{self.name}: все провайдеры исчерпали лимит после 5 попыток")
