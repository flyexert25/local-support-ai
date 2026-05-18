from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from app.ai.ai_manager import AIManager
from app.ocr.ocr_manager import OCRManager


class OCRWorker(QObject):
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, ocr_manager: OCRManager, image_path: Path) -> None:
        super().__init__()
        self.ocr_manager = ocr_manager
        self.image_path = image_path

    def run(self) -> None:
        try:
            self.finished.emit(self.ocr_manager.recognize(self.image_path))
        except Exception as exc:
            self.failed.emit(str(exc))


class GenerateWorker(QObject):
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        ai_manager: AIManager,
        customer_text: str,
        ocr_text: str,
        style_prompt: str,
        model: str,
        image_base64: str | None,
    ) -> None:
        super().__init__()
        self.ai_manager = ai_manager
        self.customer_text = customer_text
        self.ocr_text = ocr_text
        self.style_prompt = style_prompt
        self.model = model
        self.image_base64 = image_base64

    def run(self) -> None:
        try:
            self.finished.emit(
                self.ai_manager.generate_reply(
                    customer_text=self.customer_text,
                    ocr_text=self.ocr_text,
                    style_prompt=self.style_prompt,
                    model=self.model,
                    image_base64=self.image_base64,
                )
            )
        except Exception as exc:
            self.failed.emit(str(exc))


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
