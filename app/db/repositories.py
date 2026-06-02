from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Conversation, EvaluationRun, Feedback, KnowledgeArticle, KnowledgeCase


def _encode_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


class ConversationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def total(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(Conversation)) or 0)

    def latest(self, limit: int = 20) -> list[Conversation]:
        statement = select(Conversation).order_by(Conversation.id.desc()).limit(limit)
        return list(self.session.scalars(statement))


class FeedbackRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def total(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(Feedback)) or 0)

    def latest(self, limit: int = 20) -> list[Feedback]:
        statement = select(Feedback).order_by(Feedback.id.desc()).limit(limit)
        return list(self.session.scalars(statement))


class KnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_articles(self, *, enabled_only: bool = True) -> list[KnowledgeArticle]:
        statement = select(KnowledgeArticle).order_by(KnowledgeArticle.product, KnowledgeArticle.title)
        if enabled_only:
            statement = statement.where(KnowledgeArticle.enabled.is_(True))
        return list(self.session.scalars(statement))

    def get_article(self, article_id: str) -> KnowledgeArticle | None:
        statement = select(KnowledgeArticle).where(KnowledgeArticle.article_id == article_id)
        return self.session.scalar(statement)

    def upsert_article(
        self,
        *,
        article_id: str,
        title: str,
        product: str,
        category: str = "",
        summary: str = "",
        facts: list[str] | None = None,
        tags: list[str] | None = None,
        sections: list[dict[str, Any]] | None = None,
        example_queries: list[str] | None = None,
        source_path: str = "",
        source_metadata: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> KnowledgeArticle:
        article = self.get_article(article_id)
        if article is None:
            article = KnowledgeArticle(article_id=article_id)
            self.session.add(article)

        article.title = title
        article.product = product
        article.category = category
        article.summary = summary
        article.facts_json = _encode_json(facts or [])
        article.tags_json = _encode_json(tags or [])
        article.sections_json = _encode_json(sections or [])
        article.example_queries_json = _encode_json(example_queries or [])
        article.source_path = source_path
        article.source_metadata_json = _encode_json(source_metadata or {})
        article.enabled = enabled
        return article

    def list_cases(self, *, enabled_only: bool = True) -> list[KnowledgeCase]:
        statement = select(KnowledgeCase).order_by(KnowledgeCase.expected_topic, KnowledgeCase.id)
        if enabled_only:
            statement = statement.where(KnowledgeCase.enabled.is_(True))
        return list(self.session.scalars(statement))

    def get_case(self, case_id: str) -> KnowledgeCase | None:
        statement = select(KnowledgeCase).where(KnowledgeCase.case_id == case_id)
        return self.session.scalar(statement)

    def upsert_case(
        self,
        *,
        case_id: str,
        customer_text: str,
        expected_topic: str,
        expected_product: str = "",
        article_id: str | None = None,
        ocr_text: str = "",
        expected_facts: list[str] | None = None,
        ideal_answer: str = "",
        tags: list[str] | None = None,
        enabled: bool = True,
    ) -> KnowledgeCase:
        case = self.get_case(case_id)
        if case is None:
            case = KnowledgeCase(case_id=case_id)
            self.session.add(case)

        case.article_id = article_id
        case.customer_text = customer_text
        case.ocr_text = ocr_text
        case.expected_topic = expected_topic
        case.expected_product = expected_product
        case.expected_facts_json = _encode_json(expected_facts or [])
        case.ideal_answer = ideal_answer
        case.tags_json = _encode_json(tags or [])
        case.enabled = enabled
        return case


class EvaluationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_run(
        self,
        *,
        name: str,
        total_cases: int,
        passed_cases: int,
        topic_accuracy: float,
        fact_retrieval_accuracy: float,
        answer_quality_score: float,
        average_sla_ms: int,
        peak_sla_ms: int,
        result: dict[str, Any],
    ) -> EvaluationRun:
        run = EvaluationRun(
            name=name,
            total_cases=total_cases,
            passed_cases=passed_cases,
            topic_accuracy=topic_accuracy,
            fact_retrieval_accuracy=fact_retrieval_accuracy,
            answer_quality_score=answer_quality_score,
            average_sla_ms=average_sla_ms,
            peak_sla_ms=peak_sla_ms,
            result_json=_encode_json(result),
        )
        self.session.add(run)
        return run

    def latest(self, limit: int = 10) -> list[EvaluationRun]:
        statement = select(EvaluationRun).order_by(EvaluationRun.id.desc()).limit(limit)
        return list(self.session.scalars(statement))
