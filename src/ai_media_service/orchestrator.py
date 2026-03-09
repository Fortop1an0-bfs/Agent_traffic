from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .integrations import ShortsAdapter, TelegramAdapter, WebsiteCMSAdapter
from .models import ContentItem
from .niches import build_niche_catalog, choose_pilot_niches
from .pipeline import build_weekly_content_batch
from .roles import build_agent_roles
from .strategy import WeeklyContentPlan, build_4_week_strategy


@dataclass
class ChiefAgentOrchestrator:
    business_goals: List[str]
    roles: Dict[str, object] = field(default_factory=build_agent_roles)
    niches: Dict[str, object] = field(default_factory=build_niche_catalog)
    pilot_niches: List[str] = field(default_factory=choose_pilot_niches)
    strategy: Dict[str, List[WeeklyContentPlan]] = field(init=False)

    def __post_init__(self) -> None:
        self.strategy = build_4_week_strategy(self.pilot_niches)
        self.website = WebsiteCMSAdapter()
        self.telegram = TelegramAdapter()
        self.shorts = ShortsAdapter()

    def assign_weekly_tasks(self, week: int) -> Dict[str, List[str]]:
        return {
            "NicheAnalystAgent": [f"Validate trends for week {week}"],
            "ContentStrategyAgent": [f"Finalize calendar for week {week}"],
            "WebsitePublisherAgent": ["Publish 2 articles + 1 guide per niche"],
            "TelegramEditorAgent": ["Publish 1-2 posts/day per niche"],
            "ShortsScriptAgent": ["Prepare scripts for weekly short-video quota"],
            "VideoProducerAgent": ["Render and export 9:16 videos"],
            "QABrandSafetyAgent": ["Approve all assets before publication"],
            "GrowthMetricsAgent": ["Collect KPIs and propose two tests"],
        }

    def execute_week(self, week: int) -> Dict[str, List[str]]:
        logs: Dict[str, List[str]] = {}
        for niche_key in self.pilot_niches:
            plan = self.strategy[niche_key][week - 1]
            ideas = [
                f"{niche_key} theme {week}-{i}" for i in range(1, plan.website_articles + 2)
            ]
            batch: List[ContentItem] = build_weekly_content_batch(niche_key=niche_key, ideas=ideas)
            logs[niche_key] = []
            for item in batch:
                web_res = self.website.publish(item)
                tg_res = self.telegram.publish(item)
                short_res = self.shorts.publish_all(item)
                logs[niche_key].append(
                    f"{web_res.platform}:{web_res.status}, "
                    f"{tg_res.platform}:{tg_res.status}, "
                    f"{'/'.join([r.platform + ':' + r.status for r in short_res])}"
                )
        return logs

