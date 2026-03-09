from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class NicheDB(Base):
    __tablename__ = "niches"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    focus_areas: Mapped[Any] = mapped_column(JSONB)


class ContentItemDB(Base):
    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    niche_key: Mapped[str] = mapped_column(String)
    source_idea: Mapped[str] = mapped_column(Text)
    website_article: Mapped[str] = mapped_column(Text)
    telegram_posts: Mapped[Any] = mapped_column(JSONB)
    short_video_scripts: Mapped[Any] = mapped_column(JSONB)
    qa_status: Mapped[str] = mapped_column(String, default="pending")
    qa_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class WeeklyMetricsDB(Base):
    __tablename__ = "weekly_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    niche_key: Mapped[str] = mapped_column(String)
    week: Mapped[int] = mapped_column(Integer)
    views: Mapped[int] = mapped_column(Integer)
    retention_pct: Mapped[float] = mapped_column(Float)
    ctr_pct: Mapped[float] = mapped_column(Float)
    engagement_rate_pct: Mapped[float] = mapped_column(Float)
    subscribers_delta: Mapped[int] = mapped_column(Integer)
    leads: Mapped[int] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AgentTaskDB(Base):
    __tablename__ = "agent_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    week: Mapped[int] = mapped_column(Integer)
    assigned_by: Mapped[str] = mapped_column(String)
    assigned_to: Mapped[str] = mapped_column(String)
    task_description: Mapped[str] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class WeeklyDecisionDB(Base):
    __tablename__ = "weekly_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    week: Mapped[int] = mapped_column(Integer)
    niche_key: Mapped[str] = mapped_column(String)
    keep_topics: Mapped[Any] = mapped_column(JSONB)
    cut_topics: Mapped[Any] = mapped_column(JSONB)
    test_hypotheses: Mapped[Any] = mapped_column(JSONB)
    notes: Mapped[Any] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
