from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
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

from app.ai.ai_manager import AIManager
from app.core.settings_manager import SettingsManager
from app.ocr.ocr_manager import OCRManager
from app.storage.analytics_repository import AnalyticsRepository
from app.storage.database import Database
from app.styles.style_manager import StyleManager
from app.ui.widgets import ToggleSwitch
from app.utils.paths import exports_dir, logs_dir


class SettingsDialog(QDialog):
    settingsChanged = pyqtSignal()

    def __init__(
        self,
        settings: SettingsManager,
        style_manager: StyleManager,
        database: Database,
        ai_manager: AIManager,
        ocr_manager: OCRManager,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.style_manager = style_manager
        self.analytics = AnalyticsRepository(database)
        self.database = database
        self.ai_manager = ai_manager
        self.ocr_manager = ocr_manager
        self.current_style_id: int | None = settings.values.selected_style_id
        self.setWindowTitle("Настройки")
        self.resize(920, 680)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._scrollable(self._build_general_tab()), "Основное")
        self.tabs.addTab(self._scrollable(self._build_appearance_tab()), "Внешний вид")
        self.tabs.addTab(self._build_styles_tab(), "Мой стиль общения")
        self.tabs.addTab(self._scrollable(self._build_analytics_tab()), "Аналитика")
        self.tabs.addTab(self._scrollable(self._build_diagnostics_tab()), "Диагностика")

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
        self.generation_device = QComboBox()
        self.generation_device.addItem("Авто (рекомендуется)", "auto")
        self.generation_device.addItem("CPU", "cpu")
        self.generation_device.addItem("GPU", "gpu")
        device_index = self.generation_device.findData(getattr(self.settings.values, "generation_device", "auto"))
        self.generation_device.setCurrentIndex(max(device_index, 0))
        self.mode_text_only = QRadioButton("Только текст")
        self.mode_vision_auto = QRadioButton("Текст + локальная vision-модель")
        self.processing_mode_group = QButtonGroup(self)
        self.processing_mode_group.setExclusive(True)
        self.processing_mode_group.addButton(self.mode_text_only)
        self.processing_mode_group.addButton(self.mode_vision_auto)
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
                "Ollama используется только через localhost. Данные не отправляются в cloud API.",
                [
                    self._field_row("Адрес Ollama", "Обычно http://localhost:11434", self.ollama_url),
                    self._field_row("Модель по умолчанию", "Например qwen2.5vl:latest", self.preferred_model),
                    self._field_row(
                        "Устройство генерации",
                        "Авто обычно лучше: Ollama сама использует GPU, если он доступен. CPU полезен для стабильности или тестов.",
                        self.generation_device,
                    ),
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
                        "Быстрый режим для случаев, когда вы вставляете сообщение вручную. Превью скриншота скрывается, изображение не отправляется в модель.",
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
                    self._preview_row("Основной экран", "Скриншот, текст обращения, OCR и готовый ответ остаются на одном рабочем поле."),
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
            "Вставьте сюда ваши реальные ответы. Чем больше примеров, тем точнее стиль."
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
        average_generation_ms = self.analytics.average_generation_ms()
        slowest_generation_ms = self.analytics.slowest_generation_ms()
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

        export_button = QPushButton("Выгрузить диаграмму")
        export_button.setObjectName("Primary")
        export_button.clicked.connect(self._export_analytics_chart)
        root.addWidget(export_button, 0, Qt.AlignmentFlag.AlignLeft)
        root.addWidget(
            self._section(
                "Сводка",
                "Локальная статистика по ответам, сохранённая в SQLite.",
                [
                    self._metric_row("Сгенерировано ответов", str(total)),
                    self._metric_row("Среднее SLA генерации", self._format_duration(average_generation_ms)),
                    self._metric_row("Самая долгая генерация", self._format_duration(slowest_generation_ms)),
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

    def _build_diagnostics_tab(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(14)

        refresh_button = QPushButton("Обновить диагностику")
        refresh_button.setObjectName("Primary")
        refresh_button.clicked.connect(self._refresh_diagnostics)
        root.addWidget(refresh_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.diagnostics_runtime_section = self._section(
            "Состояние системы",
            "Проверка локальной модели, OCR и активного режима работы приложения.",
            [],
        )
        self.diagnostics_storage_section = self._section(
            "Локальные пути",
            "Где приложение хранит базу, настройки, логи и экспортированные отчёты.",
            [],
        )
        self.diagnostics_performance_section = self._section(
            "Быстрая сводка",
            "Короткие показатели по генерации и текущей конфигурации.",
            [],
        )

        root.addWidget(self.diagnostics_runtime_section)
        root.addWidget(self.diagnostics_storage_section)
        root.addWidget(self.diagnostics_performance_section)
        root.addStretch(1)

        self._refresh_diagnostics()
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

    def _replace_section_rows(self, frame: QFrame, rows: list[QWidget]) -> None:
        layout = frame.layout()
        if layout is None:
            return
        while layout.count() > 2:
            item = layout.takeAt(2)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for row in rows:
            layout.addWidget(row)

    def _refresh_diagnostics(self) -> None:
        ollama_status = self.ai_manager.check_status()
        ocr_status = self.ocr_manager.status()
        average_generation_ms = self.analytics.average_generation_ms()
        slowest_generation_ms = self.analytics.slowest_generation_ms()

        active_mode = "Только текст" if self.settings.values.processing_mode == "text_only" else "Текст + vision"
        device_map = {
            "auto": "Авто",
            "cpu": "CPU",
            "gpu": "GPU",
        }
        model_label = self.settings.values.preferred_model or "не выбрана"
        supported_models = ", ".join(ollama_status.supported_models[:4]) if ollama_status.supported_models else "не найдены"

        runtime_rows = [
            self._metric_row("Ollama", "доступен" if ollama_status.connected else "недоступен"),
            self._preview_row("Сообщение Ollama", ollama_status.message),
            self._metric_row("Vision-модели", supported_models),
            self._metric_row("Модель по умолчанию", model_label),
            self._metric_row("OCR", "готов" if ocr_status.ready else "не готов"),
            self._preview_row("Сообщение OCR", ocr_status.message),
            self._metric_row("Режим обработки", active_mode),
            self._metric_row("Устройство генерации", device_map.get(self.settings.values.generation_device, "Авто")),
            self._metric_row("Сеть", "полностью заблокирована" if self.settings.values.network_disabled else "разрешён только localhost"),
        ]

        storage_rows = [
            self._path_row("База SQLite", self.database.path),
            self._path_row("Файл настроек", self.settings.settings_path),
            self._path_row("Папка логов", logs_dir()),
            self._path_row("Папка экспорта", exports_dir()),
            self._path_row("Папка данных приложения", self.settings.data_dir),
        ]

        performance_rows = [
            self._metric_row("Сгенерировано ответов", str(self.analytics.total_generated())),
            self._metric_row("Среднее SLA", self._format_duration(average_generation_ms)),
            self._metric_row("Самое долгое SLA", self._format_duration(slowest_generation_ms)),
            self._metric_row("OCR-движок", self.settings.values.ocr_engine),
            self._metric_row("Языки OCR", ", ".join(self.settings.values.ocr_languages)),
        ]

        self._replace_section_rows(self.diagnostics_runtime_section, runtime_rows)
        self._replace_section_rows(self.diagnostics_storage_section, storage_rows)
        self._replace_section_rows(self.diagnostics_performance_section, performance_rows)

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

    def _path_row(self, title: str, path: Path) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)

        text_box = QVBoxLayout()
        label = QLabel(title)
        label.setStyleSheet("font-weight: 600;")
        hint = QLabel(str(path))
        hint.setObjectName("Subtle")
        hint.setWordWrap(True)
        text_box.addWidget(label)
        text_box.addWidget(hint)

        button = QPushButton("Перейти")
        button.setObjectName("Ghost")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedWidth(88)
        button.clicked.connect(lambda: self._open_path(path))

        layout.addLayout(text_box, 1)
        layout.addWidget(button, 0, Qt.AlignmentFlag.AlignTop)
        return row

    def _open_path(self, path: Path) -> None:
        try:
            target = path if path.exists() else path.parent
            if os.name == "nt":
                if path.exists() and path.is_file():
                    subprocess.run(["explorer", "/select,", str(path)], check=False)
                else:
                    os.startfile(str(target))
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        except Exception as exc:
            QMessageBox.warning(self, "Не удалось открыть путь", str(exc))

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

    @staticmethod
    def _format_duration(milliseconds: int | float) -> str:
        if not milliseconds:
            return "нет данных"
        seconds = float(milliseconds) / 1000
        if seconds < 60:
            return f"{seconds:.1f} сек"
        minutes = int(seconds // 60)
        rest = int(seconds % 60)
        return f"{minutes} мин {rest} сек"

    def _export_analytics_chart(self) -> None:
        topics = self.analytics.top_topics(limit=12)
        if not topics:
            QMessageBox.information(
                self,
                "Нет данных",
                "Диаграмму можно выгрузить после нескольких сгенерированных ответов.",
            )
            return

        default_name = f"analytics_topics_{datetime.now():%Y-%m-%d_%H-%M}.png"
        default_path = exports_dir() / default_name
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Выгрузить диаграмму",
            str(default_path),
            "PNG image (*.png)",
        )
        if not filename:
            return

        path = Path(filename)
        if path.suffix.lower() != ".png":
            path = path.with_suffix(".png")

        try:
            self._render_topics_chart(path, topics)
            QMessageBox.information(self, "Готово", f"Диаграмма сохранена:\n{path}")
        except Exception as exc:
            QMessageBox.warning(self, "Экспорт не удался", str(exc))

    def _render_topics_chart(self, path: Path, topics: list[tuple[str, int]]) -> None:
        width = 1200
        row_height = 58
        top_padding = 150
        left_padding = 310
        right_padding = 90
        bottom_padding = 80
        height = max(520, top_padding + bottom_padding + row_height * len(topics))

        is_light = self.settings.values.theme == "light"
        background = QColor("#f4f7fb" if is_light else "#0f131a")
        card = QColor("#ffffff" if is_light else "#171d26")
        text = QColor("#0f172a" if is_light else "#f4f7fb")
        muted = QColor("#64748b" if is_light else "#9aa7bd")
        grid = QColor("#d7dfeb" if is_light else "#283241")
        bar = QColor("#2f7cf6")
        bar_shadow = QColor("#8bb8ff" if is_light else "#164b9c")

        pixmap = QPixmap(width, height)
        pixmap.fill(background)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(card)
            painter.drawRoundedRect(32, 28, width - 64, height - 56, 18, 18)

            painter.setPen(text)
            title_font = QFont("Segoe UI", 26, QFont.Weight.Bold)
            painter.setFont(title_font)
            painter.drawText(72, 86, "Аналитика обращений")

            painter.setPen(muted)
            subtitle_font = QFont("Segoe UI", 13)
            painter.setFont(subtitle_font)
            generated_at = datetime.now().strftime("%d.%m.%Y %H:%M")
            painter.drawText(72, 118, f"Количество по темам · выгружено {generated_at}")

            max_count = max(count for _, count in topics) or 1
            chart_left = left_padding
            chart_top = top_padding
            chart_width = width - left_padding - right_padding
            max_bar_width = chart_width - 90

            painter.setPen(grid)
            painter.drawLine(chart_left, chart_top - 18, chart_left + max_bar_width, chart_top - 18)

            label_font = QFont("Segoe UI", 13, QFont.Weight.DemiBold)
            value_font = QFont("Segoe UI", 14, QFont.Weight.Bold)
            small_font = QFont("Segoe UI", 11)

            for index, (topic, count) in enumerate(topics):
                y = chart_top + index * row_height
                bar_width = max(10, int(max_bar_width * (count / max_count)))

                painter.setFont(label_font)
                painter.setPen(text)
                label = painter.fontMetrics().elidedText(topic, Qt.TextElideMode.ElideRight, left_padding - 110)
                painter.drawText(72, y + 28, label)

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(bar_shadow)
                painter.drawRoundedRect(chart_left, y + 7, max_bar_width, 22, 11, 11)
                painter.setBrush(bar)
                painter.drawRoundedRect(chart_left, y + 7, bar_width, 22, 11, 11)

                painter.setFont(value_font)
                painter.setPen(text)
                painter.drawText(chart_left + max_bar_width + 18, y + 27, str(count))

                painter.setFont(small_font)
                painter.setPen(muted)
                percent = round(count / sum(value for _, value in topics) * 100)
                painter.drawText(chart_left + max_bar_width + 18, y + 45, f"{percent}%")

            painter.setPen(muted)
            painter.setFont(small_font)
            painter.drawText(72, height - 56, "Local Support AI · локальный отчёт из SQLite")
        finally:
            painter.end()

        path.parent.mkdir(parents=True, exist_ok=True)
        if not pixmap.save(str(path), "PNG"):
            raise RuntimeError("Не удалось сохранить PNG-файл.")

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
            generation_device=self.generation_device.currentData() or "auto",
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
