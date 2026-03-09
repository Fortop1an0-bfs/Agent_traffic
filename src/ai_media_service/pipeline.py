from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .models import ContentItem


@dataclass(frozen=True)
class TemplatePack:
    website_template: str
    telegram_template: str
    short_script_template: str


def default_template_pack() -> TemplatePack:
    return TemplatePack(
        website_template=(
            "Title: {title}\n\n"
            "Problem\n{problem}\n\n"
            "Solution\n{solution}\n\n"
            "Checklist\n{checklist}\n\n"
            "CTA\n{cta}"
        ),
        telegram_template="[{hook}] {insight} | CTA: {cta}",
        short_script_template=(
            "Hook: {hook}\n"
            "Body: {body}\n"
            "Action: {cta}\n"
            "Duration: 15-45 sec"
        ),
    )


def repurpose_idea(niche_key: str, idea: str, templates: TemplatePack | None = None) -> ContentItem:
    templates = templates or default_template_pack()
    website_article = templates.website_template.format(
        title=f"{idea} - practical guide",
        problem=f"Why {idea} fails in real practice.",
        solution=f"Three-step framework to apply {idea}.",
        checklist=f"- Audit current state\n- Run small experiment\n- Measure weekly",
        cta="Subscribe for weekly playbooks.",
    )
    telegram_posts = [
        templates.telegram_template.format(
            hook="Quick insight",
            insight=f"{idea}: top mistake and fix in 30 seconds.",
            cta="Read the full guide on site.",
        ),
        templates.telegram_template.format(
            hook="Case",
            insight=f"Mini case: applying {idea} with measurable result.",
            cta="Vote in poll: want template?",
        ),
        templates.telegram_template.format(
            hook="Checklist",
            insight=f"3-point checklist to implement {idea} today.",
            cta="Save and share.",
        ),
    ]
    short_video_scripts = [
        templates.short_script_template.format(
            hook=f"Stop doing this with {idea}",
            body="One mistake, one fix, one proof.",
            cta="Comment for full template.",
        ),
        templates.short_script_template.format(
            hook=f"{idea} in 20 seconds",
            body="Simple framework anyone can test this week.",
            cta="Follow for next part.",
        ),
        templates.short_script_template.format(
            hook=f"Myth vs reality: {idea}",
            body="Common myth broken with practical example.",
            cta="Watch full guide in bio.",
        ),
    ]
    return ContentItem(
        niche_key=niche_key,
        source_idea=idea,
        website_article=website_article,
        telegram_posts=telegram_posts,
        short_video_scripts=short_video_scripts,
    )


def qa_check_content(item: ContentItem) -> Dict[str, str]:
    checks: Dict[str, str] = {
        "website_length": "pass" if len(item.website_article) > 200 else "fail",
        "telegram_count": "pass" if len(item.telegram_posts) >= 3 else "fail",
        "shorts_count": "pass" if len(item.short_video_scripts) >= 3 else "fail",
        "contains_cta": "pass"
        if "CTA" in item.website_article and any("CTA:" in p for p in item.telegram_posts)
        else "fail",
    }
    item.qa_status = "pass" if all(v == "pass" for v in checks.values()) else "fail"
    return checks


def build_weekly_content_batch(niche_key: str, ideas: List[str]) -> List[ContentItem]:
    batch = [repurpose_idea(niche_key=niche_key, idea=idea) for idea in ideas]
    for item in batch:
        qa_check_content(item)
    return batch

