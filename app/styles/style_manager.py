from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.storage.database import Database


@dataclass
class CommunicationStyle:
    id: int
    name: str
    examples: str
    profile: dict[str, Any]


class StyleManager:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.ensure_default_style()

    def ensure_default_style(self) -> None:
        existing = self.database.fetch_one("SELECT id FROM styles LIMIT 1")
        if existing:
            return
        examples = (
            "Понял вас. Давайте быстро проверим, что произошло, и найдем самый простой вариант.\n\n"
            "Спасибо за скриншот, по нему уже видно контекст. Я уточню детали и вернусь с решением."
        )
        profile = self.analyze_examples(examples)
        self.database.execute(
            "INSERT INTO styles(name, examples, profile_json) VALUES (?, ?, ?)",
            ("Спокойный support", examples, Database.encode_json(profile)),
        )

    def list_styles(self) -> list[CommunicationStyle]:
        rows = self.database.fetch_all("SELECT * FROM styles ORDER BY name")
        return [
            CommunicationStyle(
                id=int(row["id"]),
                name=str(row["name"]),
                examples=str(row["examples"]),
                profile=self._profile_with_domain_terms(
                    str(row["examples"]),
                    Database.decode_json(str(row["profile_json"])),
                ),
            )
            for row in rows
        ]

    def get_style(self, style_id: int | None) -> CommunicationStyle | None:
        if style_id is None:
            row = self.database.fetch_one("SELECT * FROM styles ORDER BY id LIMIT 1")
        else:
            row = self.database.fetch_one("SELECT * FROM styles WHERE id = ?", (style_id,))
        if not row:
            return None
        return CommunicationStyle(
            id=int(row["id"]),
            name=str(row["name"]),
            examples=str(row["examples"]),
            profile=self._profile_with_domain_terms(
                str(row["examples"]),
                Database.decode_json(str(row["profile_json"])),
            ),
        )

    def save_style(self, name: str, examples: str, style_id: int | None = None) -> int:
        clean_name = name.strip() or "Новый стиль"
        clean_examples = examples.strip()
        profile = self.analyze_examples(clean_examples)
        existing_profile: dict[str, Any] = {}
        if style_id:
            existing = self.get_style(style_id)
            existing_profile = existing.profile if existing else {}
        profile = self._merge_learning_profile(profile, existing_profile)
        if style_id:
            self.database.execute(
                """
                UPDATE styles
                SET name = ?, examples = ?, profile_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (clean_name, clean_examples, Database.encode_json(profile), style_id),
            )
            return style_id
        return self.database.execute(
            "INSERT INTO styles(name, examples, profile_json) VALUES (?, ?, ?)",
            (clean_name, clean_examples, Database.encode_json(profile)),
        )

    def append_example(self, style_id: int, example: str) -> CommunicationStyle:
        style = self.get_style(style_id)
        if not style:
            raise ValueError("Активный стиль не найден")
        clean_example = example.strip()
        if not clean_example:
            raise ValueError("Нечего сохранять: ответ пустой")
        separator = "\n\n" if style.examples.strip() else ""
        updated_examples = f"{style.examples.strip()}{separator}{clean_example}"
        self.save_style(style.name, updated_examples, style.id)
        self._promote_priority_examples(style.id, [clean_example])
        updated = self.get_style(style.id)
        if not updated:
            raise ValueError("Не удалось обновить стиль")
        return updated

    def delete_style(self, style_id: int) -> None:
        rows = self.database.fetch_all("SELECT id FROM styles")
        if len(rows) <= 1:
            raise ValueError("Нельзя удалить последний стиль")
        self.database.execute("DELETE FROM styles WHERE id = ?", (style_id,))

    def import_style_file(self, path: Path) -> int:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            payload = json.loads(text)
            if isinstance(payload, dict):
                return self.save_style(
                    str(payload.get("name") or path.stem),
                    str(payload.get("examples") or payload.get("text") or ""),
                )
            if isinstance(payload, list):
                return self.save_style(path.stem, "\n\n".join(map(str, payload)))
        return self.save_style(path.stem, text)

    def export_style(self, style_id: int, path: Path) -> None:
        style = self.get_style(style_id)
        if not style:
            raise ValueError("Стиль не найден")
        payload = {
            "name": style.name,
            "examples": style.examples,
            "profile": style.profile,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def analyze_examples(self, examples: str) -> dict[str, Any]:
        text = examples.strip()
        sentences = [s for s in re.split(r"[.!?。！？\n]+", text) if s.strip()]
        words = re.findall(r"[\wёЁ-]+", text, re.UNICODE)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        avg_sentence_words = round(len(words) / max(len(sentences), 1), 1)
        avg_line_chars = round(sum(map(len, lines)) / max(len(lines), 1), 1)
        emoji_count = len(re.findall(r"[\U0001F300-\U0001FAFF]", text))
        exclamation_count = text.count("!")
        question_count = text.count("?")
        polite_markers = self._count_markers(
            text,
            ["спасибо", "пожалуйста", "давайте", "подскажите", "проверим", "thank", "please", "let's"],
        )
        formal_markers = self._count_markers(
            text,
            ["уважаемый", "настоящим", "в соответствии", "информируем", "dear customer", "regards"],
        )
        typical_phrases = self._extract_typical_phrases(lines)
        domain_terms = self._extract_domain_terms(words)
        tone = "дружелюбный" if polite_markers >= formal_markers else "нейтральный"
        if formal_markers > polite_markers + 1:
            tone = "формальный"
        return {
            "avg_sentence_words": avg_sentence_words,
            "avg_line_chars": avg_line_chars,
            "paragraph_style": "короткие абзацы" if avg_line_chars < 140 else "развернутые абзацы",
            "tone": tone,
            "emotionality": "умеренная" if exclamation_count or emoji_count else "спокойная",
            "friendliness_score": polite_markers,
            "formality_score": formal_markers,
            "question_ratio": round(question_count / max(len(sentences), 1), 2),
            "typical_phrases": typical_phrases[:8],
            "domain_terms": domain_terms[:30],
            "topic_hints": [],
            "avoid": [
                "AI-клише",
                "канцелярит",
                "чрезмерно идеальная корпоративность",
                "чрезмерно официальное обращение",
            ],
        }

    def learn_from_confirmed_interaction(
        self,
        style_id: int,
        customer_text: str,
        final_response: str,
        topic: str | None = None,
        *,
        store_example: bool = False,
    ) -> CommunicationStyle:
        style = self.get_style(style_id)
        if not style:
            raise ValueError("Активный стиль не найден")

        clean_response = final_response.strip()
        if store_example and clean_response:
            style = self.append_example(style_id, clean_response)
        else:
            style = self.get_style(style_id) or style

        profile = dict(style.profile)
        if clean_response:
            existing_examples = [
                str(item).strip()
                for item in profile.get("priority_examples", [])
                if str(item).strip()
            ]
            profile["priority_examples"] = self._dedupe_examples([clean_response, *existing_examples])[:8]

        markers = self._extract_context_markers(customer_text, clean_response)
        if markers:
            existing_terms = [
                str(item).strip()
                for item in profile.get("domain_terms", [])
                if str(item).strip()
            ]
            profile["domain_terms"] = self._dedupe_terms([*markers, *existing_terms])[:40]

        clean_topic = (topic or "").strip()
        if clean_topic and clean_topic != "Общее обращение":
            existing_hints = profile.get("topic_hints", [])
            profile["topic_hints"] = self._merge_topic_hints(
                existing_hints,
                clean_topic,
                markers,
                customer_text,
            )

        self.database.execute(
            """
            UPDATE styles
            SET profile_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (Database.encode_json(profile), style_id),
        )
        updated = self.get_style(style_id)
        if not updated:
            raise ValueError("Не удалось обновить стиль")
        return updated

    def learn_from_topic_correction(
        self,
        style_id: int,
        customer_text: str,
        ocr_text: str,
        corrected_topic: str,
    ) -> CommunicationStyle:
        style = self.get_style(style_id)
        if not style:
            raise ValueError("Активный стиль не найден")

        clean_topic = corrected_topic.strip()
        if not clean_topic:
            raise ValueError("Не выбрана тема для сохранения")

        profile = dict(style.profile)
        combined_text = "\n".join(part.strip() for part in [customer_text, ocr_text] if part and part.strip())
        markers = self._extract_context_markers(combined_text, "")
        profile["topic_hints"] = self._merge_topic_hints(
            profile.get("topic_hints", []),
            clean_topic,
            markers,
            combined_text,
        )
        if markers:
            existing_terms = [
                str(item).strip()
                for item in profile.get("domain_terms", [])
                if str(item).strip()
            ]
            profile["domain_terms"] = self._dedupe_terms([*markers, *existing_terms])[:40]

        self.database.execute(
            """
            UPDATE styles
            SET profile_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (Database.encode_json(profile), style_id),
        )
        updated = self.get_style(style_id)
        if not updated:
            raise ValueError("Не удалось обновить стиль")
        return updated

    def build_style_prompt(self, style: CommunicationStyle | None) -> str:
        if not style:
            return "Пиши естественно, спокойно, без канцелярита и шаблонных AI-фраз."
        profile = style.profile
        priority_examples = [
            str(item).strip()
            for item in profile.get("priority_examples", [])
            if str(item).strip()
        ]
        priority_block = "\n".join(
            f"- {self._short_example(example, 180)}"
            for example in priority_examples[:3]
        )
        terms = self._short_terms(profile.get("domain_terms", []), 8)
        topics = self._short_terms(
            [item.get("name", "") for item in profile.get("topic_hints", []) if isinstance(item, dict)],
            4,
        )
        return (
            f"Имитируй стиль пользователя: {style.name}.\n"
            f"Тон: {profile.get('tone', 'естественный')}.\n"
            f"Длина: примерно {profile.get('avg_sentence_words', 12)} слов в предложении; "
            f"{profile.get('paragraph_style', 'короткие абзацы')}.\n"
            f"Эмоциональность: {profile.get('emotionality', 'спокойная')}.\n"
            f"Типичные термины и контекст: {terms or 'без явных доменных слов'}.\n"
            f"Частые темы: {topics or 'без устойчивых тем'}.\n"
            f"Свежие примеры, на которые полезно ориентироваться:\n"
            f"{priority_block or '- пока нет подтверждённых примеров'}\n"
            "Не копируй примеры дословно. Сохраняй живой человеческий язык, краткость и смысл."
        )

    def _promote_priority_examples(self, style_id: int, examples: list[str]) -> None:
        style = self.get_style(style_id)
        if not style:
            return
        profile = dict(style.profile)
        existing_examples = [
            str(item).strip()
            for item in profile.get("priority_examples", [])
            if str(item).strip()
        ]
        profile["priority_examples"] = self._dedupe_examples([*examples, *existing_examples])[:8]
        self.database.execute(
            """
            UPDATE styles
            SET profile_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (Database.encode_json(profile), style_id),
        )

    @staticmethod
    def _merge_learning_profile(profile: dict[str, Any], existing_profile: dict[str, Any]) -> dict[str, Any]:
        merged = dict(profile)
        priority_examples = [
            str(item).strip()
            for item in existing_profile.get("priority_examples", [])
            if str(item).strip()
        ]
        if priority_examples:
            merged["priority_examples"] = StyleManager._dedupe_examples(priority_examples)[:8]
        existing_domain_terms = [
            str(item).strip()
            for item in existing_profile.get("domain_terms", [])
            if str(item).strip()
        ]
        if existing_domain_terms:
            current_domain_terms = [
                str(item).strip()
                for item in merged.get("domain_terms", [])
                if str(item).strip()
            ]
            merged["domain_terms"] = StyleManager._dedupe_terms([*current_domain_terms, *existing_domain_terms])[:40]
        existing_topic_hints = existing_profile.get("topic_hints", [])
        if existing_topic_hints:
            merged["topic_hints"] = StyleManager._normalize_topic_hints(existing_topic_hints)
        return merged

    @staticmethod
    def _short_example(text: str, max_chars: int) -> str:
        clean = " ".join(text.split()).strip()
        if len(clean) <= max_chars:
            return clean
        truncated = clean[:max_chars].rsplit(" ", 1)[0].strip()
        return (truncated or clean[:max_chars]).strip() + "..."

    @staticmethod
    def _short_terms(raw_terms: Any, limit: int) -> str:
        if not isinstance(raw_terms, (list, tuple)):
            return ""
        terms = [
            str(term).strip()
            for term in raw_terms
            if str(term).strip()
        ]
        return ", ".join(terms[:limit])

    @staticmethod
    def _dedupe_examples(examples: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for example in examples:
            clean = example.strip()
            key = clean.lower()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(clean)
        return result

    def _profile_with_domain_terms(self, examples: str, profile: dict[str, Any]) -> dict[str, Any]:
        profile = dict(profile)
        if "domain_terms" not in profile:
            words = re.findall(r"[\wёЁ-]+", examples, re.UNICODE)
            profile["domain_terms"] = self._extract_domain_terms(words)[:30]
        if "topic_hints" not in profile:
            profile["topic_hints"] = []
        words = re.findall(r"[\wёЁ-]+", examples, re.UNICODE)
        profile["domain_terms"] = self._dedupe_terms(
            [
                *[str(item).strip() for item in profile.get("domain_terms", []) if str(item).strip()],
                *self._extract_domain_terms(words)[:12],
            ]
        )[:40]
        profile["topic_hints"] = self._normalize_topic_hints(profile.get("topic_hints", []))
        return profile

    @staticmethod
    def _count_markers(text: str, markers: list[str]) -> int:
        lowered = text.lower()
        return sum(lowered.count(marker.lower()) for marker in markers)

    @staticmethod
    def _extract_typical_phrases(lines: list[str]) -> list[str]:
        candidates: list[str] = []
        for line in lines:
            if 8 <= len(line) <= 90:
                candidates.append(line)
        seen: set[str] = set()
        result: list[str] = []
        for phrase in candidates:
            key = phrase.lower()
            if key not in seen:
                seen.add(key)
                result.append(phrase)
        return result

    @staticmethod
    def _extract_domain_terms(words: list[str]) -> list[str]:
        stop_words = {
            "здравствуйте", "понимаю", "поясню", "смотрите", "сейчас", "можно", "нужно",
            "если", "когда", "почему", "который", "которая", "которые", "вашей", "вашим",
            "ваших", "вашего", "вашему", "ваши", "ваш", "вами", "будет", "были", "было",
            "есть", "также", "только", "после", "перед", "сумма", "сумму", "деньги",
            "пользователь", "ответ", "обращение", "ситуация", "случае", "случай",
            "проверим", "уточню", "вернусь", "решением", "спасибо", "пожалуйста",
            "hello", "please", "thanks", "customer", "answer", "support",
        }
        counts: dict[str, int] = {}
        for word in words:
            clean = word.lower().strip("-_")
            if len(clean) < 5 or clean in stop_words or clean.isdigit():
                continue
            if any(ch.isdigit() for ch in clean):
                continue
            counts[clean] = counts.get(clean, 0) + 1
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        return [word for word, _ in ranked]

    @staticmethod
    def _dedupe_terms(terms: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for term in terms:
            clean = str(term).strip().lower()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            result.append(clean)
        return result

    def _extract_context_markers(self, customer_text: str, final_response: str) -> list[str]:
        customer_words = re.findall(r"[\wёЁ-]+", customer_text, re.UNICODE)
        response_words = re.findall(r"[\wёЁ-]+", final_response, re.UNICODE)
        customer_terms = self._extract_domain_terms(customer_words)[:10]
        response_terms = self._extract_domain_terms(response_words)[:6]
        phrases = self._extract_context_phrases(customer_text)[:8]
        return self._dedupe_terms([*phrases, *customer_terms, *response_terms])[:16]

    @staticmethod
    def _extract_context_phrases(text: str) -> list[str]:
        tokens = [token.lower() for token in re.findall(r"[\wёЁ-]+", text, re.UNICODE)]
        phrases: list[str] = []
        for index in range(len(tokens) - 1):
            left = tokens[index].strip("-_")
            right = tokens[index + 1].strip("-_")
            if len(left) < 4 or len(right) < 4:
                continue
            phrases.append(f"{left} {right}")
        return StyleManager._dedupe_terms(phrases)

    @staticmethod
    def _normalize_topic_hints(raw_hints: Any) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        if not isinstance(raw_hints, list):
            return normalized
        for item in raw_hints:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            markers = [
                str(marker).strip().lower()
                for marker in item.get("markers", [])
                if str(marker).strip()
            ]
            examples = [
                str(example).strip()
                for example in item.get("examples", [])
                if str(example).strip()
            ]
            try:
                hits = int(item.get("hits", 1) or 1)
            except Exception:
                hits = 1
            normalized.append(
                {
                    "name": name,
                    "markers": StyleManager._dedupe_terms(markers)[:12],
                    "examples": StyleManager._dedupe_examples(examples)[:4],
                    "hits": max(hits, 1),
                }
            )
        return normalized

    def _merge_topic_hints(
        self,
        existing_hints: Any,
        topic: str,
        markers: list[str],
        customer_text: str,
    ) -> list[dict[str, Any]]:
        hints = self._normalize_topic_hints(existing_hints)
        example = customer_text.strip()
        merged = False
        for hint in hints:
            if str(hint.get("name", "")).strip().lower() != topic.strip().lower():
                continue
            hint["markers"] = self._dedupe_terms([*markers, *hint.get("markers", [])])[:12]
            if example:
                hint["examples"] = self._dedupe_examples([example, *hint.get("examples", [])])[:4]
            hint["hits"] = int(hint.get("hits", 1) or 1) + 1
            merged = True
            break
        if not merged:
            hints.append(
                {
                    "name": topic,
                    "markers": self._dedupe_terms(markers)[:12],
                    "examples": [example] if example else [],
                    "hits": 1,
                }
            )
        hints.sort(key=lambda item: (-int(item.get("hits", 1)), str(item.get("name", "")).lower()))
        return hints[:24]
