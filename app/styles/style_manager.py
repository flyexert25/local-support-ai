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
            "avoid": [
                "AI-клише",
                "канцелярит",
                "чрезмерно идеальная корпоративность",
                "обращение 'уважаемый клиент'",
            ],
        }

    def build_style_prompt(self, style: CommunicationStyle | None) -> str:
        if not style:
            return "Пиши естественно, спокойно, без канцелярита и шаблонных AI-фраз."
        profile = style.profile
        phrases = ", ".join(profile.get("typical_phrases") or [])
        return (
            f"Имитируй стиль пользователя: {style.name}.\n"
            f"Тон: {profile.get('tone', 'естественный')}.\n"
            f"Длина: примерно {profile.get('avg_sentence_words', 12)} слов в предложении; "
            f"{profile.get('paragraph_style', 'короткие абзацы')}.\n"
            f"Эмоциональность: {profile.get('emotionality', 'спокойная')}.\n"
            f"Типичные фразы, если подходят по смыслу: {phrases or 'нет явных устойчивых фраз'}.\n"
            "Не копируй примеры дословно. Сохраняй живой человеческий язык и избегай канцелярита.\n"
            "Примеры ответов пользователя:\n"
            f"{style.examples[:3500]}"
        )

    def _profile_with_domain_terms(self, examples: str, profile: dict[str, Any]) -> dict[str, Any]:
        if "domain_terms" in profile:
            return profile
        words = re.findall(r"[\wёЁ-]+", examples, re.UNICODE)
        profile["domain_terms"] = self._extract_domain_terms(words)[:30]
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
            "клиент", "клиента", "ответ", "обращение", "ситуация", "случае", "случай",
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
