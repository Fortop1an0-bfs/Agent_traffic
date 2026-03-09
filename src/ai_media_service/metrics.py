from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Dict, List

from .models import WeeklyDecision, WeeklyMetrics


@dataclass
class MetricsCollector:
    records: List[WeeklyMetrics] = field(default_factory=list)

    def add(self, metric: WeeklyMetrics) -> None:
        self.records.append(metric)

    def by_niche(self, niche_key: str) -> List[WeeklyMetrics]:
        return [m for m in self.records if m.niche_key == niche_key]


def build_weekly_dashboard(metrics: List[WeeklyMetrics]) -> Dict[str, float]:
    if not metrics:
        return {}
    return {
        "total_views": float(sum(m.views for m in metrics)),
        "avg_retention_pct": round(mean(m.retention_pct for m in metrics), 2),
        "avg_ctr_pct": round(mean(m.ctr_pct for m in metrics), 2),
        "avg_engagement_rate_pct": round(mean(m.engagement_rate_pct for m in metrics), 2),
        "subscribers_delta": float(sum(m.subscribers_delta for m in metrics)),
        "total_leads": float(sum(m.leads for m in metrics)),
    }


def weekly_decision_loop(week: int, niche_key: str, dashboard: Dict[str, float]) -> WeeklyDecision:
    decision = WeeklyDecision(week=week, niche_key=niche_key)
    if dashboard.get("avg_retention_pct", 0.0) >= 35.0:
        decision.keep_topics.append("How-to formats with practical steps")
    else:
        decision.cut_topics.append("Long intros without immediate hook")

    if dashboard.get("avg_ctr_pct", 0.0) < 2.0:
        decision.test_hypotheses.append("Test stronger promise in first line/title")
    else:
        decision.keep_topics.append("Current title promise style")

    if dashboard.get("avg_engagement_rate_pct", 0.0) < 5.0:
        decision.test_hypotheses.append("Add binary poll CTA in Telegram")

    decision.notes["summary"] = "Use next week content plan adjustments from hypotheses."
    return decision

