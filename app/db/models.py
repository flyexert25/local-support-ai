from __future__ import annotations

from sqlalchemy import Boolean, Float, Index, Integer, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    """Generated answer history.

    Maps the existing `conversations` table created by the legacy sqlite3
    storage layer.
    """

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ocr_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    response_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    style_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    topic: Mapped[str] = mapped_column(Text, nullable=False, default="")
    signals_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    extracted_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    ocr_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    analyze_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    preview_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generation_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.current_timestamp())

    __table_args__ = (
        Index("ix_conversations_topic", "topic"),
        Index("ix_conversations_created_at", "created_at"),
        Index("ix_conversations_style_id", "style_id"),
    )


class Feedback(Base):
    """Response quality feedback.

    Maps the existing `response_feedback` table. OCR and topic feedback stay in
    their legacy tables for now; they can later be modeled separately if needed.
    """

    __tablename__ = "response_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ocr_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_response: Mapped[str] = mapped_column(Text, nullable=False, default="")
    corrected_response: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    style_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verdict: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.current_timestamp())

    __table_args__ = (
        Index("ix_response_feedback_verdict", "verdict"),
        Index("ix_response_feedback_created_at", "created_at"),
        Index("ix_response_feedback_style_id", "style_id"),
    )


class KnowledgeArticle(Base):
    """Local knowledge article with rules and facts."""

    __tablename__ = "knowledge_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    kind: Mapped[str] = mapped_column(Text, nullable=False, default="knowledge_article")
    product: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(Text, nullable=False, default="")
    language: Mapped[str] = mapped_column(Text, nullable=False, default="ru")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sections_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    facts_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    example_queries_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    source_path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.current_timestamp())

    __table_args__ = (
        Index("ix_knowledge_articles_product", "product"),
        Index("ix_knowledge_articles_category", "category"),
        Index("ix_knowledge_articles_enabled", "enabled"),
    )


class KnowledgeCase(Base):
    """Example request with expected topic/facts and an ideal answer."""

    __tablename__ = "knowledge_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    article_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ocr_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    expected_topic: Mapped[str] = mapped_column(Text, nullable=False, default="")
    expected_product: Mapped[str] = mapped_column(Text, nullable=False, default="")
    expected_facts_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    ideal_answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.current_timestamp())

    __table_args__ = (
        Index("ix_knowledge_cases_article_id", "article_id"),
        Index("ix_knowledge_cases_expected_topic", "expected_topic"),
        Index("ix_knowledge_cases_expected_product", "expected_product"),
        Index("ix_knowledge_cases_enabled", "enabled"),
    )


class EvaluationRun(Base):
    """Quality evaluation result for a batch of synthetic cases."""

    __tablename__ = "evaluation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    topic_accuracy: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fact_retrieval_accuracy: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    answer_quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    average_sla_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    peak_sla_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.current_timestamp())

    __table_args__ = (
        Index("ix_evaluation_runs_created_at", "created_at"),
        Index("ix_evaluation_runs_name", "name"),
    )

