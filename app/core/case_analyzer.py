from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class CaseAnalysis:
    topic: str
    signals: list[str]
    extracted: dict[str, list[str]]

    def to_display_text(self) -> str:
        signals = ", ".join(self.signals[:6]) if self.signals else "явных признаков пока нет"
        details: list[str] = []
        if self.extracted.get("amounts"):
            details.append("суммы: " + ", ".join(self.extracted["amounts"][:3]))
        if self.extracted.get("dates"):
            details.append("даты: " + ", ".join(self.extracted["dates"][:3]))
        if self.extracted.get("mcc_codes"):
            details.append("MCC: " + ", ".join(self.extracted["mcc_codes"][:4]))
        suffix = f" · {'; '.join(details)}" if details else ""
        return f"Тема: {self.topic}. Признаки: {signals}{suffix}"


class CaseAnalyzer:
    TOPIC_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("Проценты / кредитная карта", ("процент", "льготн", "кредитн", "выписк", "платежный период")),
        ("Арест / блокировка счетов", ("арест", "блокиров", "взыск", "долг", "пристав", "исполнительн")),
        ("Возврат / отмена покупки", ("возврат", "отмен", "вернут", "верн", "магазин", "продавец")),
        ("Премиум / подписка", ("премиум", "premium", "обслуживан", "2990", "2 990", "подписк")),
        ("Кэшбэк / уровень сервиса", ("кэшб", "cashback", "silver", "diamond", "уров", "бизнес-зал", "проход")),
        ("Переводы / СБП / MCC", ("сбп", "qr", "mcc", "перевод", "кошелек", "кошелёк", "наличн")),
        ("Кредит / рефинансирование", ("рефинанс", "кредит", "залог", "автокредит", "ипотек")),
        ("Страхование", ("страхов", "полис", "осаго", "каско", "страховой случай", "коробочное страхование")),
        ("Просрочка / дата платежа", ("просроч", "позже 21", "21:00", "дата платеж", "штраф", "пени")),
    )

    SIGNAL_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("нужна проверка начислений", ("списали", "начислили", "удержали", "проценты")),
        ("клиент не понимает правило", ("почему", "не понимаю", "объясните", "как так")),
        ("есть риск недовольства", ("ошибка", "жалоба", "несправедливо", "обман", "срочно")),
        ("нужен срок/статус", ("когда", "сколько ждать", "статус", "вернутся", "появятся")),
        ("финансовая операция", ("₽", "руб", "сумм", "деньг", "платеж", "покупк")),
        ("нужен аккуратный отказ", ("отказ", "невозможно", "не предусмотрено", "не можем")),
    )

    AMOUNT_RE = re.compile(r"(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d+)(?:[,.]\d{1,2})?\s*(?:₽|руб\.?|р\b)", re.IGNORECASE)
    DATE_RE = re.compile(r"\b(?:\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?|\d{1,2}\s+[а-яё]+)\b", re.IGNORECASE)
    MCC_RE = re.compile(r"\b(?:MCC[-\s]?)?(\d{4})(?:\s*[–-]\s*(\d{4}))?\b", re.IGNORECASE)

    def analyze(self, *parts: str, style_profile: dict[str, Any] | None = None) -> CaseAnalysis:
        text = "\n".join(part for part in parts if part).strip()
        lowered = text.lower()
        topic = self._detect_topic(lowered)
        if topic == "Общее обращение" and style_profile:
            topic = self._detect_style_topic(lowered, style_profile)
        signals = self._detect_signals(lowered)
        extracted = self._extract_entities(text)
        return CaseAnalysis(topic=topic, signals=signals, extracted=extracted)

    def _detect_topic(self, lowered: str) -> str:
        scores: list[tuple[int, str]] = []
        for topic, markers in self.TOPIC_RULES:
            score = sum(1 for marker in markers if marker in lowered)
            if score:
                scores.append((score, topic))
        if not scores:
            return "Общее обращение"
        scores.sort(reverse=True)
        return scores[0][1]

    def _detect_signals(self, lowered: str) -> list[str]:
        signals: list[str] = []
        for signal, markers in self.SIGNAL_RULES:
            if any(marker in lowered for marker in markers):
                signals.append(signal)
        return signals

    def _detect_style_topic(self, lowered: str, style_profile: dict[str, Any]) -> str:
        terms = [str(term).lower() for term in style_profile.get("domain_terms", [])]
        matches = [term for term in terms if len(term) >= 5 and term in lowered]
        if not matches:
            return "Общее обращение"
        best = sorted(matches, key=len, reverse=True)[0]
        return f"Тема из стиля: {best}"

    def _extract_entities(self, text: str) -> dict[str, list[str]]:
        amount_matches = list(self.AMOUNT_RE.finditer(text))
        amount_spans = [match.span() for match in amount_matches]
        amounts = self._unique([match.group(0) for match in amount_matches])
        dates = self._unique(self.DATE_RE.findall(text))
        mcc_codes: list[str] = []
        for match in self.MCC_RE.finditer(text):
            if self._overlaps(match.span(), amount_spans):
                continue
            start = match.group(1)
            end = match.group(2)
            if end:
                mcc_codes.append(f"{start}-{end}")
            elif start:
                mcc_codes.append(start)
        return {
            "amounts": amounts[:8],
            "dates": dates[:8],
            "mcc_codes": self._unique(mcc_codes)[:12],
        }

    @staticmethod
    def _unique(values: list[Any]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            clean = str(value).strip()
            if clean and clean.lower() not in seen:
                seen.add(clean.lower())
                result.append(clean)
        return result

    @staticmethod
    def _overlaps(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
        start, end = span
        return any(start < other_end and end > other_start for other_start, other_end in spans)
