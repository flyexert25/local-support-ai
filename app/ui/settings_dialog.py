from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QPlainTextEdit,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.settings_manager import SettingsManager
from app.storage.analytics_repository import AnalyticsRepository
from app.storage.database import Database
from app.styles.style_manager import StyleManager
from app.ui.widgets import ToggleSwitch


class SettingsDialog(QDialog):
    settingsChanged = pyqtSignal()

    def __init__(self, settings: SettingsManager, style_manager: StyleManager, database: Database, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.style_manager = style_manager
        self.analytics = AnalyticsRepository(database)
        self.current_style_id: int | None = settings.values.selected_style_id
        self.setWindowTitle("Настройки")
        self.resize(920, 680)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._scrollable(self._build_general_tab()), "Основное")
        self.tabs.addTab(self._scrollable(self._build_appearance_tab()), "Внешний вид")
        self.tabs.addTab(self._build_styles_tab(), "Мой стиль общения")
        self.tabs.addTab(self._scrollable(self._build_analytics_tab()), "Аналитика")

        save_button = QPushButton("Сохранить")
        save_button.setObjectName("Primary")
        save_button.clicked.connect(self._save_and_close)
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)

        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(save_button)
        footer.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.addWidget(self.tabs, 1)
        layout.addLayout(footer)
        self._load_styles()

    def _scrollable(self, page: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidget(page)
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        return area

    def _build_general_tab(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(14)

        self.ollama_url = QLineEdit(self.settings.values.ollama_url)
        self.preferred_model = QLineEdit(self.settings.values.preferred_model)
        self.mode_text_only = QRadioButton("Только текст")
        self.mode_vision_auto = QRadioButton("Текст + локальная vision-модель")
        mode = self.settings.values.processing_mode
        self.mode_text_only.setChecked(mode == "text_only")
        self.mode_vision_auto.setChecked(mode != "text_only")
        self.use_ocr = ToggleSwitch()
        self.use_ocr.setChecked(self.settings.values.use_ocr)
        self.ocr_engine = QComboBox()
        self.ocr_engine.addItems(["easyocr", "paddleocr"])
        self.ocr_engine.setCurrentText(self.settings.values.ocr_engine)
        self.ocr_engine.setEnabled(self.use_ocr.isChecked())
        self.use_ocr.toggled.connect(self.ocr_engine.setEnabled)
        self.mode_text_only.toggled.connect(self._sync_processing_mode_controls)
        self.mode_vision_auto.toggled.connect(self._sync_processing_mode_controls)

        self.always_on_top = ToggleSwitch()
        self.always_on_top.setChecked(self.settings.values.always_on_top)
        self.compact_mode = ToggleSwitch()
        self.compact_mode.setChecked(self.settings.values.compact_mode)
        self.network_disabled = ToggleSwitch()
        self.network_disabled.setChecked(self.settings.values.network_disabled)

        root.addWidget(
            self._section(
                "Локальная модель",
                "Ollama используется только через localhost. Клиентские данные не отправляются в cloud API.",
                [
                    self._field_row("Адрес Ollama", "Обычно http://localhost:11434", self.ollama_url),
                    self._field_row("Модель по умолчанию", "Например qwen2.5vl:latest", self.preferred_model),
                ],
            )
        )
        root.addWidget(
            self._section(
                "Обработка обращений",
                "Выберите, как приложение будет использовать текст и скриншоты. Если скриншот не нужен, быстрый текстовый режим делает интерфейс чище.",
                [
                    self._radio_row(
                        self.mode_text_only,
                        "Быстрый режим для случаев, когда вы вставляете сообщение клиента вручную. Превью скриншота скрывается, изображение не отправляется в модель.",
                    ),
                    self._radio_row(
                        self.mode_vision_auto,
                        "Обычный режим: если скриншот загружен, Qwen Vision прочитает его через локальный Ollama. Если скриншота нет, ответ строится по тексту.",
                    ),
                ],
            )
        )
        root.addWidget(
            self._section(
                "OCR для скриншотов",
                "OCR нужен только если хотите отдельно получить редактируемый текст со скриншота. Для Qwen Vision он не обязателен.",
                [
                    self._toggle_row("Использовать OCR", "Включает кнопку «Анализировать» и локальное распознавание скриншотов.", self.use_ocr),
                    self._field_row("OCR-движок", "EasyOCR проще подготовить, PaddleOCR можно поставить отдельно.", self.ocr_engine),
                ],
            )
        )
        root.addWidget(
            self._section(
                "Окно",
                "Настройки поведения приложения во время ежедневной работы.",
                [
                    self._toggle_row("Поверх всех окон", "Удобно, если приложение работает рядом с CRM или чатом.", self.always_on_top),
                    self._toggle_row("Компактный режим", "Уменьшает окно до более плотного рабочего вида.", self.compact_mode),
                ],
            )
        )
        root.addWidget(
            self._section(
                "Приватность",
                "В обычном режиме разрешён только localhost. В строгом режиме блокируются любые сетевые подключения, включая Ollama.",
                [
                    self._toggle_row("Заблокировать любые сетевые подключения", "Максимальная изоляция. Генерация через Ollama будет недоступна, пока тумблер включён.", self.network_disabled),
                ],
            )
        )
        root.addStretch(1)
        self._sync_processing_mode_controls()
        return page

    def _build_appearance_tab(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(14)

        self.light_theme = ToggleSwitch()
        self.light_theme.setChecked(self.settings.values.theme == "light")

        root.addWidget(
            self._section(
                "Тема приложения",
                "Выберите вид, в котором удобнее работать каждый день.",
                [
                    self._toggle_row(
                        "Светлая тема",
                        "Более воздушный вид для дневной работы. Если выключено, используется тёмная тема.",
                        self.light_theme,
                    ),
                ],
            )
        )
        root.addWidget(
            self._section(
                "Стиль интерфейса",
                "Приложение сделано как рабочий инструмент поддержки: без маркетинговых экранов, лишних иллюстраций и визуального шума.",
                [
                    self._preview_row("Основной экран", "Скриншот, текст клиента, OCR и готовый ответ остаются на одном рабочем поле."),
                    self._preview_row("Настройки", "Технические параметры сгруппированы в понятные секции с тумблерами."),
                ],
            )
        )
        root.addStretch(1)
        return page

    def _build_styles_tab(self) -> QWidget:
        page = QWidget()
        root = QHBoxLayout(page)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(12)

        left_panel = QFrame()
        left_panel.setObjectName("Panel")
        left = QVBoxLayout(left_panel)
        left.setContentsMargins(10, 10, 10, 10)
        self.styles_list = QListWidget()
        self.styles_list.currentItemChanged.connect(self._on_style_selected)
        add_button = QPushButton("Новый стиль")
        add_button.clicked.connect(self._new_style)
        delete_button = QPushButton("Удалить")
        delete_button.setObjectName("Danger")
        delete_button.clicked.connect(self._delete_style)
        import_button = QPushButton("Импорт txt/json")
        import_button.clicked.connect(self._import_style)
        export_button = QPushButton("Экспорт")
        export_button.clicked.connect(self._export_style)
        left.addWidget(self.styles_list, 1)
        left.addWidget(add_button)
        left.addWidget(import_button)
        left.addWidget(export_button)
        left.addWidget(delete_button)

        right_panel = QFrame()
        right_panel.setObjectName("Panel")
        right = QVBoxLayout(right_panel)
        right.setContentsMargins(12, 12, 12, 12)
        self.style_name = QLineEdit()
        self.style_examples = QPlainTextEdit()
        self.style_examples.setPlaceholderText(
            "Вставьте сюда ваши реальные ответы клиентам. Чем больше примеров, тем точнее стиль."
        )
        self.style_profile = QLabel()
        self.style_profile.setObjectName("Subtle")
        self.style_profile.setWordWrap(True)
        train_button = QPushButton("Обучить стиль")
        train_button.setObjectName("Primary")
        train_button.clicked.connect(self._train_style)

        right.addWidget(QLabel("Название стиля"))
        right.addWidget(self.style_name)
        right.addWidget(QLabel("Примеры ваших ответов"))
        right.addWidget(self.style_examples, 1)
        right.addWidget(train_button)
        right.addWidget(self.style_profile)

        root.addWidget(left_panel, 1)
        root.addWidget(right_panel, 3)
        return page

    def _build_analytics_tab(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(14)

        total = self.analytics.total_generated()
        topic_rows = [
            self._metric_row(topic, f"{count} ответ(ов)")
            for topic, count in self.analytics.top_topics()
        ]
        if not topic_rows:
            topic_rows = [self._preview_row("Пока нет данных", "Сгенерируйте несколько ответов, и здесь появятся частые темы.")]

        recent_rows = []
        for item in self.analytics.recent_cases():
            signals = Database.decode_json(item["signals_json"]).get("signals") or []
            extracted = Database.decode_json(item["extracted_json"])
            details: list[str] = []
            if signals:
                details.append("признаки: " + ", ".join(map(str, signals[:4])))
            if extracted.get("amounts"):
                details.append("суммы: " + ", ".join(extracted["amounts"][:3]))
            if extracted.get("dates"):
                details.append("даты: " + ", ".join(extracted["dates"][:3]))
            if extracted.get("mcc_codes"):
                details.append("MCC: " + ", ".join(extracted["mcc_codes"][:4]))
            recent_rows.append(
                self._preview_row(
                    f"{item['topic']} · {item['created_at']}",
                    "; ".join(details) if details else "без выделенных признаков",
                )
            )
        if not recent_rows:
            recent_rows = [self._preview_row("История пуста", "Аналитика начнёт собираться после генерации ответов.")]

        root.addWidget(
            self._section(
                "Сводка",
                "Локальная статистика по ответам, сохранённая в SQLite.",
                [
                    self._metric_row("Сгенерировано ответов", str(total)),
                ],
            )
        )
        root.addWidget(
            self._section(
                "Частые темы",
                "Темы определяются локально по правилам и регулярным выражениям.",
                topic_rows,
            )
        )
        root.addWidget(
            self._section(
                "Последние признаки",
                "Что анализатор выделил в последних обращениях: суммы, даты, MCC-коды и сигналы.",
                recent_rows,
            )
        )
        root.addStretch(1)
        return page

    def _section(self, title: str, subtitle: str, rows: list[QWidget]) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)
        heading = QLabel(title)
        heading.setStyleSheet("font-size: 15px; font-weight: 700;")
        hint = QLabel(subtitle)
        hint.setObjectName("Subtle")
        hint.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(hint)
        for row in rows:
            layout.addWidget(row)
        return frame

    def _toggle_row(self, title: str, subtitle: str, toggle: ToggleSwitch) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 4, 0, 4)
        text_box = QVBoxLayout()
        label = QLabel(title)
        label.setStyleSheet("font-weight: 600;")
        hint = QLabel(subtitle)
        hint.setObjectName("Subtle")
        hint.setWordWrap(True)
        text_box.addWidget(label)
        text_box.addWidget(hint)
        layout.addLayout(text_box, 1)
        layout.addWidget(toggle, 0, Qt.AlignmentFlag.AlignRight)
        return row

    def _radio_row(self, radio: QRadioButton, subtitle: str) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 4, 0, 4)
        radio.setStyleSheet("font-weight: 600;")
        hint = QLabel(subtitle)
        hint.setObjectName("Subtle")
        hint.setWordWrap(True)
        layout.addWidget(radio)
        layout.addWidget(hint)
        return row

    def _field_row(self, title: str, subtitle: str, field: QWidget) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 4, 0, 4)
        text_box = QVBoxLayout()
        label = QLabel(title)
        label.setStyleSheet("font-weight: 600;")
        hint = QLabel(subtitle)
        hint.setObjectName("Subtle")
        hint.setWordWrap(True)
        text_box.addWidget(label)
        text_box.addWidget(hint)
        layout.addLayout(text_box, 1)
        layout.addWidget(field, 2)
        return row

    def _preview_row(self, title: str, subtitle: str) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 4, 0, 4)
        label = QLabel(title)
        label.setStyleSheet("font-weight: 600;")
        hint = QLabel(subtitle)
        hint.setObjectName("Subtle")
        hint.setWordWrap(True)
        layout.addWidget(label)
        layout.addWidget(hint)
        return row

    def _metric_row(self, title: str, value: str) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 4, 0, 4)
        label = QLabel(title)
        label.setStyleSheet("font-weight: 600;")
        number = QLabel(value)
        number.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        number.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(label, 1)
        layout.addWidget(number)
        return row

    def _load_styles(self) -> None:
        self.styles_list.clear()
        selected_row = 0
        styles = self.style_manager.list_styles()
        for index, style in enumerate(styles):
            item = QListWidgetItem(style.name)
            item.setData(256, style.id)
            self.styles_list.addItem(item)
            if style.id == self.current_style_id:
                selected_row = index
        if styles:
            self.styles_list.setCurrentRow(selected_row)

    def _on_style_selected(self, current: QListWidgetItem | None) -> None:
        if not current:
            return
        style_id = int(current.data(256))
        style = self.style_manager.get_style(style_id)
        if not style:
            return
        self.current_style_id = style.id
        self.style_name.setText(style.name)
        self.style_examples.setPlainText(style.examples)
        self._show_profile(style.profile)

    def _new_style(self) -> None:
        self.current_style_id = None
        self.style_name.setText("Новый стиль")
        self.style_examples.clear()
        self.style_profile.setText("Добавьте примеры и нажмите «Обучить стиль».")

    def _train_style(self) -> None:
        try:
            style_id = self.style_manager.save_style(
                self.style_name.text(),
                self.style_examples.toPlainText(),
                self.current_style_id,
            )
            self.current_style_id = style_id
            self.settings.update(selected_style_id=style_id)
            self._load_styles()
            style = self.style_manager.get_style(style_id)
            if style:
                self._show_profile(style.profile)
        except Exception as exc:
            QMessageBox.warning(self, "Не удалось сохранить стиль", str(exc))

    def _delete_style(self) -> None:
        if not self.current_style_id:
            return
        try:
            self.style_manager.delete_style(self.current_style_id)
            self.current_style_id = None
            self._load_styles()
        except Exception as exc:
            QMessageBox.warning(self, "Не удалось удалить стиль", str(exc))

    def _import_style(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Импорт стиля", "", "Text or JSON (*.txt *.json)")
        if not filename:
            return
        try:
            style_id = self.style_manager.import_style_file(Path(filename))
            self.current_style_id = style_id
            self.settings.update(selected_style_id=style_id)
            self._load_styles()
        except Exception as exc:
            QMessageBox.warning(self, "Импорт не удался", str(exc))

    def _export_style(self) -> None:
        if not self.current_style_id:
            return
        filename, _ = QFileDialog.getSaveFileName(self, "Экспорт стиля", "style.json", "JSON (*.json)")
        if not filename:
            return
        try:
            self.style_manager.export_style(self.current_style_id, Path(filename))
        except Exception as exc:
            QMessageBox.warning(self, "Экспорт не удался", str(exc))

    def _save_and_close(self) -> None:
        if self.current_style_id:
            self._train_style()
        self.settings.update(
            ollama_url=self.ollama_url.text().strip() or "http://localhost:11434",
            preferred_model=self.preferred_model.text().strip(),
            processing_mode="text_only" if self.mode_text_only.isChecked() else "vision_auto",
            theme="light" if self.light_theme.isChecked() else "dark",
            use_ocr=self.use_ocr.isChecked(),
            ocr_engine=self.ocr_engine.currentText(),
            always_on_top=self.always_on_top.isChecked(),
            compact_mode=self.compact_mode.isChecked(),
            network_disabled=self.network_disabled.isChecked(),
            selected_style_id=self.current_style_id,
        )
        self.settingsChanged.emit()
        self.accept()

    def _sync_processing_mode_controls(self) -> None:
        text_only = self.mode_text_only.isChecked()
        self.use_ocr.setEnabled(not text_only)
        self.ocr_engine.setEnabled(not text_only and self.use_ocr.isChecked())

    def _show_profile(self, profile: dict) -> None:
        phrases = ", ".join(profile.get("typical_phrases") or [])
        self.style_profile.setText(
            f"Тон: {profile.get('tone', 'не определен')}. "
            f"Длина: {profile.get('avg_sentence_words', 0)} слов/предложение. "
            f"Формат: {profile.get('paragraph_style', 'не определен')}. "
            f"Типичные фразы: {phrases or 'пока не выделены'}."
        )
