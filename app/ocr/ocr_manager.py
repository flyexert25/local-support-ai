from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path

import cv2
import numpy as np

from app.core.privacy_guard import allow_hosts_temporarily
from app.core.settings_manager import SettingsManager


@dataclass
class OCRStatus:
    ready: bool
    engine: str
    message: str


class OCRManager:
    def __init__(self, settings: SettingsManager) -> None:
        self.settings = settings
        self._reader = None
        self._engine = settings.values.ocr_engine.lower()

    def status(self) -> OCRStatus:
        module_name = "paddleocr" if self._engine == "paddleocr" else "easyocr"
        if find_spec(module_name) is None:
            return OCRStatus(False, self._engine, f"Пакет {module_name} не установлен.")
        return OCRStatus(True, self._engine, "OCR пакет установлен. Модели используются локально.")

    def recognize(self, image_path: Path) -> str:
        if not image_path.exists():
            raise FileNotFoundError(f"Файл не найден: {image_path}")
        reader = self._ensure_reader()
        image = self._load_image(image_path)
        if self._engine == "paddleocr":
            result = reader.ocr(image, cls=True)
            lines: list[str] = []
            for block in result or []:
                for item in block or []:
                    if len(item) >= 2 and item[1]:
                        lines.append(str(item[1][0]))
            return "\n".join(lines).strip()
        results = reader.readtext(image, detail=0, paragraph=True)
        return "\n".join(map(str, results)).strip()

    @staticmethod
    def _load_image(image_path: Path):
        buffer = np.frombuffer(image_path.read_bytes(), dtype=np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"Не удалось прочитать изображение: {image_path}")
        return image

    def _ensure_reader(self):
        if self._reader is not None:
            return self._reader
        languages = list(self.settings.values.ocr_languages)
        self._engine = self.settings.values.ocr_engine.lower()
        if self._engine == "paddleocr":
            from paddleocr import PaddleOCR

            lang = "ru" if "ru" in languages else "en"
            self._reader = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
            return self._reader
        import easyocr

        with allow_hosts_temporarily(
            "github.com",
            "githubusercontent.com",
            "raw.githubusercontent.com",
            "objects.githubusercontent.com",
            "release-assets.githubusercontent.com",
        ):
            self._reader = easyocr.Reader(languages, gpu=False, verbose=False, download_enabled=True)
        return self._reader
