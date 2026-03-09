from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class WeeklyContentPlan:
    week: int
    website_articles: int
    website_guides: int
    telegram_posts_per_day: str
    short_videos: int
    ab_tests: List[str]
    core_theme: str


def build_4_week_strategy(pilot_niches: List[str]) -> Dict[str, List[WeeklyContentPlan]]:
    strategy: Dict[str, List[WeeklyContentPlan]] = {}
    for niche in pilot_niches:
        strategy[niche] = [
            WeeklyContentPlan(
                week=1,
                website_articles=2,
                website_guides=1,
                telegram_posts_per_day="1-2",
                short_videos=3,
                ab_tests=["headline_style"],
                core_theme="Pain points and beginner mistakes",
            ),
            WeeklyContentPlan(
                week=2,
                website_articles=2,
                website_guides=1,
                telegram_posts_per_day="1-2",
                short_videos=4,
                ab_tests=["hook_length"],
                core_theme="Frameworks and quick wins",
            ),
            WeeklyContentPlan(
                week=3,
                website_articles=2,
                website_guides=1,
                telegram_posts_per_day="2",
                short_videos=5,
                ab_tests=["cta_variants"],
                core_theme="Case studies and social proof",
            ),
            WeeklyContentPlan(
                week=4,
                website_articles=2,
                website_guides=1,
                telegram_posts_per_day="2",
                short_videos=5,
                ab_tests=["thumbnail_promises"],
                core_theme="Myths vs reality and objections",
            ),
        ]
    return strategy

