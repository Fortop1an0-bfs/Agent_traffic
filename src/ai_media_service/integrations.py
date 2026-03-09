from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .models import ContentItem


@dataclass
class PublishResult:
    platform: str
    status: str
    message: str


class WebsiteCMSAdapter:
    def publish(self, item: ContentItem) -> PublishResult:
        return PublishResult(
            platform="website",
            status="ok" if item.qa_status == "pass" else "blocked",
            message=f"Article for {item.niche_key} processed.",
        )


class TelegramAdapter:
    def publish(self, item: ContentItem) -> PublishResult:
        return PublishResult(
            platform="telegram",
            status="ok" if item.qa_status == "pass" else "blocked",
            message=f"{len(item.telegram_posts)} posts scheduled.",
        )


class ShortsAdapter:
    def publish_all(self, item: ContentItem) -> List[PublishResult]:
        status = "ok" if item.qa_status == "pass" else "blocked"
        return [
            PublishResult("tiktok", status, "Vertical export queued."),
            PublishResult("reels", status, "Vertical export queued."),
            PublishResult("shorts", status, "Vertical export queued."),
        ]

