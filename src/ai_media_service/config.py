from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ── Groq (ChiefAgent — orchestration + function calling) ──────────────────
    GROK_API_KEY: str = os.environ["GROK_API_KEY"]
    GROK_MODEL: str = os.getenv("GROK_MODEL", "llama-3.3-70b-versatile")
    GROK_BASE_URL: str = os.getenv("GROK_BASE_URL", "https://api.groq.com/openai/v1")

    # ── Google Gemini (sub-agents — content generation, FREE 1M tokens/day) ───
    # Ключ: https://aistudio.google.com/app/apikey
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_MODEL: str = os.getenv("GOOGLE_MODEL", "gemini-2.0-flash")
    GOOGLE_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # ── Mistral AI (резерв субагентов) ───────────────────────────────────────
    # Ключ: https://console.mistral.ai/
    MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")
    MISTRAL_MODEL: str = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
    MISTRAL_BASE_URL: str = "https://api.mistral.ai/v1"

    # ── OpenRouter (запасной провайдер, бесплатные модели) ────────────────────
    # Ключ: https://openrouter.ai/keys
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    DATABASE_URL: str = os.environ["DATABASE_URL"]
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ADMIN_CHAT_ID: str = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")

    # Отдельный канал на каждую нишу
    TELEGRAM_CHANNEL_AI_BUSINESS: str = os.getenv("TELEGRAM_CHANNEL_AI_BUSINESS", "")
    TELEGRAM_CHANNEL_PERSONAL_BRAND: str = os.getenv("TELEGRAM_CHANNEL_PERSONAL_BRAND", "")
    TELEGRAM_CHANNEL_FINANCE: str = os.getenv("TELEGRAM_CHANNEL_FINANCE", "")

    # Маппинг ниша → channel_id
    @property
    def niche_channels(self) -> dict[str, str]:
        return {
            "ai_business":    self.TELEGRAM_CHANNEL_AI_BUSINESS,
            "personal_brand": self.TELEGRAM_CHANNEL_PERSONAL_BRAND,
            "finance":        self.TELEGRAM_CHANNEL_FINANCE,
        }

    def channel_for(self, niche_key: str) -> str:
        return self.niche_channels.get(niche_key, "")


settings = Settings()
