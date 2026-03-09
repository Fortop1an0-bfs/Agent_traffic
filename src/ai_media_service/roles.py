from __future__ import annotations

from typing import Dict

from .models import AgentRole


def build_agent_roles() -> Dict[str, AgentRole]:
    """Fixed role catalog with clear IO and KPIs."""
    roles = [
        AgentRole(
            name="ChiefAgentOrchestrator",
            purpose="Set priorities, assign work, enforce deadlines and quality gates.",
            inputs=[
                "business_goals",
                "weekly_metrics",
                "risk_flags",
                "content_backlog",
            ],
            outputs=[
                "weekly_tasks",
                "priority_matrix",
                "approval_or_rework_decisions",
            ],
            kpis=["schedule_reliability_pct", "qa_pass_rate_pct", "cycle_time_hours"],
        ),
        AgentRole(
            name="NicheAnalystAgent",
            purpose="Track trends, competitors, and audience demand in each niche.",
            inputs=["niche_catalog", "search_signals", "platform_trends"],
            outputs=["insight_briefs", "topic_opportunities", "risk_notes"],
            kpis=["insight_hit_rate_pct", "trend_to_publish_hours"],
        ),
        AgentRole(
            name="ContentStrategyAgent",
            purpose="Create rubrics, tone, and calendar from insights.",
            inputs=["insight_briefs", "brand_voice", "monthly_targets"],
            outputs=["content_calendar", "rubric_map", "weekly_objectives"],
            kpis=["calendar_fulfillment_pct", "topic_conversion_to_publish_pct"],
        ),
        AgentRole(
            name="SeoAgent",
            purpose="Build semantic clusters and optimize article structure.",
            inputs=["keyword_sets", "content_briefs", "site_taxonomy"],
            outputs=["seo_briefs", "internal_link_plan", "metadata"],
            kpis=["organic_clicks_growth_pct", "avg_position_improvement"],
        ),
        AgentRole(
            name="WebsitePublisherAgent",
            purpose="Publish and update website pages and long-form content.",
            inputs=["seo_briefs", "draft_articles", "publishing_slots"],
            outputs=["published_articles", "update_log"],
            kpis=["publish_on_time_pct", "article_quality_score"],
        ),
        AgentRole(
            name="TelegramEditorAgent",
            purpose="Adapt core ideas into high-frequency Telegram formats.",
            inputs=["core_messages", "topic_briefs", "community_feedback"],
            outputs=["telegram_posts", "polls", "cta_sequences"],
            kpis=["post_er_pct", "click_to_site_pct", "reply_rate_pct"],
        ),
        AgentRole(
            name="ShortsScriptAgent",
            purpose="Produce hooks and scripts for 15-45 second videos.",
            inputs=["core_messages", "trend_hooks", "platform_constraints"],
            outputs=["short_scripts", "hook_variants", "cta_variants"],
            kpis=["hook_hold_3s_pct", "script_to_publish_pct"],
        ),
        AgentRole(
            name="VideoProducerAgent",
            purpose="Create vertical videos with subtitles and platform exports.",
            inputs=["short_scripts", "visual_assets", "voice_profiles"],
            outputs=["tiktok_cut", "reels_cut", "shorts_cut"],
            kpis=["video_turnaround_hours", "avg_watch_time_sec"],
        ),
        AgentRole(
            name="CreativeDesignerAgent",
            purpose="Create covers, templates, and reusable brand visuals.",
            inputs=["brand_system", "storyboards", "campaign_themes"],
            outputs=["thumbnail_pack", "visual_templates", "style_updates"],
            kpis=["creative_reuse_rate_pct", "thumbnail_ctr_lift_pct"],
        ),
        AgentRole(
            name="CommunityModeratorAgent",
            purpose="Handle comments, FAQ, and sentiment-sensitive responses.",
            inputs=["incoming_comments", "response_guidelines", "risk_policy"],
            outputs=["moderation_actions", "faq_updates", "sentiment_summary"],
            kpis=["first_response_time_min", "negative_escalation_rate_pct"],
        ),
        AgentRole(
            name="QABrandSafetyAgent",
            purpose="Run fact checks and legal/brand checks before publishing.",
            inputs=["draft_assets", "policy_rules", "claim_sources"],
            outputs=["qa_report", "approve_or_block", "required_fixes"],
            kpis=["first_pass_rate_pct", "policy_violation_rate_pct"],
        ),
        AgentRole(
            name="GrowthMetricsAgent",
            purpose="Measure outcomes and suggest weekly experiments.",
            inputs=["platform_metrics", "content_metadata", "test_registry"],
            outputs=["kpi_dashboard", "experiment_plan", "weekly_decisions"],
            kpis=["experiment_win_rate_pct", "subscriber_growth_pct"],
        ),
    ]
    return {role.name: role for role in roles}

