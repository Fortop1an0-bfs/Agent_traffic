from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class AgentRole:
    name: str
    purpose: str
    inputs: List[str]
    outputs: List[str]
    kpis: List[str]


@dataclass(frozen=True)
class Niche:
    key: str
    title: str
    focus_areas: List[str]


@dataclass
class ContentItem:
    niche_key: str
    source_idea: str
    website_article: str
    telegram_posts: List[str]
    short_video_scripts: List[str]
    qa_status: str = "pending"


@dataclass
class WeeklyMetrics:
    niche_key: str
    views: int
    retention_pct: float
    ctr_pct: float
    engagement_rate_pct: float
    subscribers_delta: int
    leads: int


@dataclass
class SprintTask:
    week: int
    owner_role: str
    description: str
    success_criteria: str


@dataclass
class WeeklyDecision:
    week: int
    niche_key: str
    keep_topics: List[str] = field(default_factory=list)
    cut_topics: List[str] = field(default_factory=list)
    test_hypotheses: List[str] = field(default_factory=list)
    notes: Dict[str, str] = field(default_factory=dict)

