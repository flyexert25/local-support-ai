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
from app.core.backend_client import BackendClient
from app.core.case_analyzer import CaseAnalysis, CaseAnalyzer
from app.core.learning_manager import LearningManager
from app.core.privacy_guard import set_allow_localhost
from app.core.settings_manager import SettingsManager
from app.ocr.ocr_manager import OCRManager
from app.storage.database import Database
from app.styles.style_manager import StyleManager
from app.ui.settings_dialog import SettingsDialog
from app.ui.theme import apply_theme
from app.ui.widgets import CaseInsightPanel, ScreenshotDropZone, StatusPill
from app.ui.workers import BackendAnalyzeWorker, BackendPreviewWorker, GenerateWorker, OCRWorker, start_worker
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
        self.backend_client = BackendClient(settings)
        self.case_analyzer = CaseAnalyzer()
        self.learning_manager = LearningManager(database)
        self.current_image_path: Path | None = None
        self.current_clipboard_image_base64: str | None = None
        self.last_ocr_raw_text: str = ""
        self.last_generated_raw_response: str = ""
        self.last_generated_model: str = ""
        self.last_generated_style_id: int | None = None
        self.last_case_analysis: CaseAnalysis | None = None
        self.last_case_source: str = "Ожидание"
        self.stage_metrics: dict[str, float | None] = {
            "ocr_ms": None,
            "analyze_ms": None,
            "preview_ms": None,
            "generate_ms": None,
        }
        self._busy = False
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
        self.sla_message = QLabel()
        self.sla_message.setObjectName("Subtle")
        self.sla_message.setContentsMargins(16, 0, 16, 8)
        outer.addWidget(self.sla_message)
        self._update_sla_message()
        self.setCentralWidget(root)

    def _build_top_bar(self) -> QWidget:
        top = QWidget()
        top.setObjectName("TopBar")
        layout = QHBoxLayout(top)
        layout.setContentsMargins(16, 10, 16, 10)
        title_box = QVBoxLayout()
        title = QLabel("Local Support AI")
        title.setObjectName("Title")
        subtitle = QLabel("Offline-first генератор ответов по обращениям")
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
        self.customer_text.setPlaceholderText("Вставьте сообщение или фрагмент переписки...")
        self.customer_text.textChanged.connect(self.update_case_summary)
        layout.addWidget(self._wrap_panel("Сообщение", self.customer_text), 1)

        self.case_summary = CaseInsightPanel()
        layout.addWidget(self._wrap_panel("Аналитика обращения", self.case_summary), 0)

        self.topic_override_combo = QComboBox()
        self.topic_override_combo.addItems(self._available_topics())
        self.topic_override_combo.setEnabled(False)
        self.topic_override_save_button = QPushButton("Сохранить тему")
        self.topic_override_save_button.setObjectName("Tiny")
        self.topic_override_save_button.setEnabled(False)
        self.topic_override_save_button.clicked.connect(self.save_topic_correction)
        topic_override_body = QWidget()
        topic_override_layout = QHBoxLayout(topic_override_body)
        topic_override_layout.setContentsMargins(0, 0, 0, 0)
        topic_override_layout.setSpacing(8)
        topic_override_layout.addWidget(self.topic_override_combo, 1)
        topic_override_layout.addWidget(self.topic_override_save_button)
        self.topic_override_panel = self._wrap_panel("Коррекция темы", topic_override_body)
        self.topic_override_panel.setVisible(False)
        layout.addWidget(self.topic_override_panel, 0)

        buttons = QGridLayout()
        self.load_button = QPushButton("Загрузить скриншот")
        self.load_button.clicked.connect(self.open_image_dialog)
        self.analyze_button = QPushButton("Подготовить ответ")
        self.analyze_button.setObjectName("Secondary")
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
        self.ocr_feedback_correct_button = QPushButton("OCR верно")
        self.ocr_feedback_correct_button.setObjectName("Tiny")
        self.ocr_feedback_correct_button.clicked.connect(self.mark_ocr_correct)
        self.ocr_feedback_save_button = QPushButton("Сохранить исправленный текст")
        self.ocr_feedback_save_button.setObjectName("Tiny")
        self.ocr_feedback_save_button.clicked.connect(self.save_corrected_ocr_text)
        ocr_actions = QHBoxLayout()
        ocr_actions.addStretch(1)
        ocr_actions.addWidget(self.ocr_feedback_correct_button)
        ocr_actions.addWidget(self.ocr_feedback_save_button)
        ocr_panel_body = QWidget()
        ocr_panel_layout = QVBoxLayout(ocr_panel_body)
        ocr_panel_layout.setContentsMargins(0, 0, 0, 0)
        ocr_panel_layout.setSpacing(10)
        ocr_panel_layout.addWidget(self.ocr_text, 1)
        ocr_panel_layout.addLayout(ocr_actions)
        layout.addWidget(self._wrap_panel("Распознанный текст", ocr_panel_body), 1)
        self._set_ocr_feedback_enabled(False)

        self.response_text = QPlainTextEdit()
        self.response_text.setPlaceholderText("Готовый ответ появится здесь.")
        self.response_feedback_correct_button = QPushButton("Ответ верный")
        self.response_feedback_correct_button.setObjectName("Tiny")
        self.response_feedback_correct_button.clicked.connect(self.mark_response_correct)
        self.response_feedback_save_button = QPushButton("Сохранить исправленный ответ")
        self.response_feedback_save_button.setObjectName("Tiny")
        self.response_feedback_save_button.clicked.connect(self.save_corrected_response)
        response_actions = QHBoxLayout()
        response_actions.addStretch(1)
        response_actions.addWidget(self.response_feedback_correct_button)
        response_actions.addWidget(self.response_feedback_save_button)
        response_panel_body = QWidget()
        response_panel_layout = QVBoxLayout(response_panel_body)
        response_panel_layout.setContentsMargins(0, 0, 0, 0)
        response_panel_layout.setSpacing(10)
        response_panel_layout.addWidget(self.response_text, 1)
        response_panel_layout.addLayout(response_actions)
        layout.addWidget(self._wrap_panel("Сгенерированный ответ", response_panel_body), 1)
        self._set_response_feedback_enabled(False)

        buttons = QHBoxLayout()
        self.preview_button = QPushButton("Быстрый черновик")
        self.preview_button.setObjectName("Secondary")
        self.preview_button.clicked.connect(self.generate_preview)
        self.preview_button.setVisible(False)
        self.generate_button = QPushButton("Сгенерировать ответ")
        self.generate_button.setObjectName("Primary")
        self.generate_button.clicked.connect(self.generate_reply)
        self.save_to_style_button = QPushButton("Сохранить в стиль")
        self.save_to_style_button.clicked.connect(self.save_reply_to_style)
        self.copy_button = QPushButton("Копировать")
        self.copy_button.clicked.connect(self.copy_reply)
        buttons.addStretch(1)
        buttons.addWidget(self.preview_button)
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
        layout.setSpacing(8)
        label = QLabel(title)
        label.setObjectName("PanelTitle")
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

    def _available_topics(self) -> list[str]:
        topics = [
            "Общее обращение",
            "Проценты / кредит наличными",
            "Проценты / кредитная карта",
            "Проценты / кредит",
        ]
        topics.extend(topic for topic, _ in self.case_analyzer.TOPIC_RULES)
        seen: set[str] = set()
        result: list[str] = []
        for topic in topics:
            clean = topic.strip()
            key = clean.lower()
            if not clean or key in seen:
                continue
            seen.add(key)
            result.append(clean)
        return result

    def _set_stage_metric(self, key: str, elapsed_ms: float | None) -> None:
        if key not in self.stage_metrics:
            return
        self.stage_metrics[key] = elapsed_ms if elapsed_ms and elapsed_ms > 0 else None
        self._update_sla_message()

    def _reset_stage_metrics(self) -> None:
        for key in self.stage_metrics:
            self.stage_metrics[key] = None
        self._update_sla_message()

    def _update_sla_message(self) -> None:
        if not any(self.stage_metrics.values()):
            self.sla_message.clear()
            return
        parts = [
            f"OCR {self._format_duration(self.stage_metrics['ocr_ms'])}",
            f"Анализ {self._format_duration(self.stage_metrics['analyze_ms'])}",
            f"Черновик {self._format_duration(self.stage_metrics['preview_ms'])}",
            f"Генерация {self._format_duration(self.stage_metrics['generate_ms'])}",
        ]
        self.sla_message.setText("SLA: " + " · ".join(parts))

    def _sync_topic_override_controls(self, topic: str | None = None) -> None:
        has_analysis = self.last_case_analysis is not None
        self.topic_override_panel.setVisible(has_analysis)
        self.topic_override_combo.setEnabled(has_analysis and not self._busy)
        self.topic_override_save_button.setEnabled(has_analysis and not self._busy)
        if not has_analysis:
            return
        selected_topic = (topic or self.last_case_analysis.topic).strip()
        if not selected_topic:
            return
        existing_index = self.topic_override_combo.findText(selected_topic)
        if existing_index < 0:
            self.topic_override_combo.addItem(selected_topic)
            existing_index = self.topic_override_combo.findText(selected_topic)
        self.topic_override_combo.setCurrentIndex(existing_index)

    def refresh_status(self) -> None:
        self.local_pill.set_state("Локальный режим", not self.settings.values.network_disabled)
        if self.settings.values.network_disabled:
            self.local_pill.set_state("Сеть отключена полностью", True)

        if self.settings.values.processing_mode == "text_only":
            self.ocr_pill.set_state("OCR скрыт", True)
        elif self.settings.values.use_ocr:
            ocr_status = self.ocr_manager.status()
            self.ocr_pill.set_state("OCR готов" if ocr_status.ready else "OCR не готов", ocr_status.ready)
        else:
            self.ocr_pill.set_state("OCR выключен", True)

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
        self._refresh_analyze_button_state()

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
        self.last_ocr_raw_text = ""
        self.last_generated_raw_response = ""
        self.last_generated_model = ""
        self.last_generated_style_id = None
        self.last_case_analysis = None
        self.last_case_source = "Ожидание"
        self._reset_stage_metrics()
        self._set_ocr_feedback_enabled(False)
        self._set_response_feedback_enabled(False)
        self._sync_topic_override_controls(None)
        self.drop_zone.set_pixmap(pixmap)
        self._set_status(f"Скриншот загружен: {path.name}")
        self._refresh_analyze_button_state()

    def analyze_screenshot(self) -> None:
        customer = self.customer_text.toPlainText().strip()
        ocr = self.ocr_text.toPlainText().strip()
        text_only = self.settings.values.processing_mode == "text_only"

        if not text_only and self.current_image_path and self.settings.values.use_ocr:
            self._set_busy(True)
            worker = OCRWorker(self.ocr_manager, self.current_image_path)
            worker.finished.connect(self._ocr_finished)
            worker.failed.connect(self._ocr_failed)
            worker.finished.connect(lambda *_: self._forget_worker(worker))
            worker.failed.connect(lambda *_: self._forget_worker(worker))
            self.workers.append(worker)
            self.threads.append(start_worker(worker))
            self._set_status("OCR распознает текст локально...")
            return

        if customer or ocr:
            self._run_backend_analysis(customer, ocr)
            return

        if self.current_image_path and not self.settings.values.use_ocr:
            QMessageBox.information(self, "OCR выключен", "Включите OCR в настройках, если хотите распознавать текст.")
            return

        if text_only:
            QMessageBox.information(self, "Нет текста", "Введите сообщение, чтобы запустить анализ обращения.")
            return

        QMessageBox.information(self, "Нет данных", "Добавьте сообщение или загрузите скриншот перед анализом.")

    def _run_backend_analysis(self, customer_text: str, ocr_text: str) -> None:
        style = self.style_manager.get_style(self.settings.values.selected_style_id)
        self._set_busy(True)
        worker = BackendAnalyzeWorker(
            self.backend_client,
            customer_text=customer_text,
            ocr_text=ocr_text,
            selected_style=style.name if style else None,
        )
        worker.finished.connect(self._backend_analysis_finished)
        worker.failed.connect(
            lambda message, elapsed_ms, customer=customer_text, ocr=ocr_text, profile=style.profile if style else None: self._backend_analysis_failed(
                message,
                elapsed_ms,
                customer,
                ocr,
                profile,
            )
        )
        worker.finished.connect(lambda *_: self._forget_worker(worker))
        worker.failed.connect(lambda *_: self._forget_worker(worker))
        self.workers.append(worker)
        self.threads.append(start_worker(worker))
        self._set_status("FastAPI анализирует обращение...")

    def generate_preview(self) -> None:
        customer = self.customer_text.toPlainText().strip()
        ocr = self.ocr_text.toPlainText().strip()
        if not customer and not ocr:
            QMessageBox.information(self, "Нет текста", "Для черновика нужен текст сообщения или OCR-контекст.")
            return

        style = self.style_manager.get_style(self.settings.values.selected_style_id)
        self._set_busy(True)
        worker = BackendPreviewWorker(
            self.backend_client,
            customer_text=customer,
            ocr_text=ocr,
            selected_style=style.name if style else None,
        )
        worker.finished.connect(self._preview_finished)
        worker.failed.connect(self._preview_failed)
        worker.finished.connect(lambda *_: self._forget_worker(worker))
        worker.failed.connect(lambda *_: self._forget_worker(worker))
        self.workers.append(worker)
        self.threads.append(start_worker(worker))
        self._set_status("FastAPI собирает быстрый черновик ответа...")

    def generate_reply(self) -> None:
        customer = self.customer_text.toPlainText().strip()
        ocr = self.ocr_text.toPlainText().strip()
        text_only = self.settings.values.processing_mode == "text_only"
        has_image = bool(self.current_image_path or self.current_clipboard_image_base64) and not text_only
        if not customer and not ocr and not has_image:
            QMessageBox.information(self, "Нет контекста", "Добавьте сообщение или скриншот.")
            return

        model = self.model_combo.currentText().strip() or self.settings.values.preferred_model
        style = self.style_manager.get_style(self.settings.values.selected_style_id)
        style_prompt = self.style_manager.build_style_prompt(style)
        quality_rules = self.learning_manager.build_quality_rules(style.profile if style else None)
        style_id = style.id if style else None
        style_profile = style.profile if style else None
        image_base64 = None if text_only else self.current_clipboard_image_base64
        if self.current_image_path and not text_only:
            image_base64 = image_path_to_base64(self.current_image_path)

        self._set_busy(True)
        worker = GenerateWorker(self.ai_manager, customer, ocr, style_prompt, quality_rules, model, image_base64)
        worker.finished.connect(lambda text, elapsed_ms: self._generation_finished(text, model, style_id, style_profile, elapsed_ms))
        worker.failed.connect(self._worker_failed)
        worker.finished.connect(lambda *_: self._forget_worker(worker))
        worker.failed.connect(lambda *_: self._forget_worker(worker))
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
            self.style_manager.learn_from_confirmed_interaction(
                updated.id,
                self.customer_text.toPlainText(),
                text,
                self.case_analyzer.analyze(
                    self.customer_text.toPlainText(),
                    self.ocr_text.toPlainText(),
                    style_profile=updated.profile,
                ).topic,
            )
            self.settings.update(selected_style_id=updated.id)
            self._set_status(f"Ответ сохранён в стиль и усилил контекст: {updated.name}")
        except Exception as exc:
            QMessageBox.warning(self, "Не удалось сохранить в стиль", str(exc))

    def clear_all(self) -> None:
        self.customer_text.clear()
        self.ocr_text.clear()
        self.response_text.clear()
        self.current_image_path = None
        self.current_clipboard_image_base64 = None
        self.last_ocr_raw_text = ""
        self.last_generated_raw_response = ""
        self.last_generated_model = ""
        self.last_generated_style_id = None
        self.last_case_analysis = None
        self.last_case_source = "Ожидание"
        self._reset_stage_metrics()
        self._set_ocr_feedback_enabled(False)
        self._set_response_feedback_enabled(False)
        self._sync_topic_override_controls(None)
        self.drop_zone.set_pixmap(None)
        self._set_status("Очищено")
        self._refresh_analyze_button_state()

    def open_settings(self) -> None:
        dialog = SettingsDialog(
            self.settings,
            self.style_manager,
            self.database,
            self.ai_manager,
            self.ocr_manager,
            self,
        )
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
                self.last_ocr_raw_text = ""
                self.last_generated_raw_response = ""
                self.last_generated_model = ""
                self.last_generated_style_id = None
                self.last_case_analysis = None
                self.last_case_source = "Ожидание"
                self._reset_stage_metrics()
                self._set_ocr_feedback_enabled(False)
                self._set_response_feedback_enabled(False)
                self._sync_topic_override_controls(None)
                self.drop_zone.set_pixmap(load_pixmap(temp_path))
                self._set_status("Скриншот вставлен из буфера обмена")
                self._refresh_analyze_button_state()
                return
        super().keyPressEvent(event)

    def _ocr_finished(self, text: str, elapsed_ms: float) -> None:
        self._set_stage_metric("ocr_ms", elapsed_ms)
        self.last_ocr_raw_text = text or ""
        learned = self.learning_manager.apply_ocr_memory(text or "")
        self.ocr_text.setPlainText(learned.text)
        self._set_ocr_feedback_enabled(bool(text))
        if not text:
            self._set_busy(False)
            self._set_status(f"OCR завершен, текст не найден · {self._format_duration(elapsed_ms)}")
        elif learned.replacements:
            preview = ", ".join(f"{source} -> {target}" for source, target in learned.replacements[:3])
            self._set_status(f"OCR завершен · {self._format_duration(elapsed_ms)} · автокоррекция: {preview}")
            self._set_busy(False)
            self._run_backend_analysis(self.customer_text.toPlainText().strip(), learned.text)
        else:
            self._set_status(f"OCR завершен · {self._format_duration(elapsed_ms)}")
            self._set_busy(False)
            self._run_backend_analysis(self.customer_text.toPlainText().strip(), learned.text)

    def _ocr_failed(self, message: str, elapsed_ms: float) -> None:
        self._set_stage_metric("ocr_ms", elapsed_ms)
        self._worker_failed(message)

    def _backend_analysis_finished(self, payload: dict, elapsed_ms: float) -> None:
        self._set_stage_metric("analyze_ms", elapsed_ms)
        self._show_analysis_payload(payload, "FastAPI")
        self._set_status(f"Анализ готов · {self._format_duration(elapsed_ms)}. Собираю черновик ответа...")
        self._set_busy(False)
        self.generate_preview()

    def _backend_analysis_failed(
        self,
        message: str,
        elapsed_ms: float,
        customer_text: str,
        ocr_text: str,
        style_profile: dict | None,
    ) -> None:
        self._set_stage_metric("analyze_ms", elapsed_ms)
        analysis = self.case_analyzer.analyze(
            customer_text,
            ocr_text,
            style_profile=style_profile,
        )
        self._show_case_analysis(analysis, "Fallback")
        self._set_status(f"{message} Использован локальный анализ.")
        self._set_busy(False)

    def _preview_finished(self, payload: dict, elapsed_ms: float) -> None:
        self._set_stage_metric("preview_ms", elapsed_ms)
        draft_reply = str(payload.get("draft_reply", "")).strip()
        self.response_text.setPlainText(draft_reply)
        self.last_generated_raw_response = ""
        self.last_generated_model = ""
        self.last_generated_style_id = None
        self._set_response_feedback_enabled(False)
        self._show_analysis_payload(payload, "Preview")
        topic = str(payload.get("topic", "Общее обращение"))
        self._set_status(f"Черновик собран через FastAPI · {self._format_duration(elapsed_ms)} · тема: {topic}")
        self._set_busy(False)

    def _preview_failed(self, message: str, elapsed_ms: float) -> None:
        self._set_stage_metric("preview_ms", elapsed_ms)
        self._worker_failed(message)

    def _generation_finished(
        self,
        text: str,
        model: str,
        style_id: int | None,
        style_profile: dict | None,
        elapsed_ms: float,
    ) -> None:
        try:
            self._set_stage_metric("generate_ms", elapsed_ms)
            self.response_text.setPlainText(text)
            self.last_generated_raw_response = text
            self.last_generated_model = model
            self.last_generated_style_id = style_id
            self._set_response_feedback_enabled(bool(text.strip()))
            analysis = self.case_analyzer.analyze(
                self.customer_text.toPlainText(),
                self.ocr_text.toPlainText(),
                style_profile=style_profile,
            )
            self.database.execute(
                """
                INSERT INTO conversations(
                    customer_text, ocr_text, response_text, model_name, style_id,
                    topic, signals_json, extracted_json, ocr_ms, analyze_ms, preview_ms, generation_ms
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    int(self.stage_metrics.get("ocr_ms") or 0),
                    int(self.stage_metrics.get("analyze_ms") or 0),
                    int(self.stage_metrics.get("preview_ms") or 0),
                    int(elapsed_ms),
                ),
            )
            self._show_case_analysis(analysis, "Локально")
            self._set_status(f"Ответ сгенерирован локально · SLA {self._format_duration(elapsed_ms)}")
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
        self._busy = busy
        for button in [self.load_button, self.preview_button, self.generate_button, self.save_to_style_button, self.clear_button]:
            button.setEnabled(not busy)
        self._refresh_analyze_button_state()
        self.refresh_button.setEnabled(not busy)
        self._sync_topic_override_controls()

        has_ocr_feedback = bool(self.last_ocr_raw_text)
        has_response_feedback = bool(self.last_generated_raw_response)
        self.ocr_feedback_correct_button.setEnabled(not busy and has_ocr_feedback)
        self.ocr_feedback_save_button.setEnabled(not busy and has_ocr_feedback)
        self.response_feedback_correct_button.setEnabled(not busy and has_response_feedback)
        self.response_feedback_save_button.setEnabled(not busy and has_response_feedback)

    def _set_ocr_feedback_enabled(self, enabled: bool) -> None:
        self.ocr_feedback_correct_button.setEnabled(enabled)
        self.ocr_feedback_save_button.setEnabled(enabled)
        self.ocr_feedback_correct_button.setVisible(enabled)
        self.ocr_feedback_save_button.setVisible(enabled)

    def _set_response_feedback_enabled(self, enabled: bool) -> None:
        self.response_feedback_correct_button.setEnabled(enabled)
        self.response_feedback_save_button.setEnabled(enabled)
        self.response_feedback_correct_button.setVisible(enabled)
        self.response_feedback_save_button.setVisible(enabled)

    def mark_ocr_correct(self) -> None:
        text = self.ocr_text.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Нет OCR-текста", "Сначала распознайте текст со скриншота.")
            return
        self._save_ocr_feedback("correct", text)
        self._set_status("OCR отмечен как корректный")

    def save_corrected_ocr_text(self) -> None:
        corrected_text = self.ocr_text.toPlainText().strip()
        if not corrected_text:
            QMessageBox.information(self, "Нет текста", "Исправьте OCR-текст или сначала выполните распознавание.")
            return
        if not self.last_ocr_raw_text:
            QMessageBox.information(self, "Нет исходного OCR", "Сначала выполните OCR, а потом сохраните исправленный текст.")
            return
        self._save_ocr_feedback("corrected", corrected_text)
        self._set_status("Исправленный OCR-текст сохранён")

    def _save_ocr_feedback(self, verdict: str, corrected_text: str) -> None:
        self.database.execute(
            """
            INSERT INTO ocr_feedback(image_path, raw_text, corrected_text, engine, verdict)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(self.current_image_path or ""),
                self.last_ocr_raw_text,
                corrected_text,
                self.settings.values.ocr_engine,
                verdict,
            ),
        )

    def mark_response_correct(self) -> None:
        text = self.response_text.toPlainText().strip()
        if not text or not self.last_generated_raw_response:
            QMessageBox.information(self, "Нет ответа", "Сначала сгенерируйте ответ.")
            return
        self._save_response_feedback("correct", text)
        learned = self._auto_learn_from_response(text, store_example=False)
        if learned:
            self._set_status(f"Ответ отмечен как удачный и усилил стиль: {learned.name}")
        else:
            self._set_status("Ответ отмечен как удачный")

    def save_corrected_response(self) -> None:
        corrected_text = self.response_text.toPlainText().strip()
        if not corrected_text or not self.last_generated_raw_response:
            QMessageBox.information(self, "Нет исходного ответа", "Сначала сгенерируйте ответ, затем при необходимости исправьте его.")
            return
        self._save_response_feedback("corrected", corrected_text)
        learned = self._auto_learn_from_response(corrected_text, store_example=True)
        if learned:
            self._set_status(f"Исправленный ответ сохранён и усилил стиль: {learned.name}")
        else:
            self._set_status("Исправленный ответ сохранён в память качества")

    def _save_response_feedback(self, verdict: str, corrected_response: str) -> None:
        self.database.execute(
            """
            INSERT INTO response_feedback(
                customer_text, ocr_text, raw_response, corrected_response,
                model_name, style_id, verdict
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.customer_text.toPlainText(),
                self.ocr_text.toPlainText(),
                self.last_generated_raw_response,
                corrected_response,
                self.last_generated_model,
                self.last_generated_style_id,
                verdict,
            ),
        )

    def _auto_learn_from_response(self, final_response: str, *, store_example: bool) -> object | None:
        style_id = self.last_generated_style_id or self.settings.values.selected_style_id
        if not style_id:
            return None
        style = self.style_manager.get_style(style_id)
        if not style:
            return None
        analysis = self.case_analyzer.analyze(
            self.customer_text.toPlainText(),
            self.ocr_text.toPlainText(),
            style_profile=style.profile,
        )
        updated = self.style_manager.learn_from_confirmed_interaction(
            style_id,
            self.customer_text.toPlainText(),
            final_response,
            analysis.topic,
            store_example=store_example,
        )
        self.settings.update(selected_style_id=updated.id)
        return updated

    def save_topic_correction(self) -> None:
        if not self.last_case_analysis:
            QMessageBox.information(self, "Нет анализа", "Сначала выполните анализ обращения.")
            return
        corrected_topic = self.topic_override_combo.currentText().strip()
        if not corrected_topic:
            QMessageBox.information(self, "Нет темы", "Выберите тему из списка.")
            return
        style = self.style_manager.get_style(self.settings.values.selected_style_id)
        if not style:
            QMessageBox.warning(self, "Стиль не выбран", "Выберите активный стиль, чтобы обучение было контекстным.")
            return

        self.style_manager.learn_from_topic_correction(
            style.id,
            self.customer_text.toPlainText(),
            self.ocr_text.toPlainText(),
            corrected_topic,
        )
        self.database.execute(
            """
            INSERT INTO topic_feedback(customer_text, ocr_text, raw_topic, corrected_topic, style_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                self.customer_text.toPlainText(),
                self.ocr_text.toPlainText(),
                self.last_case_analysis.topic,
                corrected_topic,
                style.id,
            ),
        )
        corrected_analysis = CaseAnalysis(
            topic=corrected_topic,
            signals=list(self.last_case_analysis.signals),
            extracted=dict(self.last_case_analysis.extracted),
        )
        self._show_case_analysis(corrected_analysis, "Подтверждено")
        self._set_status(f"Тема сохранена и усилила стиль: {corrected_topic}")

    def apply_processing_mode(self) -> None:
        text_only = self.settings.values.processing_mode == "text_only"
        self.screenshot_panel.setVisible(not text_only)
        self.load_button.setVisible(not text_only)
        self.analyze_button.setVisible(True)
        if text_only:
            self.current_image_path = None
            self.current_clipboard_image_base64 = None
            self.drop_zone.set_pixmap(None)
            self._set_status("Быстрый режим: генерация только по тексту")
        else:
            self._set_status("Режим со скриншотами: изображение используется, если оно загружено")
        self._refresh_analyze_button_state()

    def _set_status(self, message: str) -> None:
        self.status_message.setText(message)
        animation = QPropertyAnimation(self.status_message, b"maximumHeight", self)
        animation.setDuration(180)
        animation.setStartValue(24)
        animation.setEndValue(38)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    @staticmethod
    def _format_duration(milliseconds: float | None) -> str:
        if not milliseconds:
            return "—"
        seconds = milliseconds / 1000
        if seconds < 60:
            return f"{seconds:.1f} сек"
        minutes = int(seconds // 60)
        rest = int(seconds % 60)
        return f"{minutes} мин {rest} сек"

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
            self.case_summary.set_placeholder("Признаки появятся после ввода текста или OCR.")
            self.last_case_analysis = None
            self.last_case_source = "Ожидание"
            self._sync_topic_override_controls(None)
            self._refresh_analyze_button_state()
            return
        style = self.style_manager.get_style(self.settings.values.selected_style_id)
        analysis = self.case_analyzer.analyze(
            text,
            ocr,
            style_profile=style.profile if style else None,
        )
        self._show_case_analysis(analysis, "Предпросмотр")
        self._refresh_analyze_button_state()

    def _refresh_analyze_button_state(self) -> None:
        has_text = bool(self.customer_text.toPlainText().strip() or self.ocr_text.toPlainText().strip())
        can_use_ocr = (
            self.settings.values.processing_mode != "text_only"
            and self.settings.values.use_ocr
            and bool(self.current_image_path)
        )
        enabled = not self._busy and (has_text or can_use_ocr)
        self.analyze_button.setEnabled(enabled)
        self.preview_button.setEnabled(not self._busy and has_text)
        if self._busy:
            self.analyze_button.setToolTip("Дождитесь завершения текущей операции.")
            self.preview_button.setToolTip("Дождитесь завершения текущей операции.")
        elif can_use_ocr:
            self.analyze_button.setToolTip("Сделать всё по цепочке: OCR -> анализ -> черновик ответа.")
            self.preview_button.setToolTip("Для черновика сначала нужен текст из сообщения или OCR.")
        elif has_text:
            self.analyze_button.setToolTip("Собрать тему обращения и быстрый черновик ответа через FastAPI.")
            self.preview_button.setToolTip("Собрать быстрый черновик ответа через FastAPI без полной генерации.")
        elif self.settings.values.processing_mode == "text_only":
            self.analyze_button.setToolTip("Введите сообщение, чтобы подготовить черновик ответа.")
            self.preview_button.setToolTip("Введите сообщение, чтобы собрать черновик.")
        elif not self.settings.values.use_ocr:
            self.analyze_button.setToolTip("Включите OCR или введите текст вручную.")
            self.preview_button.setToolTip("Введите текст вручную или сначала получите OCR.")
        else:
            self.analyze_button.setToolTip("Загрузите скриншот или введите сообщение.")
            self.preview_button.setToolTip("Нужен текст сообщения или OCR-контекст.")

    def _show_case_analysis(self, analysis: CaseAnalysis, source: str) -> None:
        self.last_case_analysis = analysis
        self.last_case_source = source
        self.case_summary.set_analysis(
            topic=analysis.topic,
            signals=analysis.signals,
            extracted=analysis.extracted,
            source=source,
        )
        self._sync_topic_override_controls(analysis.topic)

    def _show_analysis_payload(self, payload: dict, source: str) -> None:
        topic = str(payload.get("topic", "Общее обращение"))
        signals = payload.get("signals", [])
        if not isinstance(signals, list):
            signals = []
        extracted = payload.get("extracted", {})
        if not isinstance(extracted, dict):
            extracted = {}
        normalized_extracted = {
            "amounts": [str(item) for item in extracted.get("amounts", [])][:8],
            "dates": [str(item) for item in extracted.get("dates", [])][:8],
            "mcc_codes": [str(item) for item in extracted.get("mcc_codes", [])][:12],
        }
        analysis = CaseAnalysis(
            topic=topic,
            signals=[str(item) for item in signals],
            extracted=normalized_extracted,
        )
        self._show_case_analysis(analysis, source)

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
