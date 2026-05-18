from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PyQt6.QtGui import QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.ai.ai_manager import AIManager
from app.core.case_analyzer import CaseAnalyzer
from app.core.privacy_guard import set_allow_localhost
from app.core.settings_manager import SettingsManager
from app.ocr.ocr_manager import OCRManager
from app.storage.database import Database
from app.styles.style_manager import StyleManager
from app.ui.settings_dialog import SettingsDialog
from app.ui.theme import apply_theme
from app.ui.widgets import ScreenshotDropZone, StatusPill
from app.ui.workers import GenerateWorker, OCRWorker, start_worker
from app.utils.image_utils import image_path_to_base64, load_pixmap, qimage_to_base64, qimage_to_png_bytes


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: SettingsManager,
        database: Database,
        style_manager: StyleManager,
        ai_manager: AIManager,
        ocr_manager: OCRManager,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.database = database
        self.style_manager = style_manager
        self.ai_manager = ai_manager
        self.ocr_manager = ocr_manager
        self.case_analyzer = CaseAnalyzer()
        self.current_image_path: Path | None = None
        self.current_clipboard_image_base64: str | None = None
        self.threads = []
        self.workers = []

        self.setWindowTitle("Local Support AI")
        icon_path = Path(__file__).resolve().parents[2] / "assets" / "app_icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1280, 780)
        self.setMinimumSize(980, 620)
        self.setAcceptDrops(True)
        self._build_ui()
        self._bind_shortcuts()
        self._apply_window_settings()
        self.refresh_status()
        self.apply_processing_mode()

    def _build_ui(self) -> None:
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_top_bar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([520, 760])
        outer.addWidget(splitter, 1)

        self.status_message = QLabel("Готов к локальной работе")
        self.status_message.setObjectName("Subtle")
        self.status_message.setContentsMargins(16, 8, 16, 8)
        outer.addWidget(self.status_message)
        self.setCentralWidget(root)

    def _build_top_bar(self) -> QWidget:
        top = QWidget()
        top.setObjectName("TopBar")
        layout = QHBoxLayout(top)
        layout.setContentsMargins(16, 12, 16, 12)
        title_box = QVBoxLayout()
        title = QLabel("Local Support AI")
        title.setObjectName("Title")
        subtitle = QLabel("Offline-first генератор ответов клиентам")
        subtitle.setObjectName("Subtle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        self.local_pill = StatusPill("Локальный режим")
        self.ocr_pill = StatusPill("OCR готов")
        self.model_pill = StatusPill("Qwen подключён")
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(220)
        self.model_combo.currentTextChanged.connect(self._model_changed)

        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.clicked.connect(self.refresh_status)
        self.settings_button = QPushButton("Настройки")
        self.settings_button.clicked.connect(self.open_settings)

        layout.addLayout(title_box, 1)
        layout.addWidget(self.local_pill)
        layout.addWidget(self.ocr_pill)
        layout.addWidget(self.model_pill)
        layout.addWidget(self.model_combo)
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.settings_button)
        return top

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 8, 16)
        layout.setSpacing(12)

        self.drop_zone = ScreenshotDropZone()
        self.drop_zone.imageDropped.connect(self.load_image)
        self.screenshot_panel = self._wrap_panel("Превью скриншота", self.drop_zone)
        layout.addWidget(self.screenshot_panel, 2)

        self.customer_text = QPlainTextEdit()
        self.customer_text.setPlaceholderText("Вставьте сообщение клиента или фрагмент переписки...")
        self.customer_text.textChanged.connect(self.update_case_summary)
        layout.addWidget(self._wrap_panel("Сообщение клиента", self.customer_text), 1)

        self.case_summary = QLabel("Признаки обращения появятся после ввода текста или OCR.")
        self.case_summary.setObjectName("Subtle")
        self.case_summary.setWordWrap(True)
        layout.addWidget(self._wrap_panel("Аналитика обращения", self.case_summary), 0)

        buttons = QGridLayout()
        self.load_button = QPushButton("Загрузить скриншот")
        self.load_button.clicked.connect(self.open_image_dialog)
        self.analyze_button = QPushButton("Анализировать")
        self.analyze_button.setObjectName("Primary")
        self.analyze_button.clicked.connect(self.analyze_screenshot)
        self.clear_button = QPushButton("Очистить")
        self.clear_button.clicked.connect(self.clear_all)
        buttons.addWidget(self.load_button, 0, 0)
        buttons.addWidget(self.analyze_button, 0, 1)
        buttons.addWidget(self.clear_button, 0, 2)
        layout.addLayout(buttons)
        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 16, 16, 16)
        layout.setSpacing(12)

        self.ocr_text = QPlainTextEdit()
        self.ocr_text.setPlaceholderText("Здесь появится распознанный текст со скриншота. Можно редактировать вручную.")
        self.ocr_text.textChanged.connect(self.update_case_summary)
        layout.addWidget(self._wrap_panel("Распознанный текст", self.ocr_text), 1)

        self.response_text = QPlainTextEdit()
        self.response_text.setPlaceholderText("Готовый ответ клиенту появится здесь.")
        layout.addWidget(self._wrap_panel("Сгенерированный ответ", self.response_text), 1)

        buttons = QHBoxLayout()
        self.generate_button = QPushButton("Сгенерировать ответ")
        self.generate_button.setObjectName("Primary")
        self.generate_button.clicked.connect(self.generate_reply)
        self.save_to_style_button = QPushButton("Сохранить в стиль")
        self.save_to_style_button.clicked.connect(self.save_reply_to_style)
        self.copy_button = QPushButton("Копировать")
        self.copy_button.clicked.connect(self.copy_reply)
        buttons.addStretch(1)
        buttons.addWidget(self.generate_button)
        buttons.addWidget(self.save_to_style_button)
        buttons.addWidget(self.copy_button)
        layout.addLayout(buttons)
        return panel

    @staticmethod
    def _wrap_panel(title: str, child: QWidget) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        label = QLabel(title)
        label.setStyleSheet("font-weight: 700;")
        layout.addWidget(label)
        layout.addWidget(child, 1)
        return frame

    def _bind_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.open_image_dialog)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.generate_reply)
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.clear_all)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, activated=self.copy_reply)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self.open_settings)

    def refresh_status(self) -> None:
        self.local_pill.set_state("Локальный режим", not self.settings.values.network_disabled)
        if self.settings.values.network_disabled:
            self.local_pill.set_state("Сеть отключена полностью", True)

        if self.settings.values.processing_mode == "text_only":
            self.ocr_pill.set_state("OCR скрыт", True)
            self.analyze_button.setEnabled(False)
            self.analyze_button.setToolTip("В режиме «Только текст» скриншоты и OCR скрыты")
        elif self.settings.values.use_ocr:
            ocr_status = self.ocr_manager.status()
            self.ocr_pill.set_state("OCR готов" if ocr_status.ready else "OCR не готов", ocr_status.ready)
            self.analyze_button.setEnabled(True)
            self.analyze_button.setToolTip("Распознать текст со скриншота локально")
        else:
            self.ocr_pill.set_state("OCR выключен", True)
            self.analyze_button.setEnabled(False)
            self.analyze_button.setToolTip("Включите OCR в настройках, если нужен распознанный текст")

        status = self.ai_manager.check_status()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        models = status.supported_models or status.installed_models
        self.model_combo.addItems(models)
        preferred = self.settings.values.preferred_model
        if preferred and preferred in models:
            self.model_combo.setCurrentText(preferred)
        elif status.supported_models:
            self.model_combo.setCurrentText(status.supported_models[0])
            self.settings.update(preferred_model=status.supported_models[0])
        self.model_combo.blockSignals(False)

        selected_model = self.model_combo.currentText().lower()
        connected_label = "Qwen подключён" if "qwen" in selected_model else "Модель подключена"
        self.model_pill.set_state(connected_label if status.supported_models else "Модель не найдена", bool(status.supported_models))
        if not status.supported_models:
            self._set_status(status.message + " Установка: ollama pull qwen2.5vl")
        else:
            self._set_status(status.message)

    def open_image_dialog(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите скриншот",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if filename:
            self.load_image(Path(filename))

    def load_image(self, path: Path) -> None:
        if self.settings.values.processing_mode == "text_only":
            QMessageBox.information(
                self,
                "Режим только текста",
                "Сейчас включён режим «Только текст». Включите режим со скриншотами в настройках, если хотите использовать изображение.",
            )
            return
        pixmap = load_pixmap(path)
        if pixmap is None:
            QMessageBox.warning(self, "Не удалось открыть изображение", str(path))
            return
        self.current_image_path = path
        self.current_clipboard_image_base64 = None
        self.drop_zone.set_pixmap(pixmap)
        self._set_status(f"Скриншот загружен: {path.name}")

    def analyze_screenshot(self) -> None:
        if self.settings.values.processing_mode == "text_only":
            QMessageBox.information(self, "Режим только текста", "В этом режиме скриншоты и OCR не используются.")
            return
        if not self.settings.values.use_ocr:
            QMessageBox.information(self, "OCR выключен", "Включите OCR в настройках, если хотите распознавать текст.")
            return
        if not self.current_image_path:
            QMessageBox.information(self, "Нет скриншота", "Загрузите или вставьте скриншот перед анализом.")
            return
        self._set_busy(True)
        worker = OCRWorker(self.ocr_manager, self.current_image_path)
        worker.finished.connect(self._ocr_finished)
        worker.failed.connect(self._worker_failed)
        worker.finished.connect(lambda: self._forget_worker(worker))
        worker.failed.connect(lambda _: self._forget_worker(worker))
        self.workers.append(worker)
        self.threads.append(start_worker(worker))
        self._set_status("OCR распознает текст локально...")

    def generate_reply(self) -> None:
        customer = self.customer_text.toPlainText().strip()
        ocr = self.ocr_text.toPlainText().strip()
        text_only = self.settings.values.processing_mode == "text_only"
        has_image = bool(self.current_image_path or self.current_clipboard_image_base64) and not text_only
        if not customer and not ocr and not has_image:
            QMessageBox.information(self, "Нет контекста", "Добавьте сообщение клиента или скриншот.")
            return

        model = self.model_combo.currentText().strip() or self.settings.values.preferred_model
        style = self.style_manager.get_style(self.settings.values.selected_style_id)
        style_prompt = self.style_manager.build_style_prompt(style)
        style_id = style.id if style else None
        style_profile = style.profile if style else None
        image_base64 = None if text_only else self.current_clipboard_image_base64
        if self.current_image_path and not text_only:
            image_base64 = image_path_to_base64(self.current_image_path)

        self._set_busy(True)
        worker = GenerateWorker(self.ai_manager, customer, ocr, style_prompt, model, image_base64)
        worker.finished.connect(lambda text: self._generation_finished(text, model, style_id, style_profile))
        worker.failed.connect(self._worker_failed)
        worker.finished.connect(lambda _: self._forget_worker(worker))
        worker.failed.connect(lambda _: self._forget_worker(worker))
        self.workers.append(worker)
        self.threads.append(start_worker(worker))
        self._set_status("Локальная модель генерирует ответ...")

    def copy_reply(self) -> None:
        QApplication.clipboard().setText(self.response_text.toPlainText())
        self._set_status("Ответ скопирован в буфер обмена")

    def save_reply_to_style(self) -> None:
        text = self.response_text.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Ответ пустой", "Сначала сгенерируйте или напишите ответ.")
            return
        style = self.style_manager.get_style(self.settings.values.selected_style_id)
        if not style:
            QMessageBox.warning(self, "Стиль не выбран", "Создайте или выберите стиль в настройках.")
            return
        try:
            updated = self.style_manager.append_example(style.id, text)
            self.settings.update(selected_style_id=updated.id)
            self._set_status(f"Ответ сохранён в стиль: {updated.name}")
        except Exception as exc:
            QMessageBox.warning(self, "Не удалось сохранить в стиль", str(exc))

    def clear_all(self) -> None:
        self.customer_text.clear()
        self.ocr_text.clear()
        self.response_text.clear()
        self.current_image_path = None
        self.current_clipboard_image_base64 = None
        self.drop_zone.set_pixmap(None)
        self._set_status("Очищено")

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self.style_manager, self.database, self)
        dialog.settingsChanged.connect(self._settings_changed)
        dialog.exec()

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.StandardKey.Paste):
            clipboard = QApplication.clipboard()
            mime = clipboard.mimeData()
            if mime.hasImage():
                if self.settings.values.processing_mode == "text_only":
                    self._set_status("Скриншот не вставлен: включён режим «Только текст»")
                    return
                image = clipboard.image()
                self.current_clipboard_image_base64 = qimage_to_base64(image)
                temp_path = self.settings.data_dir / "clipboard_image.png"
                temp_path.write_bytes(qimage_to_png_bytes(image))
                self.current_image_path = temp_path
                self.drop_zone.set_pixmap(load_pixmap(temp_path))
                self._set_status("Скриншот вставлен из буфера обмена")
                return
        super().keyPressEvent(event)

    def _ocr_finished(self, text: str) -> None:
        self.ocr_text.setPlainText(text or "")
        self._set_busy(False)
        self._set_status("OCR завершен" if text else "OCR завершен, текст не найден")

    def _generation_finished(
        self,
        text: str,
        model: str,
        style_id: int | None,
        style_profile: dict | None,
    ) -> None:
        try:
            self.response_text.setPlainText(text)
            analysis = self.case_analyzer.analyze(
                self.customer_text.toPlainText(),
                self.ocr_text.toPlainText(),
                style_profile=style_profile,
            )
            self.database.execute(
                """
                INSERT INTO conversations(
                    customer_text, ocr_text, response_text, model_name, style_id,
                    topic, signals_json, extracted_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.customer_text.toPlainText(),
                    self.ocr_text.toPlainText(),
                    text,
                    model,
                    style_id,
                    analysis.topic,
                    Database.encode_json({"signals": analysis.signals}),
                    Database.encode_json(analysis.extracted),
                ),
            )
            self.case_summary.setText(analysis.to_display_text())
            self._set_status("Ответ сгенерирован локально")
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка после генерации", str(exc))
            self._set_status(f"Ответ получен, но не удалось сохранить аналитику: {exc}")
        finally:
            self._set_busy(False)

    def _worker_failed(self, message: str) -> None:
        self._set_busy(False)
        QMessageBox.warning(self, "Ошибка", message)
        self._set_status(message)

    def _set_busy(self, busy: bool) -> None:
        for button in [self.load_button, self.generate_button, self.save_to_style_button, self.clear_button]:
            button.setEnabled(not busy)
        self.analyze_button.setEnabled(
            not busy
            and self.settings.values.use_ocr
            and self.settings.values.processing_mode != "text_only"
        )
        self.refresh_button.setEnabled(not busy)

    def apply_processing_mode(self) -> None:
        text_only = self.settings.values.processing_mode == "text_only"
        self.screenshot_panel.setVisible(not text_only)
        self.load_button.setVisible(not text_only)
        self.analyze_button.setVisible(not text_only)
        if text_only:
            self.current_image_path = None
            self.current_clipboard_image_base64 = None
            self.drop_zone.set_pixmap(None)
            self._set_status("Быстрый режим: генерация только по тексту")
        else:
            self._set_status("Режим со скриншотами: изображение используется, если оно загружено")

    def _set_status(self, message: str) -> None:
        self.status_message.setText(message)
        animation = QPropertyAnimation(self.status_message, b"maximumHeight", self)
        animation.setDuration(180)
        animation.setStartValue(24)
        animation.setEndValue(38)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _settings_changed(self) -> None:
        set_allow_localhost(not self.settings.values.network_disabled)
        app = QApplication.instance()
        if app:
            apply_theme(app, self.settings.values.theme)
        self._apply_window_settings()
        self.apply_processing_mode()
        self.refresh_status()

    def update_case_summary(self) -> None:
        text = self.customer_text.toPlainText().strip()
        ocr = self.ocr_text.toPlainText().strip()
        if not text and not ocr:
            self.case_summary.setText("Признаки обращения появятся после ввода текста или OCR.")
            return
        style = self.style_manager.get_style(self.settings.values.selected_style_id)
        analysis = self.case_analyzer.analyze(
            text,
            ocr,
            style_profile=style.profile if style else None,
        )
        self.case_summary.setText(analysis.to_display_text())

    def _forget_worker(self, worker) -> None:
        if worker in self.workers:
            self.workers.remove(worker)

    def _model_changed(self, model: str) -> None:
        if model:
            self.settings.update(preferred_model=model)

    def _apply_window_settings(self) -> None:
        flags = self.windowFlags()
        if self.settings.values.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        if self.settings.values.compact_mode:
            self.resize(980, 620)
        self.show()
