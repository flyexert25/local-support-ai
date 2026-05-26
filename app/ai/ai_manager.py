from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

from app.core.settings_manager import SettingsManager


SUPPORTED_VISION_MODELS = ("qwen2.5vl", "llava", "minicpm-v")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass
class OllamaStatus:
    connected: bool
    installed_models: list[str]
    supported_models: list[str]
    message: str


class LocalNetworkError(RuntimeError):
    """Raised when a request tries to leave the local machine."""


class LocalOnlySession(requests.Session):
    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in LOCAL_HOSTS:
            raise LocalNetworkError("Разрешены только локальные подключения к localhost.")
        return super().request(method, url, **kwargs)


class AIManager:
    FORBIDDEN_REPLY_PATTERNS = (
        r"\bдосвидос\b",
        r"\bпохер\b",
        r"\bпофиг\b",
        r"\bхрен\b",
        r"\bнах\b",
        r"\bидиот\b",
        r"\bтуп",
        r"\bбред\b",
        r"\bзаткни",
        r"\bнеинтересн\w*\b",
        r"\bотвали\b",
        r"\bвали\b",
    )

    def __init__(self, settings: SettingsManager) -> None:
        self.settings = settings
        self.session = LocalOnlySession()

    @property
    def base_url(self) -> str:
        return self.settings.values.ollama_url.rstrip("/")

    def check_status(self) -> OllamaStatus:
        if self.settings.values.network_disabled:
            return OllamaStatus(False, [], [], "Сетевой доступ полностью отключен в настройках.")
        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=2.5)
            response.raise_for_status()
            payload = response.json()
            installed = [item.get("name", "") for item in payload.get("models", []) if item.get("name")]
            supported = [name for name in installed if self.is_supported_vision_model(name)]
            if not supported:
                return OllamaStatus(
                    True,
                    installed,
                    [],
                    "Ollama подключен, но vision-модель не найдена.",
                )
            return OllamaStatus(True, installed, supported, "Локальная модель подключена.")
        except (requests.RequestException, LocalNetworkError, json.JSONDecodeError) as exc:
            return OllamaStatus(False, [], [], f"Ollama недоступен: {exc}")

    def generate_reply(
        self,
        customer_text: str,
        ocr_text: str,
        style_prompt: str,
        quality_rules: str,
        model: str,
        image_base64: str | None = None,
        topic_hint: str | None = None,
        knowledge_facts: list[str] | None = None,
    ) -> str:
        if self.settings.values.network_disabled:
            raise LocalNetworkError("Сетевой доступ полностью отключен. Ollama localhost недоступен.")
        if not model:
            raise ValueError("Не выбрана локальная модель Ollama.")
        prompt = self._build_prompt(
            customer_text,
            ocr_text,
            style_prompt,
            quality_rules,
            topic_hint=topic_hint,
            knowledge_facts=knowledge_facts or [],
        )
        use_image = self._should_attach_image(image_base64, ocr_text)
        num_predict = self._estimate_num_predict(customer_text, ocr_text, use_image)
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.settings.values.temperature,
                "num_predict": num_predict,
            },
        }
        device = getattr(self.settings.values, "generation_device", "auto")
        if device == "cpu":
            payload["options"]["num_gpu"] = 0
        elif device == "gpu":
            payload["options"]["num_gpu"] = 999
        if use_image and image_base64:
            payload["images"] = [image_base64]
        response = self.session.post(f"{self.base_url}/api/generate", json=payload, timeout=180)
        response.raise_for_status()
        data = response.json()
        text = str(data.get("response", "")).strip()
        if not text:
            raise RuntimeError("Модель вернула пустой ответ.")
        return self._cleanup_reply(text)

    @staticmethod
    def is_supported_vision_model(model_name: str) -> bool:
        normalized = model_name.split(":")[0].lower()
        return any(normalized.startswith(prefix) for prefix in SUPPORTED_VISION_MODELS)

    @staticmethod
    def _cleanup_reply(text: str) -> str:
        prefixes = ["Готовый ответ:", "Ответ:", "Можно ответить так:"]
        cleaned = text.strip()
        for prefix in prefixes:
            if cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix) :].strip()
        cleaned = AIManager._sanitize_reply(cleaned)
        return cleaned

    @staticmethod
    def _sanitize_reply(text: str) -> str:
        cleaned = " ".join(text.split()).strip()
        lowered = cleaned.lower()
        if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in AIManager.FORBIDDEN_REPLY_PATTERNS):
            sentences = re.split(r"(?<=[.!?])\s+", cleaned)
            safe_sentences: list[str] = []
            for sentence in sentences:
                lowered_sentence = sentence.lower()
                if any(re.search(pattern, lowered_sentence, re.IGNORECASE) for pattern in AIManager.FORBIDDEN_REPLY_PATTERNS):
                    continue
                safe_sentences.append(sentence.strip())
            cleaned = " ".join(part for part in safe_sentences if part).strip()
            if not cleaned:
                cleaned = "Понял вас. Давайте решим вопрос спокойно и по сути."
        return cleaned

    @staticmethod
    def _build_prompt(
        customer_text: str,
        ocr_text: str,
        style_prompt: str,
        quality_rules: str,
        *,
        topic_hint: str | None,
        knowledge_facts: list[str],
    ) -> str:
        customer_block = AIManager._normalize_context_text(customer_text, 650) or "[нет текста клиента]"
        ocr_block = AIManager._normalize_context_text(ocr_text, 750)
        if ocr_block and customer_block != "[нет текста клиента]" and ocr_block.lower() == customer_block.lower():
            ocr_block = ""

        rules_block = AIManager._compact_rules_block(quality_rules)
        knowledge_block = AIManager._build_knowledge_block(topic_hint, knowledge_facts)
        return (
            "Ты пишешь ответ клиенту от лица живого сотрудника поддержки.\n"
            "Пиши спокойно, по-человечески и по сути. Не упоминай ИИ, шаблоны или внутренние правила.\n"
            "Если данных мало, не выдумывай детали и не обещай то, чего нет в сообщении.\n\n"
            f"{style_prompt}\n\n"
            "Уточнения по качеству ответа:\n"
            f"{rules_block}\n\n"
            f"{knowledge_block}"
            "Сообщение клиента:\n"
            f"{customer_block}\n\n"
            "OCR-контекст:\n"
            f"{ocr_block or '[нет OCR-контекста]'}\n\n"
            "Готовый ответ:"
        )

    @staticmethod
    def _should_attach_image(image_base64: str | None, ocr_text: str) -> bool:
        if not image_base64:
            return False
        normalized_ocr = AIManager._normalize_context_text(ocr_text, 1200)
        return len(normalized_ocr) < 120

    def _estimate_num_predict(self, customer_text: str, ocr_text: str, has_image: bool) -> int:
        configured_max = max(int(self.settings.values.max_tokens or 0), 120)
        total_chars = len(customer_text.strip()) + len(ocr_text.strip())

        if has_image:
            limit = 420
        elif total_chars <= 180:
            limit = 180
        elif total_chars <= 500:
            limit = 260
        elif total_chars <= 1200:
            limit = 340
        else:
            limit = 420
        return min(configured_max, limit)

    @staticmethod
    def _normalize_context_text(text: str, max_chars: int) -> str:
        cleaned = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        cleaned = cleaned.strip()
        if len(cleaned) <= max_chars:
            return cleaned
        truncated = cleaned[:max_chars].rsplit(" ", 1)[0].strip()
        return (truncated or cleaned[:max_chars]).strip() + "..."

    @staticmethod
    def _compact_rules_block(quality_rules: str) -> str:
        lines = [line.strip() for line in quality_rules.splitlines() if line.strip()]
        if not lines:
            return "- Пиши ясно и без лишнего официоза."
        return "\n".join(lines[:3])

    @staticmethod
    def _build_knowledge_block(topic_hint: str | None, knowledge_facts: list[str]) -> str:
        clean_facts = [fact.strip() for fact in knowledge_facts if fact and fact.strip()][:2]
        if not topic_hint and not clean_facts:
            return ""

        lines = ["Локальная проверка контекста:"]
        if topic_hint:
            lines.append(f"- Проверенная тема: {topic_hint}")
        for fact in clean_facts:
            lines.append(f"- Факт: {fact}")
        lines.append("")
        return "\n".join(lines)
