from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from app.storage.database import Database


TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9-]+|[^\w\s]", re.UNICODE)


@dataclass
class OCRCorrectionResult:
    text: str
    replacements: list[tuple[str, str]]


class LearningManager:
    def __init__(self, database: Database) -> None:
        self.database = database

    def apply_ocr_memory(self, text: str, min_hits: int = 2) -> OCRCorrectionResult:
        if not text.strip():
            return OCRCorrectionResult(text=text, replacements=[])

        replacement_map = self._build_ocr_replacement_map(min_hits=min_hits)
        if not replacement_map:
            return OCRCorrectionResult(text=text, replacements=[])

        parts = re.split(r"(\W+)", text)
        applied: list[tuple[str, str]] = []
        for index, part in enumerate(parts):
            normalized = self._normalize_token(part)
            replacement = replacement_map.get(normalized)
            if not replacement or part == replacement:
                continue
            parts[index] = self._match_case(part, replacement)
            applied.append((part, parts[index]))
        return OCRCorrectionResult(text="".join(parts), replacements=applied)

    def build_quality_rules(self, style_profile: dict[str, Any] | None = None) -> str:
        rules: list[str] = []
        style_profile = style_profile or {}
        ocr_stats = self.ocr_feedback_stats()
        response_stats = self.response_feedback_stats()
        response_patterns = self.response_feedback_patterns()

        if ocr_stats["total"] >= 3 and ocr_stats["corrected_ratio"] >= 0.35:
            rules.append(
                "Если OCR-текст выглядит шумно или местами битым, опирайся на общий смысл и не повторяй искажённые фрагменты дословно."
            )
        if style_profile.get("avg_sentence_words", 0) and float(style_profile["avg_sentence_words"]) <= 10:
            rules.append("Держи ответ коротким: лучше несколько простых предложений, чем один тяжёлый абзац.")
        if style_profile.get("formality_score", 0) > style_profile.get("friendliness_score", 0):
            rules.append("Не скатывайся в чрезмерную официальность. Пиши ровно и по-человечески.")
        else:
            rules.append("Сохраняй спокойный дружелюбный тон без шаблонного сервиса и без лишнего пафоса.")

        if style_profile.get("priority_examples"):
            rules.append("Сильнее ориентируйся на свежие сохранённые примеры, чем на общий усреднённый тон.")
        if response_stats["total"] >= 3 and response_stats["corrected_ratio"] >= 0.3:
            rules.append("Если формулировка звучит тяжело, упростись и сделай ответ ближе к обычной живой переписке.")
        if response_patterns["prefer_shorter"]:
            rules.append("Держи ответ компактным: без лишних вводных фраз и без второго круга объяснений.")
        if response_patterns["avoid_formal_greeting"]:
            rules.append("Не начинай ответ с формального приветствия, если без него можно обойтись.")
        if response_patterns["avoid_thanks_opening"]:
            rules.append("Не открывай ответ дежурной благодарностью, если она не помогает сути.")

        return "\n".join(f"- {rule}" for rule in rules)

    def ocr_feedback_stats(self) -> dict[str, float]:
        row = self.database.fetch_one(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN verdict = 'correct' THEN 1 ELSE 0 END) AS correct_count,
                SUM(CASE WHEN verdict = 'corrected' THEN 1 ELSE 0 END) AS corrected_count
            FROM ocr_feedback
            """
        )
        total = int(row["total"] or 0) if row else 0
        correct_count = int(row["correct_count"] or 0) if row else 0
        corrected_count = int(row["corrected_count"] or 0) if row else 0
        corrected_ratio = corrected_count / total if total else 0.0
        return {
            "total": float(total),
            "correct_count": float(correct_count),
            "corrected_count": float(corrected_count),
            "corrected_ratio": corrected_ratio,
        }

    def response_feedback_stats(self) -> dict[str, float]:
        row = self.database.fetch_one(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN verdict = 'correct' THEN 1 ELSE 0 END) AS correct_count,
                SUM(CASE WHEN verdict = 'corrected' THEN 1 ELSE 0 END) AS corrected_count
            FROM response_feedback
            """
        )
        total = int(row["total"] or 0) if row else 0
        correct_count = int(row["correct_count"] or 0) if row else 0
        corrected_count = int(row["corrected_count"] or 0) if row else 0
        corrected_ratio = corrected_count / total if total else 0.0
        return {
            "total": float(total),
            "correct_count": float(correct_count),
            "corrected_count": float(corrected_count),
            "corrected_ratio": corrected_ratio,
        }

    def response_feedback_patterns(self) -> dict[str, bool]:
        rows = self.database.fetch_all(
            """
            SELECT raw_response, corrected_response
            FROM response_feedback
            WHERE verdict = 'corrected'
              AND TRIM(raw_response) <> ''
              AND TRIM(corrected_response) <> ''
            ORDER BY id DESC
            LIMIT 40
            """
        )
        if not rows:
            return {
                "prefer_shorter": False,
                "avoid_formal_greeting": False,
                "avoid_thanks_opening": False,
            }

        raw_lengths: list[int] = []
        corrected_lengths: list[int] = []
        formal_greeting_removed = 0
        thanks_opening_removed = 0

        for row in rows:
            raw = str(row["raw_response"]).strip()
            corrected = str(row["corrected_response"]).strip()
            if not raw or not corrected:
                continue
            raw_lengths.append(len(raw))
            corrected_lengths.append(len(corrected))

            raw_start = raw.lower()[:40]
            corrected_start = corrected.lower()[:40]
            if ("здравствуйте" in raw_start or "добрый день" in raw_start) and (
                "здравствуйте" not in corrected_start and "добрый день" not in corrected_start
            ):
                formal_greeting_removed += 1
            if ("спасибо" in raw_start or "благодар" in raw_start) and (
                "спасибо" not in corrected_start and "благодар" not in corrected_start
            ):
                thanks_opening_removed += 1

        if not raw_lengths or not corrected_lengths:
            return {
                "prefer_shorter": False,
                "avoid_formal_greeting": False,
                "avoid_thanks_opening": False,
            }

        sample_size = min(len(raw_lengths), len(corrected_lengths))
        avg_raw = sum(raw_lengths) / sample_size
        avg_corrected = sum(corrected_lengths) / sample_size
        return {
            "prefer_shorter": avg_corrected <= avg_raw * 0.88 and sample_size >= 2,
            "avoid_formal_greeting": formal_greeting_removed >= 2,
            "avoid_thanks_opening": thanks_opening_removed >= 2,
        }

    def _build_ocr_replacement_map(self, min_hits: int) -> dict[str, str]:
        rows = self.database.fetch_all(
            """
            SELECT raw_text, corrected_text
            FROM ocr_feedback
            WHERE verdict = 'corrected'
              AND TRIM(raw_text) <> ''
              AND TRIM(corrected_text) <> ''
            ORDER BY id DESC
            """
        )
        pairs: Counter[tuple[str, str]] = Counter()
        for row in rows:
            for pair in self._extract_token_replacements(str(row["raw_text"]), str(row["corrected_text"])):
                pairs[pair] += 1

        replacement_map: dict[str, str] = {}
        ranked = sorted(pairs.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
        for (source, target), hits in ranked:
            if hits < min_hits or source in replacement_map:
                continue
            replacement_map[source] = target
        return replacement_map

    def _extract_token_replacements(self, raw_text: str, corrected_text: str) -> list[tuple[str, str]]:
        raw_tokens = TOKEN_RE.findall(raw_text)
        corrected_tokens = TOKEN_RE.findall(corrected_text)
        if not raw_tokens or not corrected_tokens:
            return []

        matcher = SequenceMatcher(None, raw_tokens, corrected_tokens)
        replacements: list[tuple[str, str]] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != "replace":
                continue
            raw_chunk = raw_tokens[i1:i2]
            corrected_chunk = corrected_tokens[j1:j2]
            if len(raw_chunk) != len(corrected_chunk):
                continue
            for raw_token, corrected_token in zip(raw_chunk, corrected_chunk):
                source = self._normalize_token(raw_token)
                target = corrected_token.strip()
                if not source or not target:
                    continue
                if source == self._normalize_token(target):
                    continue
                if not self._is_learning_candidate(source, target):
                    continue
                replacements.append((source, target))
        return replacements

    @staticmethod
    def _normalize_token(token: str) -> str:
        return token.strip().lower()

    @staticmethod
    def _is_learning_candidate(source: str, target: str) -> bool:
        if len(source) < 4 or len(target) < 4:
            return False
        if source.isdigit() or target.isdigit():
            return False
        if not any(char.isalpha() for char in source + target):
            return False
        return True

    @staticmethod
    def _match_case(original: str, replacement: str) -> str:
        if original.isupper():
            return replacement.upper()
        if original[:1].isupper():
            return replacement[:1].upper() + replacement[1:]
        return replacement
