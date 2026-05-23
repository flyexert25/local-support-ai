from pathlib import Path
import sys

from fastapi import FastAPI
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from app.core.case_analyzer import CaseAnalyzer
from app.core.learning_manager import LearningManager
from app.core.settings_manager import SettingsManager
from app.storage.database import Database
from app.styles.style_manager import StyleManager


app = FastAPI()
settings = SettingsManager()
database = Database(settings.database_path)
style_manager = StyleManager(database)
learning_manager = LearningManager(database)
case_analyzer = CaseAnalyzer()


class EchoRequest(BaseModel):
    text: str


class AnalyzeRequest(BaseModel):
    customer_text: str
    ocr_text: str | None = None
    selected_style: str | None = None


class GeneratePreviewRequest(BaseModel):
    customer_text: str
    ocr_text: str | None = None
    selected_style: str | None = None


class GeneratePreviewResponse(BaseModel):
    customer_text: str
    ocr_text: str | None = None
    selected_style: str | None = None
    style_name: str | None = None
    tone: str | None = None
    topic: str
    signals: list[str]
    extracted: dict[str, list[str]]
    quality_rules: list[str]
    draft_reply: str


@app.get("/")
def root():
    return {"message": "FastAPI is working"}


@app.get("/status")
def status():
    return {
        "app": "Local Support AI backend",
        "status": "ok",
        "mode": "learning",
    }


@app.post("/echo")
def echo(data: EchoRequest):
    return {
        "original_text": data.text,
        "length": len(data.text),
        "message": "POST endpoint received your text",
    }


@app.post("/analyze-request")
def analyze_request(data: AnalyzeRequest):
    style = _resolve_style(data.selected_style)
    analysis = case_analyzer.analyze(
        data.customer_text,
        data.ocr_text or "",
        style_profile=style.profile if style else None,
    )

    return {
        "customer_text": data.customer_text,
        "ocr_text": data.ocr_text,
        "selected_style": data.selected_style,
        "style_name": style.name if style else None,
        "topic": analysis.topic,
        "signals": analysis.signals,
        "extracted": analysis.extracted,
    }


@app.post("/generate-preview", response_model=GeneratePreviewResponse)
def generate_preview(data: GeneratePreviewRequest):
    style = _resolve_style(data.selected_style)
    analysis = case_analyzer.analyze(
        data.customer_text,
        data.ocr_text or "",
        style_profile=style.profile if style else None,
    )
    quality_rules_raw = learning_manager.build_quality_rules(style.profile if style else None)
    quality_rules = [
        line.lstrip("- ").strip()
        for line in quality_rules_raw.splitlines()
        if line.strip()
    ]

    return GeneratePreviewResponse(
        customer_text=data.customer_text,
        ocr_text=data.ocr_text,
        selected_style=data.selected_style,
        style_name=style.name if style else None,
        tone=str(style.profile.get("tone")) if style else None,
        topic=analysis.topic,
        signals=analysis.signals,
        extracted=analysis.extracted,
        quality_rules=quality_rules,
        draft_reply=_build_draft_reply(analysis, style.profile if style else None),
    )


def _resolve_style(style_name: str | None):
    default_style = style_manager.get_style(settings.values.selected_style_id)
    if not style_name:
        return default_style
    normalized = style_name.strip().lower()
    for style in style_manager.list_styles():
        if style.name.strip().lower() == normalized:
            return style
    return default_style


def _build_draft_reply(analysis, style_profile: dict | None) -> str:
    style_profile = style_profile or {}
    tone = str(style_profile.get("tone", "дружелюбный"))
    short = float(style_profile.get("avg_sentence_words", 12) or 12) <= 10

    if tone == "формальный":
        opening = "Понимаю ваш вопрос."
    elif tone == "нейтральный":
        opening = "Понял вас."
    else:
        opening = "Понял вас. Давайте быстро разберемся."

    topic_map = {
        "Проценты / кредит наличными": "Проверю, почему начислились проценты по кредиту наличными, и поясню, как это связано с графиком и условиями договора.",
        "Проценты / кредитная карта": "Проверю, почему произошло списание процентов, и коротко поясню логику расчета.",
        "Проценты / кредит": "Проверю, почему появились проценты по кредиту, и поясню, какие условия и даты на это повлияли.",
        "Арест / блокировка счетов": "Посмотрю, как именно отображается блокировка, и объясню, что это означает по вашим счетам.",
        "Возврат / отмена покупки": "Уточню статус возврата и подскажу, на каком этапе сейчас находится операция.",
        "Премиум / подписка": "Проверю условия сервиса и поясню, откуда появилось списание или изменение условий.",
        "Кэшбэк / уровень сервиса": "Сверю условия программы и объясню, как именно учитываются операции в вашем случае.",
        "Переводы / СБП / MCC": "Проверю тип операции и поясню, как она учитывается по правилам сервиса.",
        "Кредит / рефинансирование": "Посмотрю на контекст запроса и поясню, какие варианты здесь реально можно рассмотреть.",
        "Страхование": "Проверю, о каком именно страховом сценарии идет речь, и дальше поясню условия.",
        "Просрочка / дата платежа": "Уточню, как операция прошла по дате обработки, и объясню, что это значит для статуса платежа.",
        "Общее обращение": "Сначала уточню контекст и затем помогу сформулировать понятный ответ по ситуации.",
    }
    body = topic_map.get(analysis.topic, topic_map["Общее обращение"])

    follow_up = ""
    if "нужен срок/статус" in analysis.signals:
        follow_up = " Если понадобится, добавлю ориентир по срокам."
    elif "непонятно правило" in analysis.signals:
        follow_up = " Объясню без лишней формальности и по шагам."
    elif "нужна проверка начислений" in analysis.signals:
        follow_up = " Отдельно проверю расчеты и начисления."

    draft = f"{opening} {body}{follow_up}".strip()
    if short:
        draft = draft.replace("Давайте быстро разберемся. ", "")
    return " ".join(draft.split())
