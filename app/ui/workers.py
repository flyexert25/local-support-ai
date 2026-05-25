from __future__ import annotations

from time import perf_counter
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from app.ai.ai_manager import AIManager
from app.core.backend_client import BackendClient
from app.ocr.ocr_manager import OCRManager


class OCRWorker(QObject):
    finished = pyqtSignal(str, float)
    failed = pyqtSignal(str, float)

    def __init__(self, ocr_manager: OCRManager, image_path: Path) -> None:
        super().__init__()
        self.ocr_manager = ocr_manager
        self.image_path = image_path

    def run(self) -> None:
        started_at = perf_counter()
        try:
            text = self.ocr_manager.recognize(self.image_path)
            elapsed_ms = (perf_counter() - started_at) * 1000
            self.finished.emit(text, elapsed_ms)
        except Exception as exc:
            elapsed_ms = (perf_counter() - started_at) * 1000
            self.failed.emit(str(exc), elapsed_ms)


class GenerateWorker(QObject):
    finished = pyqtSignal(str, float)
    failed = pyqtSignal(str)

    def __init__(
        self,
        ai_manager: AIManager,
        customer_text: str,
        ocr_text: str,
        style_prompt: str,
        quality_rules: str,
        model: str,
        image_base64: str | None,
    ) -> None:
        super().__init__()
        self.ai_manager = ai_manager
        self.customer_text = customer_text
        self.ocr_text = ocr_text
        self.style_prompt = style_prompt
        self.quality_rules = quality_rules
        self.model = model
        self.image_base64 = image_base64

    def run(self) -> None:
        try:
            started_at = perf_counter()
            reply = self.ai_manager.generate_reply(
                customer_text=self.customer_text,
                ocr_text=self.ocr_text,
                style_prompt=self.style_prompt,
                quality_rules=self.quality_rules,
                model=self.model,
                image_base64=self.image_base64,
            )
            elapsed_ms = (perf_counter() - started_at) * 1000
            self.finished.emit(reply, elapsed_ms)
        except Exception as exc:
            self.failed.emit(str(exc))


class BackendAnalyzeWorker(QObject):
    finished = pyqtSignal(dict, float)
    failed = pyqtSignal(str, float)

    def __init__(
        self,
        backend_client: BackendClient,
        customer_text: str,
        ocr_text: str,
        selected_style: str | None,
    ) -> None:
        super().__init__()
        self.backend_client = backend_client
        self.customer_text = customer_text
        self.ocr_text = ocr_text
        self.selected_style = selected_style

    def run(self) -> None:
        started_at = perf_counter()
        try:
            payload = self.backend_client.analyze_request(
                customer_text=self.customer_text,
                ocr_text=self.ocr_text,
                selected_style=self.selected_style,
            )
            elapsed_ms = (perf_counter() - started_at) * 1000
            self.finished.emit(payload, elapsed_ms)
        except Exception as exc:
            elapsed_ms = (perf_counter() - started_at) * 1000
            self.failed.emit(str(exc), elapsed_ms)


class BackendPreviewWorker(QObject):
    finished = pyqtSignal(dict, float)
    failed = pyqtSignal(str, float)

    def __init__(
        self,
        backend_client: BackendClient,
        customer_text: str,
        ocr_text: str,
        selected_style: str | None,
    ) -> None:
        super().__init__()
        self.backend_client = backend_client
        self.customer_text = customer_text
        self.ocr_text = ocr_text
        self.selected_style = selected_style

    def run(self) -> None:
        started_at = perf_counter()
        try:
            payload = self.backend_client.generate_preview(
                customer_text=self.customer_text,
                ocr_text=self.ocr_text,
                selected_style=self.selected_style,
            )
            elapsed_ms = (perf_counter() - started_at) * 1000
            self.finished.emit(payload, elapsed_ms)
        except Exception as exc:
            elapsed_ms = (perf_counter() - started_at) * 1000
            self.failed.emit(str(exc), elapsed_ms)


def start_worker(worker: QObject) -> QThread:
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.failed.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    worker.failed.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread
