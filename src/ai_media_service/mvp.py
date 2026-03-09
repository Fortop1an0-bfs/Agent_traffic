from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .models import SprintTask


@dataclass(frozen=True)
class MvpPhase:
    name: str
    weeks: List[int]
    goals: List[str]


def build_8_week_tasks() -> List[SprintTask]:
    return [
        SprintTask(1, "ChiefAgentOrchestrator", "Initialize workflow and role SLA", "SLA document approved"),
        SprintTask(1, "NicheAnalystAgent", "Validate pilot niche demand", "2 pilot niches confirmed"),
        SprintTask(2, "ContentStrategyAgent", "Deliver 4-week content calendar", "Calendar approved"),
        SprintTask(2, "WebsitePublisherAgent", "Launch site publishing routine", ">=90% on-time publishing"),
        SprintTask(3, "ShortsScriptAgent", "Produce short scripts for pilots", ">=3 videos/niche/week"),
        SprintTask(3, "VideoProducerAgent", "Activate 9:16 export workflow", "All 3 platforms receive assets"),
        SprintTask(4, "QABrandSafetyAgent", "Enforce quality and risk checks", ">=70% first-pass QA"),
        SprintTask(5, "GrowthMetricsAgent", "Build KPI dashboard", "Weekly report generated"),
        SprintTask(5, "GrowthMetricsAgent", "Run A/B test #1 (headline/hook)", "One winning variant selected"),
        SprintTask(6, "GrowthMetricsAgent", "Run A/B test #2 (CTA)", "CTA uplift recorded"),
        SprintTask(7, "ChiefAgentOrchestrator", "Scale from 2 to 5 niches", "No KPI degradation >10%"),
        SprintTask(8, "ChiefAgentOrchestrator", "Prepare rollout to 10 niches", "Scale readiness checklist passed"),
    ]


def build_mvp_phases() -> List[MvpPhase]:
    return [
        MvpPhase(
            name="Phase 1: Baseline",
            weeks=[1, 2],
            goals=[
                "Chief + 4 key agents live",
                "Two pilot niches activated",
                "Templates and QA checklist active",
            ],
        ),
        MvpPhase(
            name="Phase 2: Short-video loop",
            weeks=[3, 4],
            goals=[
                "Script + production loop online",
                ">=3 short videos per pilot niche weekly",
                "Subtitle and intro/outro automation",
            ],
        ),
        MvpPhase(
            name="Phase 3: KPI governance",
            weeks=[5, 6],
            goals=[
                "Weekly KPI dashboard",
                "Two A/B tests per week",
                "Decision loop active",
            ],
        ),
        MvpPhase(
            name="Phase 4: Scale gate",
            weeks=[7, 8],
            goals=[
                "Scale to 5 niches",
                "Publishing SLA remains >=90%",
                "Rollout playbook for 10 niches",
            ],
        ),
    ]


def scale_readiness_check(kpi_snapshot: Dict[str, float]) -> Dict[str, bool]:
    return {
        "publishing_sla_ok": kpi_snapshot.get("publishing_sla_pct", 0.0) >= 90.0,
        "cycle_time_ok": kpi_snapshot.get("cycle_time_hours", 999.0) <= 24.0,
        "qa_first_pass_ok": kpi_snapshot.get("qa_first_pass_pct", 0.0) >= 70.0,
        "growth_ok": kpi_snapshot.get("subscriber_growth_pct", 0.0) >= 10.0,
    }

