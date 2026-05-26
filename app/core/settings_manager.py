from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from app.utils.paths import user_data_dir


@dataclass
class AppSettings:
    ollama_url: str = "http://localhost:11434"
    preferred_model: str = ""
    processing_mode: str = "vision_auto"
    use_ocr: bool = True
    ocr_engine: str = "easyocr"
    ocr_languages: tuple[str, ...] = ("ru", "en")
    selected_style_id: int | None = None
    theme: str = "dark"
    expert_mode: bool = False
    always_on_top: bool = False
    compact_mode: bool = False
    network_disabled: bool = False
    generation_device: str = "auto"
    temperature: float = 0.35
    max_tokens: int = 900


class SettingsManager:
    def __init__(self) -> None:
        self.data_dir = user_data_dir()
        self.settings_path = self.data_dir / "settings.json"
        self.database_path = self.data_dir / "local_support_ai.sqlite3"
        self._settings = self._load()

    @property
    def values(self) -> AppSettings:
        return self._settings

    def _load(self) -> AppSettings:
        if not self.settings_path.exists():
            settings = AppSettings()
            self._write(settings)
            return settings
        try:
            payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
            if isinstance(payload.get("ocr_languages"), list):
                payload["ocr_languages"] = tuple(payload["ocr_languages"])
            return AppSettings(**{**asdict(AppSettings()), **payload})
        except Exception:
            backup = self.settings_path.with_suffix(".broken.json")
            self.settings_path.replace(backup)
            settings = AppSettings()
            self._write(settings)
            return settings

    def _write(self, settings: AppSettings) -> None:
        payload = asdict(settings)
        payload["ocr_languages"] = list(settings.ocr_languages)
        self.settings_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def save(self) -> None:
        self._write(self._settings)

    def update(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if not hasattr(self._settings, key):
                raise KeyError(f"Unknown setting: {key}")
            setattr(self._settings, key, value)
        self.save()

    def export_path(self, filename: str) -> Path:
        path = self.data_dir / "exports"
        path.mkdir(parents=True, exist_ok=True)
        return path / filename
