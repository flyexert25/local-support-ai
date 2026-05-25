from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9-]{4,}", re.UNICODE)


@dataclass
class KnowledgeMatch:
    article_id: str
    title: str
    product: str
    score: int
    summary: str
    facts: list[str]
    matched_terms: list[str]


class KnowledgeService:
    def __init__(self, project_root: Path, pack_id: str = "generic_bank_core_ru") -> None:
        self.project_root = project_root
        self.pack_id = pack_id
        self.pack_root = self.project_root / "knowledge_private" / "packs" / pack_id
        self.manifest_path = self.pack_root / "manifest.json"
        self.manifest: dict[str, Any] | None = None
        self.articles: list[dict[str, Any]] = []
        self.reload()

    @property
    def available(self) -> bool:
        return self.manifest is not None and bool(self.articles)

    def reload(self) -> None:
        self.manifest = None
        self.articles = []
        if not self.manifest_path.exists():
            return

        try:
            self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except Exception:
            self.manifest = None
            return

        article_paths = self.manifest.get("articles", [])
        if not isinstance(article_paths, list):
            self.manifest = None
            return

        loaded: list[dict[str, Any]] = []
        for relative_path in article_paths:
            try:
                article_path = self.pack_root / str(relative_path)
                article = json.loads(article_path.read_text(encoding="utf-8"))
                if isinstance(article, dict):
                    loaded.append(article)
            except Exception:
                continue
        self.articles = loaded

    def status(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "pack_id": self.pack_id,
            "article_count": len(self.articles),
        }

    def search(
        self,
        customer_text: str,
        ocr_text: str = "",
        topic: str | None = None,
        limit: int = 3,
    ) -> list[KnowledgeMatch]:
        if not self.available:
            return []

        query_text = " ".join(part for part in [customer_text, ocr_text, topic or ""] if part).lower()
        query_tokens = self._extract_tokens(query_text)
        if not query_tokens:
            return []

        scored: list[KnowledgeMatch] = []
        for article in self.articles:
            match = self._score_article(article, query_text, query_tokens, topic or "")
            if match.score > 0:
                scored.append(match)

        scored.sort(key=lambda item: (-item.score, item.title))
        if not scored:
            return []

        top_score = scored[0].score
        min_score = max(6, top_score // 2)
        filtered = [item for item in scored if item.score >= min_score]
        return filtered[:limit]

    def _score_article(
        self,
        article: dict[str, Any],
        query_text: str,
        query_tokens: set[str],
        topic: str,
    ) -> KnowledgeMatch:
        title = str(article.get("title", "")).strip()
        product = str(article.get("product", "")).strip()
        summary = str(article.get("summary", "")).strip()
        tags = self._normalize_strings(article.get("tags", []), lowercase=True)
        facts = self._normalize_strings(article.get("facts", []), lowercase=False)
        facts_lower = [item.lower() for item in facts]
        example_queries = self._normalize_strings(article.get("example_queries", []), lowercase=True)

        sections_text = " ".join(
            f"{str(item.get('heading', '')).strip()} {str(item.get('content', '')).strip()}"
            for item in article.get("sections", [])
            if isinstance(item, dict)
        ).lower()
        title_lower = title.lower()
        summary_lower = summary.lower()
        tags_blob = " ".join(tags)
        facts_blob = " ".join(facts_lower)
        examples_blob = " ".join(example_queries)

        score = 0
        matched_terms: set[str] = set()
        for token in query_tokens:
            token_score = 0
            if token in title_lower:
                token_score += 5
            if token in tags_blob:
                token_score += 4
            if token in examples_blob:
                token_score += 3
            if token in facts_blob:
                token_score += 2
            if token in summary_lower or token in sections_text:
                token_score += 1
            if token_score:
                score += token_score
                matched_terms.add(token)

        score += self._topic_boost(topic.lower(), query_text, product, title_lower, tags_blob)

        return KnowledgeMatch(
            article_id=str(article.get("id", "")).strip(),
            title=title,
            product=product,
            score=score,
            summary=summary,
            facts=facts[:2],
            matched_terms=sorted(matched_terms),
        )

    def _topic_boost(
        self,
        topic_lower: str,
        query_text: str,
        product: str,
        title_lower: str,
        tags_blob: str,
    ) -> int:
        score = 0
        if product == "credit_card" and (
            "кредитная карта" in topic_lower
            or "льгот" in topic_lower
            or "кредитная карта" in query_text
            or "минимальн" in query_text
        ):
            score += 8
        if product == "debit_card" and ("дебетов" in query_text or "кэшб" in query_text):
            score += 8
        if product == "deposit" and ("вклад" in query_text or "депозит" in query_text):
            score += 8
        if product == "savings_account" and ("накоп" in query_text or "счет" in query_text or "счёт" in query_text):
            score += 8
        if "кэшбэк" in title_lower or "кэшбэк" in tags_blob:
            if "кэшб" in query_text:
                score += 3
        if "льготный период" in title_lower and "льгот" in query_text:
            score += 3
        return score

    @staticmethod
    def _extract_tokens(text: str) -> set[str]:
        return {token.lower() for token in TOKEN_RE.findall(text)}

    @staticmethod
    def _normalize_strings(values: Any, lowercase: bool) -> list[str]:
        if not isinstance(values, list):
            return []
        result: list[str] = []
        for value in values:
            clean = str(value).strip()
            if lowercase:
                clean = clean.lower()
            if clean:
                result.append(clean)
        return result
