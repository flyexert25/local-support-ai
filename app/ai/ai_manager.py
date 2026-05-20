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
    ) -> str:
        if self.settings.values.network_disabled:
            raise LocalNetworkError("Сетевой доступ полностью отключен. Ollama localhost недоступен.")
        if not model:
            raise ValueError("Не выбрана локальная модель Ollama.")
        prompt = self._build_prompt(customer_text, ocr_text, style_prompt, quality_rules)
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.settings.values.temperature,
                "num_predict": self.settings.values.max_tokens,
            },
        }
        device = getattr(self.settings.values, "generation_device", "auto")
        if device == "cpu":
            payload["options"]["num_gpu"] = 0
        elif device == "gpu":
            payload["options"]["num_gpu"] = 999
        if image_base64:
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
    def _build_prompt(customer_text: str, ocr_text: str, style_prompt: str, quality_rules: str) -> str:
        return (
            "Ты локальный помощник сотрудника поддержки. Никаких внешних API, никаких упоминаний AI.\n"
            "Задача: по сообщению и/или тексту со скриншота написать один готовый ответ.\n\n"
            "Правила ответа:\n"
            "- пиши естественно, как живой сотрудник;\n"
            "- не используй чрезмерно официальные обращения;\n"
            "- не добавляй выдуманные факты;\n"
            "- если данных не хватает, задай короткий уточняющий вопрос;\n"
            "- не объясняй свои рассуждения, верни только текст ответа;\n"
            "- сохраняй спокойный дружелюбный тон;\n"
            "- даже если пользователь пишет резко, грубо или агрессивно, не зеркаль этот тон;\n"
            "- не используй сленг, насмешку, пассивную агрессию, хамство, сарказм и фразы вроде «досвидос», «мне неинтересно», «отвали»;\n"
            "- если пользователь хочет прекратить диалог, сформулируй это нейтрально и уважительно.\n\n"
            f"{style_prompt}\n\n"
            "Локальные правила качества, собранные из прошлых исправлений:\n"
            f"{quality_rules or '- пока нет накопленных правил'}\n\n"
            "Сообщение, вставленное пользователем:\n"
            f"{customer_text.strip() or '[нет текстового сообщения]'}\n\n"
            "Текст, распознанный со скриншота:\n"
            f"{ocr_text.strip() or '[OCR-текст отсутствует]'}\n\n"
            "Сформируй финальный ответ:"
        )
