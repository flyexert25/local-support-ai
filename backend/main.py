from pathlib import Path
import sys

from fastapi import FastAPI
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from app.core.case_analyzer import CaseAnalyzer
from app.core.knowledge_service import KnowledgeService
from app.core.learning_manager import LearningManager
from app.core.settings_manager import SettingsManager
from app.storage.database import Database
from app.styles.style_manager import StyleManager
from app.ai.ai_manager import AIManager


app = FastAPI()
settings = SettingsManager()
database = Database(settings.database_path)
style_manager = StyleManager(database)
learning_manager = LearningManager(database)
case_analyzer = CaseAnalyzer()
knowledge_service = KnowledgeService(PROJECT_ROOT)
ai_manager = AIManager(settings)


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


class KnowledgeMatchResponse(BaseModel):
    article_id: str
    title: str
    product: str
    score: int
    summary: str
    facts: list[str]
    matched_terms: list[str]


class GeneratePreviewResponse(BaseModel):
    customer_text: str
    ocr_text: str | None = None
    selected_style: str | None = None
    style_name: str | None = None
    tone: str | None = None
    topic: str
    signals: list[str]
    extracted: dict[str, list[str]]
    customer_tone: str
    escalation_risk: str
    priority: str
    reply_style_label: str | None = None
    quality_rules: list[str]
    knowledge_articles: list[str]
    knowledge_facts: list[str]
    knowledge_matches: list[KnowledgeMatchResponse]
    knowledge_status: str
    draft_reply: str


class GenerateFinalRequest(BaseModel):
    customer_text: str
    ocr_text: str | None = None
    selected_style: str | None = None
    model: str | None = None
    image_base64: str | None = None


class RetrieveKnowledgeRequest(BaseModel):
    customer_text: str
    ocr_text: str | None = None
    topic: str | None = None
    limit: int = 3


class RetrieveKnowledgeResponse(BaseModel):
    topic: str | None = None
    knowledge_articles: list[str]
    knowledge_facts: list[str]
    knowledge_matches: list[KnowledgeMatchResponse]
    knowledge_status: str


class GenerateFinalResponse(BaseModel):
    response_text: str
    model: str
    topic: str
    signals: list[str]
    extracted: dict[str, list[str]]
    customer_tone: str
    escalation_risk: str
    priority: str
    reply_style_label: str | None = None
    knowledge_articles: list[str]
    knowledge_facts: list[str]
    knowledge_matches: list[KnowledgeMatchResponse]
    knowledge_status: str


@app.get("/")
def root():
    return {"message": "FastAPI is working"}


@app.get("/status")
def status():
    return {
        "app": "Local Support AI backend",
        "status": "ok",
        "mode": "learning",
        "knowledge": knowledge_service.status(),
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
    style, analysis = _build_analysis(data.customer_text, data.ocr_text or "", data.selected_style)

    return {
        "customer_text": data.customer_text,
        "ocr_text": data.ocr_text,
        "selected_style": data.selected_style,
        "style_name": style.name if style else None,
        "topic": analysis.topic,
        "signals": analysis.signals,
        "extracted": analysis.extracted,
        "customer_tone": analysis.customer_tone,
        "escalation_risk": analysis.escalation_risk,
        "priority": analysis.priority,
        "reply_style_label": analysis.reply_style_label,
    }


@app.post("/analyze")
def analyze(data: AnalyzeRequest):
    return analyze_request(data)


@app.post("/retrieve-knowledge", response_model=RetrieveKnowledgeResponse)
def retrieve_knowledge(data: RetrieveKnowledgeRequest):
    topic = data.topic
    if not topic:
        _, analysis = _build_analysis(data.customer_text, data.ocr_text or "", None)
        topic = analysis.topic

    knowledge_matches = knowledge_service.search(
        customer_text=data.customer_text,
        ocr_text=data.ocr_text or "",
        topic=topic,
        limit=max(1, min(int(data.limit or 3), 8)),
    )
    knowledge_titles, knowledge_facts, knowledge_details, knowledge_status = _build_knowledge_context(knowledge_matches)
    return RetrieveKnowledgeResponse(
        topic=topic,
        knowledge_articles=knowledge_titles,
        knowledge_facts=knowledge_facts[:4],
        knowledge_matches=knowledge_details,
        knowledge_status=knowledge_status,
    )


@app.post("/generate-preview", response_model=GeneratePreviewResponse)
def generate_preview(data: GeneratePreviewRequest):
    context = _build_backend_context(
        customer_text=data.customer_text,
        ocr_text=data.ocr_text or "",
        selected_style=data.selected_style,
        knowledge_limit=2,
    )

    return GeneratePreviewResponse(
        customer_text=data.customer_text,
        ocr_text=data.ocr_text,
        selected_style=data.selected_style,
        style_name=context["style"].name if context["style"] else None,
        tone=str(context["style"].profile.get("tone")) if context["style"] else None,
        topic=context["analysis"].topic,
        signals=context["analysis"].signals,
        extracted=context["analysis"].extracted,
        customer_tone=context["analysis"].customer_tone,
        escalation_risk=context["analysis"].escalation_risk,
        priority=context["analysis"].priority,
        reply_style_label=context["analysis"].reply_style_label,
        quality_rules=context["quality_rules"],
        knowledge_articles=context["knowledge_titles"],
        knowledge_facts=context["knowledge_facts"][:2],
        knowledge_matches=context["knowledge_details"],
        knowledge_status=context["knowledge_status"],
        draft_reply=_build_draft_reply(
            context["analysis"],
            context["style"].profile if context["style"] else None,
            knowledge_facts=context["knowledge_facts"][:2],
        ),
    )


@app.post("/generate-final", response_model=GenerateFinalResponse)
def generate_final(data: GenerateFinalRequest):
    return _generate_final_response(data)


@app.post("/prepare-answer", response_model=GenerateFinalResponse)
def prepare_answer(data: GenerateFinalRequest):
    return _generate_final_response(data)


def _generate_final_response(data: GenerateFinalRequest) -> GenerateFinalResponse:
    model = (data.model or settings.values.preferred_model or "").strip()
    if not model:
        raise ValueError("Не выбрана локальная модель для генерации.")

    context = _build_backend_context(
        customer_text=data.customer_text,
        ocr_text=data.ocr_text or "",
        selected_style=data.selected_style,
        knowledge_limit=2,
    )
    style = context["style"]

    style_prompt = style_manager.build_style_prompt(style)
    quality_rules = context["quality_rules_raw"]
    reply = ai_manager.generate_reply(
        customer_text=data.customer_text,
        ocr_text=data.ocr_text or "",
        style_prompt=style_prompt,
        quality_rules=quality_rules,
        model=model,
        image_base64=data.image_base64,
        topic_hint=context["analysis"].topic,
        knowledge_facts=context["knowledge_facts"][:2],
    )

    return GenerateFinalResponse(
        response_text=reply,
        model=model,
        topic=context["analysis"].topic,
        signals=context["analysis"].signals,
        extracted=context["analysis"].extracted,
        customer_tone=context["analysis"].customer_tone,
        escalation_risk=context["analysis"].escalation_risk,
        priority=context["analysis"].priority,
        reply_style_label=context["analysis"].reply_style_label,
        knowledge_articles=context["knowledge_titles"],
        knowledge_facts=context["knowledge_facts"][:2],
        knowledge_matches=context["knowledge_details"],
        knowledge_status=context["knowledge_status"],
    )


def _build_analysis(customer_text: str, ocr_text: str, selected_style: str | None):
    style = _resolve_style(selected_style)
    analysis = case_analyzer.analyze(
        customer_text,
        ocr_text,
        style_profile=style.profile if style else None,
        reply_style_label=style.name if style else None,
    )
    return style, analysis


def _build_backend_context(
    customer_text: str,
    ocr_text: str,
    selected_style: str | None,
    knowledge_limit: int,
) -> dict:
    style, analysis = _build_analysis(customer_text, ocr_text, selected_style)
    knowledge_matches = knowledge_service.search(
        customer_text=customer_text,
        ocr_text=ocr_text,
        topic=analysis.topic,
        limit=knowledge_limit,
    )
    knowledge_titles, knowledge_facts, knowledge_details, knowledge_status = _build_knowledge_context(knowledge_matches)
    quality_rules_raw = learning_manager.build_quality_rules(style.profile if style else None)
    quality_rules = [
        line.lstrip("- ").strip()
        for line in quality_rules_raw.splitlines()
        if line.strip()
    ]
    return {
        "style": style,
        "analysis": analysis,
        "quality_rules_raw": quality_rules_raw,
        "quality_rules": quality_rules,
        "knowledge_titles": knowledge_titles,
        "knowledge_facts": knowledge_facts,
        "knowledge_details": knowledge_details,
        "knowledge_status": knowledge_status,
    }


def _resolve_style(style_name: str | None):
    default_style = style_manager.get_style(settings.values.selected_style_id)
    if not style_name:
        return default_style
    normalized = style_name.strip().lower()
    for style in style_manager.list_styles():
        if style.name.strip().lower() == normalized:
            return style
    return default_style


def _build_knowledge_context(knowledge_matches) -> tuple[list[str], list[str], list[KnowledgeMatchResponse], str]:
    knowledge_titles = [match.title for match in knowledge_matches]
    knowledge_facts: list[str] = []
    knowledge_details: list[KnowledgeMatchResponse] = []

    for match in knowledge_matches:
        match_facts: list[str] = []
        for fact in match.facts:
            if not fact:
                continue
            match_facts.append(fact)
            if fact not in knowledge_facts:
                knowledge_facts.append(fact)

        knowledge_details.append(
            KnowledgeMatchResponse(
                article_id=match.article_id,
                title=match.title,
                product=match.product,
                score=match.score,
                summary=match.summary,
                facts=match_facts[:2],
                matched_terms=match.matched_terms[:8],
            )
        )

    if knowledge_facts:
        status = "found"
    elif knowledge_matches:
        status = "article_without_facts"
    else:
        status = "not_found"

    return knowledge_titles, knowledge_facts, knowledge_details, status


def _build_draft_reply(
    analysis,
    style_profile: dict | None,
    knowledge_facts: list[str] | None = None,
) -> str:
    style_profile = style_profile or {}
    tone = str(style_profile.get("tone", "дружелюбный"))
    short = float(style_profile.get("avg_sentence_words", 12) or 12) <= 10
    knowledge_facts = knowledge_facts or []

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
        "Дебетовая карта / кэшбэк": "Проверю условия по дебетовой карте и поясню, как в вашем случае работают категории и начисление кэшбэка.",
        "Дебетовая карта / переводы и лимиты": "Проверю правила по дебетовой карте и подскажу, как в вашем случае работают переводы, лимиты или комиссии.",
        "Вклад / проценты": "Проверю условия вклада и поясню, как считаются проценты и от чего зависит итоговый доход.",
        "Вклад / пополнение и закрытие": "Проверю правила по вкладу и поясню, как здесь работают пополнение, досрочное закрытие или снятие средств.",
        "Накопительный счет / проценты": "Проверю условия по накопительному счету и поясню, как ставка и остаток влияют на начисление процентов.",
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

    facts_part = ""
    if knowledge_facts:
        selected = knowledge_facts[:1] if short else knowledge_facts[:2]
        facts_part = " По правилам продукта: " + " ".join(selected)

    draft = f"{opening} {body}{follow_up}{facts_part}".strip()
    if short:
        draft = draft.replace("Давайте быстро разберемся. ", "")
    return " ".join(draft.split())
