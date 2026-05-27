from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import requests

from app.core.settings_manager import SettingsManager


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"


class BackendUnavailableError(RuntimeError):
    """Raised when the local FastAPI backend is unavailable."""


class LocalBackendSession(requests.Session):
    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in LOCAL_HOSTS:
            raise BackendUnavailableError("FastAPI backend разрешён только через localhost.")
        return super().request(method, url, **kwargs)


class BackendClient:
    def __init__(self, settings: SettingsManager, base_url: str = DEFAULT_BACKEND_URL) -> None:
        self.settings = settings
        self.base_url = base_url.rstrip("/")
        self.session = LocalBackendSession()

    def analyze_request(
        self,
        customer_text: str,
        ocr_text: str = "",
        selected_style: str | None = None,
    ) -> dict[str, Any]:
        if self.settings.values.network_disabled:
            raise BackendUnavailableError("Сетевой доступ полностью отключён в настройках.")

        payload = {
            "customer_text": customer_text,
            "ocr_text": ocr_text or None,
            "selected_style": selected_style,
        }
        try:
            response = self.session.post(
                f"{self.base_url}/analyze-request",
                json=payload,
                timeout=12,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise BackendUnavailableError(f"FastAPI backend недоступен: {exc}") from exc
        except ValueError as exc:
            raise BackendUnavailableError("FastAPI backend вернул некорректный JSON.") from exc

        if not isinstance(data, dict):
            raise BackendUnavailableError("FastAPI backend вернул неожиданный формат ответа.")
        return data

    def generate_preview(
        self,
        customer_text: str,
        ocr_text: str = "",
        selected_style: str | None = None,
    ) -> dict[str, Any]:
        if self.settings.values.network_disabled:
            raise BackendUnavailableError("Сетевой доступ полностью отключён в настройках.")

        payload = {
            "customer_text": customer_text,
            "ocr_text": ocr_text or None,
            "selected_style": selected_style,
        }
        try:
            response = self.session.post(
                f"{self.base_url}/generate-preview",
                json=payload,
                timeout=12,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise BackendUnavailableError(f"FastAPI backend недоступен: {exc}") from exc
        except ValueError as exc:
            raise BackendUnavailableError("FastAPI backend вернул некорректный JSON.") from exc

        if not isinstance(data, dict):
            raise BackendUnavailableError("FastAPI backend вернул неожиданный формат ответа.")
        return data

    def generate_final(
        self,
        customer_text: str,
        ocr_text: str = "",
        selected_style: str | None = None,
        model: str | None = None,
        image_base64: str | None = None,
    ) -> dict[str, Any]:
        if self.settings.values.network_disabled:
            raise BackendUnavailableError("Сетевой доступ полностью отключён в настройках.")

        payload = {
            "customer_text": customer_text,
            "ocr_text": ocr_text or None,
            "selected_style": selected_style,
            "model": model,
            "image_base64": image_base64,
        }
        try:
            response = self.session.post(
                f"{self.base_url}/generate-final",
                json=payload,
                timeout=180,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise BackendUnavailableError(f"FastAPI backend недоступен: {exc}") from exc
        except ValueError as exc:
            raise BackendUnavailableError("FastAPI backend вернул некорректный JSON.") from exc

        if not isinstance(data, dict):
            raise BackendUnavailableError("FastAPI backend вернул неожиданный формат ответа.")
        return data
