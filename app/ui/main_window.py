from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
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
from app.ui.widgets import AnalyticsChips, CaseInsightPanel, StatusPill, ToggleSwitch
from app.ui.workers import (
    BackendAnalyzeWorker,
    BackendGenerateWorker,
    BackendPreviewWorker,
    GenerateWorker,
    OCRWorker,
    start_worker,
)
from app.utils.image_utils import (
    SUPPORTED_IMAGE_EXTENSIONS,
    image_path_to_base64,
    load_pixmap,
    qimage_to_base64,
    qimage_to_png_bytes,
)


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
        self.last_preview_payload: dict | None = None
        self.stage_metrics: dict[str, float | None] = {
            "ocr_ms": None,
            "analyze_ms": None,
            "preview_ms": None,
            "generate_ms": None,
        }
        self._busy = False
        self._autofinalize_after_preview = False
        self._negative_feedback_requested = False
        self.threads = []
        self.workers = []

        self.setWindowTitle("Local Support AI")
        icon_path = Path(__file__).resolve().parents[2] / "assets" / "app_icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1320, 820)
        self.setMinimumSize(980, 640)
        self.setAcceptDrops(True)

        self._build_ui()
        self._apply_icon_set()
        self._bind_shortcuts()
        self._apply_window_settings()
        self._apply_expert_mode(self.settings.values.expert_mode, persist=False)
        self._apply_theme_button_state()
        self.refresh_status()
        self.apply_processing_mode()
        self.update_case_summary()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("AppShell")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_top_bar())

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(18, 18, 18, 14)
        content_layout.setSpacing(16)
        self.left_rail = self._build_left_rail()
        content_layout.addWidget(self.left_rail, 0)
        content_layout.addWidget(self._build_main_column(), 5)
        self.summary_column = self._build_summary_column()
        self.expert_sidebar = self._build_expert_sidebar()
        content_layout.addWidget(self.summary_column, 2)
        content_layout.addWidget(self.expert_sidebar, 2)
        outer.addWidget(content, 1)

        outer.addWidget(self._build_footer())
        self.setCentralWidget(root)

    def _build_top_bar(self) -> QWidget:
        top = QWidget()
        top.setObjectName("TopBar")
        layout = QHBoxLayout(top)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(14)

        self.logo_label = QLabel()
        self.logo_label.setObjectName("LogoMark")
        self.logo_label.setFixedSize(22, 22)
        brand_box = QVBoxLayout()
        brand_box.setSpacing(0)
        title = QLabel("Local Support AI")
        title.setObjectName("Title")
        brand_box.addWidget(title)

        self.local_status = StatusPill("Local", True)
        self.ready_status = StatusPill("Готово", True)

        expert_box = QWidget()
        expert_layout = QHBoxLayout(expert_box)
        expert_layout.setContentsMargins(0, 0, 0, 0)
        expert_layout.setSpacing(8)
        expert_label = QLabel("Expert")
        expert_label.setObjectName("Subtle")
        self.expert_toggle = ToggleSwitch()
        self.expert_toggle.setChecked(self.settings.values.expert_mode)
        self.expert_toggle.toggled.connect(self._expert_toggled)
        expert_layout.addWidget(expert_label)
        expert_layout.addWidget(self.expert_toggle)

        self.theme_button = QPushButton()
        self.theme_button.setObjectName("IconButton")
        self.theme_button.setFixedSize(38, 38)
        self.theme_button.clicked.connect(self._toggle_theme)

        self.menu_button = QPushButton()
        self.menu_button.setObjectName("IconButton")
        self.menu_button.setFixedSize(38, 38)
        self.menu_button.clicked.connect(self.open_settings)

        layout.addWidget(self.logo_label)
        layout.addLayout(brand_box)
        layout.addStretch(1)
        layout.addWidget(self.local_status)
        layout.addWidget(self.ready_status)
        layout.addWidget(expert_box)
        layout.addWidget(self.theme_button)
        layout.addWidget(self.menu_button)
        return top

    def _build_left_rail(self) -> QFrame:
        rail = QFrame()
        rail.setObjectName("Rail")
        rail.setFixedWidth(58)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(10)

        self.rail_buttons_group = QButtonGroup(self)
        self.rail_buttons_group.setExclusive(True)
        self.rail_buttons: list[QPushButton] = []
        self.rail_icon_names: list[str] = []
        buttons = [
            ("plus", "Новое обращение"),
            ("message", "Текущий экран"),
            ("analytics", "OCR и скриншоты"),
            ("bookmark", "Стили ответов"),
            ("history", "История и SLA"),
        ]
        for index, (icon_name, tooltip) in enumerate(buttons):
            button = QPushButton()
            button.setObjectName("RailButton")
            button.setCheckable(True)
            button.setToolTip(tooltip)
            button.setFixedSize(40, 40)
            self.rail_icon_names.append(icon_name)
            if icon_name == "plus":
                button.clicked.connect(self.clear_all)
            elif icon_name == "message":
                button.clicked.connect(lambda: self.customer_text.setFocus())
            elif icon_name == "analytics":
                button.clicked.connect(lambda: self.open_settings(tab_index=0))
            elif icon_name == "bookmark":
                button.clicked.connect(lambda: self.open_settings(tab_index=2))
            elif icon_name == "history":
                button.clicked.connect(lambda: self.open_settings(tab_index=3))
            else:
                button.clicked.connect(lambda checked=False: self._expert_toggled(True))
            self.rail_buttons_group.addButton(button, index)
            layout.addWidget(button)
            self.rail_buttons.append(button)
        if len(self.rail_buttons) > 1:
            self.rail_buttons[1].setChecked(True)
        layout.addStretch(1)
        return rail

    def _build_main_column(self) -> QWidget:
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.message_card = self._build_message_card()
        self.answer_card = self._build_answer_card()
        self.section_divider = QFrame()
        self.section_divider.setObjectName("SectionDivider")
        self.section_divider.setFixedHeight(1)
        layout.addWidget(self.message_card, 3)
        layout.addWidget(self.section_divider)
        layout.addWidget(self.answer_card, 4)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 14, 0)
        bottom_row.setSpacing(10)
        self.clear_button = QPushButton("Очистить")
        self.clear_button.setObjectName("Ghost")
        self.clear_button.clicked.connect(self.clear_all)
        self.primary_action_button = QPushButton("Подготовить ответ  →")
        self.primary_action_button.setObjectName("HeroButton")
        self.primary_action_button.clicked.connect(self.prepare_answer)
        bottom_row.addWidget(self.clear_button)
        bottom_row.addStretch(1)
        bottom_row.addWidget(self.primary_action_button)
        layout.addLayout(bottom_row)
        return column

    def _build_message_card(self) -> QFrame:
        frame = self._create_panel("Сообщение клиента")
        frame.setProperty("flat_section", True)
        layout = frame.layout()
        layout.setSpacing(12)

        self.customer_box = QFrame()
        self.customer_box.setObjectName("InputBox")
        customer_box_layout = QVBoxLayout(self.customer_box)
        customer_box_layout.setContentsMargins(1, 1, 1, 1)
        customer_box_layout.setSpacing(0)
        self.customer_text = QPlainTextEdit()
        self.customer_text.setObjectName("CustomerEditor")
        self.customer_text.setPlaceholderText("Вставьте сообщение клиента или переписку. Скриншот можно добавить из буфера или выбрать файлом.")
        self.customer_text.setFixedHeight(210)
        self.customer_text.textChanged.connect(self.update_case_summary)
        self.customer_text.textChanged.connect(self._update_message_counter)
        customer_box_layout.addWidget(self.customer_text)
        layout.addWidget(self.customer_box)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.screenshot_button = QPushButton("Скриншот")
        self.screenshot_button.setObjectName("Ghost")
        self.screenshot_button.setMinimumWidth(104)
        self.screenshot_button.setToolTip("Добавить скриншот")
        self.screenshot_button.clicked.connect(self.open_image_dialog)
        self.ocr_only_button = QPushButton("OCR со скриншота")
        self.ocr_only_button.setObjectName("Ghost")
        self.ocr_only_button.setMinimumWidth(156)
        self.ocr_only_button.clicked.connect(self._manual_ocr_only)
        self.remove_screenshot_button = QPushButton("Убрать")
        self.remove_screenshot_button.setObjectName("Tiny")
        self.remove_screenshot_button.clicked.connect(self._clear_image_only)
        self.remove_screenshot_button.setVisible(False)
        self.attachment_label = QLabel("Скриншот не добавлен")
        self.attachment_label.setObjectName("Subtle")
        self.message_count_label = QLabel("0/4000")
        self.message_count_label.setObjectName("Subtle")
        actions.addWidget(self.screenshot_button)
        actions.addWidget(self.ocr_only_button)
        actions.addWidget(self.remove_screenshot_button)
        actions.addWidget(self.attachment_label, 1)
        actions.addWidget(self.message_count_label)
        layout.addLayout(actions)
        return frame

    def _build_answer_card(self) -> QFrame:
        frame = self._create_panel("Итоговый ответ")
        frame.setProperty("flat_section", True)
        layout = frame.layout()

        header_title = layout.itemAt(0).widget()
        if header_title is not None:
            layout.removeWidget(header_title)
            header_title.deleteLater()

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)
        title = QLabel("Итоговый ответ")
        title.setObjectName("PanelTitle")
        title.setMinimumWidth(150)
        header_row.addWidget(title, 0, Qt.AlignmentFlag.AlignVCenter)
        header_row.addStretch(1)

        self.answer_copy_icon = QPushButton()
        self.answer_copy_icon.setObjectName("IconButton")
        self.answer_copy_icon.setProperty("variant", "action")
        self.answer_copy_icon.setToolTip("Копировать ответ")
        self.answer_copy_icon.clicked.connect(self.copy_reply)
        self.answer_save_icon = QPushButton()
        self.answer_save_icon.setObjectName("IconButton")
        self.answer_save_icon.setProperty("variant", "action")
        self.answer_save_icon.setToolTip("Сохранить как удачный стиль")
        self.answer_save_icon.clicked.connect(self.save_reply_to_style)
        self.answer_like_icon = QPushButton()
        self.answer_like_icon.setObjectName("IconButton")
        self.answer_like_icon.setProperty("variant", "action")
        self.answer_like_icon.setToolTip("Ответ удачный")
        self.answer_like_icon.clicked.connect(self.mark_response_correct)
        self.answer_dislike_icon = QPushButton()
        self.answer_dislike_icon.setObjectName("IconButton")
        self.answer_dislike_icon.setProperty("variant", "action")
        self.answer_dislike_icon.setToolTip("Нужно исправить ответ")
        self.answer_dislike_icon.clicked.connect(self._toggle_negative_feedback)
        self.answer_rerun_icon = QPushButton()
        self.answer_rerun_icon.setObjectName("IconButton")
        self.answer_rerun_icon.setProperty("variant", "action")
        self.answer_rerun_icon.setToolTip("Сгенерировать заново")
        self.answer_rerun_icon.clicked.connect(self.prepare_answer)
        for button in [
            self.answer_copy_icon,
            self.answer_save_icon,
            self.answer_like_icon,
            self.answer_dislike_icon,
            self.answer_rerun_icon,
        ]:
            button.setFixedSize(28, 28)
            header_row.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(header_row)

        self.response_box = QFrame()
        self.response_box.setObjectName("ResponseBox")
        response_box_layout = QVBoxLayout(self.response_box)
        response_box_layout.setContentsMargins(1, 1, 1, 1)
        response_box_layout.setSpacing(0)
        self.response_text = QPlainTextEdit()
        self.response_text.setObjectName("ResponseEditor")
        self.response_text.setPlaceholderText("Готовый ответ появится здесь.")
        self.response_text.setMinimumHeight(280)
        self.response_text.textChanged.connect(self._refresh_response_actions)
        response_box_layout.addWidget(self.response_text)
        layout.addWidget(self.response_box, 1)

        self.analytics_chips = AnalyticsChips()
        layout.addWidget(self.analytics_chips)

        feedback_row = QHBoxLayout()
        feedback_row.setContentsMargins(0, 4, 0, 0)
        feedback_row.setSpacing(8)
        self.feedback_caption = QLabel("Полезно?")
        self.feedback_caption.setObjectName("Subtle")
        self.feedback_positive_button = QPushButton()
        self.feedback_positive_button.setObjectName("Tiny")
        self.feedback_positive_button.setFixedSize(36, 32)
        self.feedback_positive_button.setToolTip("Отметить ответ как удачный")
        self.feedback_positive_button.clicked.connect(self.mark_response_correct)
        self.feedback_negative_button = QPushButton()
        self.feedback_negative_button.setObjectName("Tiny")
        self.feedback_negative_button.setFixedSize(36, 32)
        self.feedback_negative_button.setToolTip("Показать сохранение исправленного ответа")
        self.feedback_negative_button.clicked.connect(self._toggle_negative_feedback)
        self.copy_button = QPushButton("Копировать")
        self.copy_button.setObjectName("Ghost")
        self.copy_button.setMinimumWidth(108)
        self.copy_button.clicked.connect(self.copy_reply)
        self.save_to_style_button = QPushButton("Сохранить как удачный стиль")
        self.save_to_style_button.setObjectName("Ghost")
        self.save_to_style_button.setMinimumWidth(210)
        self.save_to_style_button.clicked.connect(self.save_reply_to_style)
        feedback_row.addWidget(self.feedback_caption)
        feedback_row.addWidget(self.feedback_positive_button)
        feedback_row.addWidget(self.feedback_negative_button)
        feedback_row.addStretch(1)
        feedback_row.addWidget(self.save_to_style_button)
        feedback_row.addWidget(self.copy_button)
        layout.addLayout(feedback_row)

        self.response_feedback_save_button = QPushButton("Сохранить исправленный ответ")
        self.response_feedback_save_button.setObjectName("Tiny")
        self.response_feedback_save_button.clicked.connect(self.save_corrected_response)
        self.response_feedback_save_button.setVisible(False)
        layout.addWidget(self.response_feedback_save_button, 0, Qt.AlignmentFlag.AlignLeft)
        return frame

    def _build_summary_column(self) -> QWidget:
        column = QWidget()
        column.setFixedWidth(260)
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.summary_card = self._create_panel("Аналитика")
        summary_layout = self.summary_card.layout()

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)
        self.summary_source_label = QLabel("Ожидание")
        self.summary_source_label.setObjectName("InsightSource")
        header_row.addWidget(self.summary_source_label, 0, Qt.AlignmentFlag.AlignLeft)
        header_row.addStretch(1)
        summary_layout.addLayout(header_row)

        self.summary_topic_value = self._summary_value("")
        self.summary_tone_value = self._summary_value("")
        self.summary_risk_value = self._summary_value("")
        self.summary_priority_value = self._summary_value("")
        self.summary_style_value = self._summary_value("")

        summary_layout.addWidget(self._summary_pair("Тема", self.summary_topic_value))
        summary_layout.addWidget(self._summary_pair("Тон", self.summary_tone_value))
        summary_layout.addWidget(self._summary_pair("Риск эскалации", self.summary_risk_value))
        summary_layout.addWidget(self._summary_pair("Приоритет", self.summary_priority_value))
        summary_layout.addWidget(self._summary_pair("Стиль", self.summary_style_value))

        self.summary_signal_chips = AnalyticsChips()
        summary_layout.addWidget(self.summary_signal_chips)
        self.summary_details_label = QLabel("Появится после анализа обращения.")
        self.summary_details_label.setObjectName("Subtle")
        self.summary_details_label.setWordWrap(True)
        summary_layout.addWidget(self.summary_details_label)

        self.topic_override_toggle = QPushButton("Исправить тему")
        self.topic_override_toggle.setObjectName("Ghost")
        self.topic_override_toggle.clicked.connect(self._toggle_topic_override)
        summary_layout.addWidget(self.topic_override_toggle, 0, Qt.AlignmentFlag.AlignLeft)

        self.topic_override_combo = QComboBox()
        self.topic_override_combo.setEditable(True)
        self.topic_override_combo.addItems(self._available_topics())
        self.topic_override_save_button = QPushButton("Сохранить тему")
        self.topic_override_save_button.setObjectName("Tiny")
        self.topic_override_save_button.clicked.connect(self.save_topic_correction)

        self.topic_override_container = QWidget()
        override_layout = QHBoxLayout(self.topic_override_container)
        override_layout.setContentsMargins(0, 0, 0, 0)
        override_layout.setSpacing(8)
        override_layout.addWidget(self.topic_override_combo, 1)
        override_layout.addWidget(self.topic_override_save_button)
        self.topic_override_container.setVisible(False)
        summary_layout.addWidget(self.topic_override_container)
        layout.addWidget(self.summary_card)
        layout.addStretch(1)
        return column

    def _build_expert_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(270)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        ocr_card = self._create_panel("OCR preview")
        ocr_layout = ocr_card.layout()
        self.expert_image_label = QLabel("Скриншот не добавлен")
        self.expert_image_label.setObjectName("Hint")
        self.expert_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.expert_image_label.setMinimumHeight(150)
        self.expert_image_label.setFrameShape(QFrame.Shape.StyledPanel)
        self.expert_image_label.setStyleSheet("border-radius: 8px;")
        ocr_layout.addWidget(self.expert_image_label)

        self.ocr_text = QPlainTextEdit()
        self.ocr_text.setPlaceholderText("Распознанный текст со скриншота появится здесь.")
        self.ocr_text.setMinimumHeight(120)
        self.ocr_text.textChanged.connect(self.update_case_summary)
        ocr_layout.addWidget(self.ocr_text)

        ocr_actions = QHBoxLayout()
        self.ocr_feedback_correct_button = QPushButton("OCR верно")
        self.ocr_feedback_correct_button.setObjectName("Tiny")
        self.ocr_feedback_correct_button.clicked.connect(self.mark_ocr_correct)
        self.ocr_feedback_save_button = QPushButton("Сохранить исправленный текст")
        self.ocr_feedback_save_button.setObjectName("Tiny")
        self.ocr_feedback_save_button.clicked.connect(self.save_corrected_ocr_text)
        ocr_actions.addWidget(self.ocr_feedback_correct_button)
        ocr_actions.addWidget(self.ocr_feedback_save_button)
        ocr_layout.addLayout(ocr_actions)
        layout.addWidget(ocr_card)
        self.ocr_card = ocr_card

        style_card = self._create_panel("Стиль")
        style_layout = style_card.layout()
        self.current_style_name = QLabel("Не выбран")
        self.current_style_name.setObjectName("PanelTitle")
        self.current_style_tone = QLabel("—")
        self.current_style_tone.setObjectName("Subtle")
        style_layout.addWidget(self.current_style_name)
        style_layout.addWidget(self.current_style_tone)
        self.current_style_pill = QLabel("Не выбран")
        self.current_style_pill.setObjectName("InsightChip")
        style_layout.addWidget(self.current_style_pill, 0, Qt.AlignmentFlag.AlignLeft)
        style_layout.addStretch(1)
        layout.addWidget(style_card)

        recent_styles_card = self._create_panel("Последние стили")
        recent_layout = recent_styles_card.layout()
        self.recent_styles_labels: list[QLabel] = []
        for index in range(3):
            label = QLabel("—")
            label.setObjectName("RecentStylePrimary" if index == 0 else "Subtle")
            recent_layout.addWidget(label)
            self.recent_styles_labels.append(label)
        self.show_more_styles_button = QPushButton("Показать больше")
        self.show_more_styles_button.setObjectName("Ghost")
        self.show_more_styles_button.clicked.connect(self.open_settings)
        recent_layout.addWidget(self.show_more_styles_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(recent_styles_card)
        self.recent_styles_card = recent_styles_card

        knowledge_card = self._create_panel("Использованные знания")
        knowledge_layout = knowledge_card.layout()
        self.knowledge_status_label = QLabel("Ожидание")
        self.knowledge_status_label.setObjectName("InsightSource")
        knowledge_layout.addWidget(self.knowledge_status_label, 0, Qt.AlignmentFlag.AlignLeft)
        self.knowledge_details_label = QLabel("Факты появятся после подготовки ответа.")
        self.knowledge_details_label.setObjectName("Subtle")
        self.knowledge_details_label.setWordWrap(True)
        knowledge_layout.addWidget(self.knowledge_details_label)
        layout.addWidget(knowledge_card)
        self.knowledge_card = knowledge_card

        status_card = self._create_panel("Статусы")
        status_layout = status_card.layout()
        self.backend_status_value = self._status_row(status_layout, "Backend")
        self.model_status_value = self._status_row(status_layout, "Модель")
        self.ocr_status_value = self._status_row(status_layout, "OCR")
        self.expert_sla_label = QLabel("SLA по этапам появится после подготовки ответа.")
        self.expert_sla_label.setObjectName("Subtle")
        self.expert_sla_label.setWordWrap(True)
        status_layout.addWidget(self.expert_sla_label)

        self.expert_debug_label = QLabel("")
        self.expert_debug_label.setObjectName("Subtle")
        self.expert_debug_label.setWordWrap(True)
        self.expert_debug_label.setVisible(False)
        status_layout.addWidget(self.expert_debug_label)

        controls_row = QHBoxLayout()
        self.model_combo = QComboBox()
        self.model_combo.currentTextChanged.connect(self._model_changed)
        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.setObjectName("Ghost")
        self.refresh_button.clicked.connect(self.refresh_status)
        controls_row.addWidget(self.model_combo, 1)
        controls_row.addWidget(self.refresh_button)
        status_layout.addLayout(controls_row)
        layout.addWidget(status_card)
        self.statuses_card = status_card
        self.detail_card = None
        return sidebar

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setObjectName("TopBar")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(18, 8, 18, 10)
        layout.setSpacing(12)
        self.runtime_note_label = QLabel("Локальная модель: —")
        self.runtime_note_label.setObjectName("Subtle")
        self.status_message = QLabel("Готово к локальной работе.")
        self.status_message.setObjectName("Subtle")
        self.status_message.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.runtime_note_label, 1)
        layout.addWidget(self.status_message, 2)
        return footer

    def _icon_color(self) -> str:
        return "#111827" if self.settings.values.theme == "light" else "#E5E7EB"

    def _render_icon(self, name: str, size: int = 18, color: str | None = None) -> QIcon:
        icon_path = Path(__file__).resolve().parents[2] / "assets" / "icons" / f"{name}.svg"
        if not icon_path.exists():
            icon_path = Path(__file__).resolve().parents[2] / "assets" / "icons" / "moon.svg"
        svg_text = icon_path.read_text(encoding="utf-8").replace("currentColor", color or self._icon_color())
        renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

    def _set_button_icon(
        self,
        button: QPushButton,
        icon_name: str,
        tooltip: str,
        *,
        size: int = 18,
        color: str | None = None,
        text: str | None = None,
    ) -> None:
        button.setIcon(self._render_icon(icon_name, size=size, color=color))
        button.setIconSize(QSize(size, size))
        button.setToolTip(tooltip)
        if text is not None:
            button.setText(text)

    def _apply_icon_set(self) -> None:
        color = self._icon_color()
        white = "#FFFFFF"

        self.logo_label.setPixmap(self._render_icon("logo-mark", size=20).pixmap(20, 20))

        theme_icon = "moon" if self.settings.values.theme == "light" else "sun"
        self._set_button_icon(self.theme_button, theme_icon, " ", color=color)
        self._set_button_icon(self.menu_button, "menu", "Открыть меню", color=color)

        for button, icon_name in zip(self.rail_buttons, self.rail_icon_names):
            self._set_button_icon(button, icon_name, button.toolTip(), color=color, text="")

        self._set_button_icon(self.screenshot_button, "attachment", "Добавить скриншот", color=color, text="Скриншот")
        self._set_button_icon(self.ocr_only_button, "camera", "OCR со скриншота", color=color, text="OCR со скриншота")

        self._set_button_icon(self.answer_copy_icon, "copy", "Копировать ответ", color=color, text="")
        self._set_button_icon(self.answer_save_icon, "bookmark", "Сохранить как удачный стиль", color=color, text="")
        self._set_button_icon(self.answer_like_icon, "thumbs-up", "Ответ удачный", color=color, text="")
        self._set_button_icon(self.answer_dislike_icon, "thumbs-down", "Нужно исправить ответ", color=color, text="")
        self._set_button_icon(self.answer_rerun_icon, "refresh", "Сгенерировать заново", color=color, text="")

        self._set_button_icon(self.feedback_positive_button, "thumbs-up", "Отметить ответ как удачный", size=16, color=color, text="")
        self._set_button_icon(self.feedback_negative_button, "thumbs-down", "Исправить ответ", size=16, color=color, text="")
        self._set_button_icon(self.primary_action_button, "magic", "Подготовить ответ", size=16, color=white, text="Подготовить ответ  →")

    @staticmethod
    def _create_panel(title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        label = QLabel(title)
        label.setObjectName("PanelTitle")
        layout.addWidget(label)
        return frame

    @staticmethod
    def _summary_value(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("InsightMetaValue")
        label.setWordWrap(True)
        return label

    @staticmethod
    def _summary_pair(title: str, value_label: QLabel) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("Subtle")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return row

    @staticmethod
    def _status_row(layout: QVBoxLayout, title: str) -> QLabel:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        left = QLabel(title)
        left.setObjectName("Subtle")
        right = QLabel("—")
        right.setObjectName("InsightMetaValue")
        row_layout.addWidget(left)
        row_layout.addStretch(1)
        row_layout.addWidget(right)
        layout.addWidget(row)
        return right

    def _bind_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.open_image_dialog)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.prepare_answer)
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.clear_all)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, activated=self.copy_reply)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self.open_settings)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=lambda: self.expert_toggle.toggle())

    def _available_topics(self) -> list[str]:
        topics = [
            "Общее обращение",
            "Проценты / кредит наличными",
            "Проценты / кредитная карта",
            "Проценты / кредит",
            "Дебетовая карта / кэшбэк",
            "Дебетовая карта / переводы и лимиты",
            "Вклад / проценты",
            "Вклад / пополнение и закрытие",
            "Накопительный счет / проценты",
        ]
        topics.extend(topic for topic, _ in self.case_analyzer.TOPIC_RULES)
        result: list[str] = []
        seen: set[str] = set()
        for topic in topics:
            clean = topic.strip()
            key = clean.lower()
            if clean and key not in seen:
                seen.add(key)
                result.append(clean)
        return result

    def _model_changed(self, model: str) -> None:
        if model:
            self.settings.update(preferred_model=model)
            self.runtime_note_label.setText(f"Локальная модель: {model}")

    def _set_stage_metric(self, key: str, elapsed_ms: float | None) -> None:
        if key in self.stage_metrics:
            self.stage_metrics[key] = elapsed_ms if elapsed_ms and elapsed_ms > 0 else None
            self._update_sla_message()

    def _reset_stage_metrics(self) -> None:
        for key in self.stage_metrics:
            self.stage_metrics[key] = None
        self._update_sla_message()

    def _update_sla_message(self) -> None:
        if not any(self.stage_metrics.values()):
            self.expert_sla_label.setText("SLA по этапам появится после подготовки ответа.")
            return
        parts = [
            f"OCR {self._format_duration(self.stage_metrics['ocr_ms'])}",
            f"Анализ {self._format_duration(self.stage_metrics['analyze_ms'])}",
            f"Preview {self._format_duration(self.stage_metrics['preview_ms'])}",
            f"Генерация {self._format_duration(self.stage_metrics['generate_ms'])}",
        ]
        self.expert_sla_label.setText("SLA: " + " • ".join(parts))

    def refresh_status(self) -> None:
        self.local_status.set_state("Local", not self.settings.values.network_disabled)
        if self.settings.values.network_disabled:
            self.local_status.set_state("Offline strict", True)

        ocr_ready = True
        if self.settings.values.processing_mode == "text_only":
            self.ocr_status_value.setText("Скрыт")
        elif self.settings.values.use_ocr:
            ocr_status = self.ocr_manager.status()
            ocr_ready = ocr_status.ready
            self.ocr_status_value.setText("Готов" if ocr_status.ready else "Не готов")
        else:
            self.ocr_status_value.setText("Выключен")

        status = self.ai_manager.check_status()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        models = status.supported_models or status.installed_models
        self.model_combo.addItems(models)
        preferred = self.settings.values.preferred_model
        if preferred and preferred in models:
            self.model_combo.setCurrentText(preferred)
        elif models:
            self.model_combo.setCurrentText(models[0])
            self.settings.update(preferred_model=models[0])
        self.model_combo.blockSignals(False)

        model_ready = bool(status.supported_models)
        self.ready_status.set_state("Ready", model_ready and ocr_ready)
        self.backend_status_value.setText("Local FastAPI")
        self.model_status_value.setText(self.model_combo.currentText() or "Не найдена")
        self.runtime_note_label.setText(
            f"Локальная модель: {self.model_combo.currentText() or 'не выбрана'}"
        )
        if model_ready:
            self._set_status("Локальный backend и модель готовы к работе.")
        else:
            self._set_status("Не удалось подготовить модель. Проверьте Ollama или список моделей.")
            self._set_expert_debug(status.message)
        self._refresh_primary_action_state()

    def apply_processing_mode(self) -> None:
        text_only = self.settings.values.processing_mode == "text_only"
        self.screenshot_button.setEnabled(not text_only)
        has_image = bool(self.current_image_path)
        self.remove_screenshot_button.setEnabled(not text_only and has_image)
        self.remove_screenshot_button.setVisible(not text_only and has_image)
        self.ocr_card.setVisible(self.settings.values.expert_mode and not text_only)
        if text_only:
            self.attachment_label.setText("Режим только текста")
            self._clear_image_only()
        else:
            self._update_attachment_label()

    def _apply_window_settings(self) -> None:
        flags = self.windowFlags()
        if self.settings.values.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        if self.settings.values.compact_mode:
            self.resize(1240, 760)
        self.show()

    def _apply_theme_button_state(self) -> None:
        if self.settings.values.theme == "light":
            self.theme_button.setToolTip("Переключить на тёмную тему")
        else:
            self.theme_button.setToolTip("Переключить на светлую тему")
        self._apply_icon_set()

    def _toggle_theme(self) -> None:
        next_theme = "light" if self.settings.values.theme == "dark" else "dark"
        self.settings.update(theme=next_theme)
        app = QApplication.instance()
        if app:
            apply_theme(app, next_theme, self.settings.values.corner_radius, self.settings.values.button_style)
        self._apply_theme_button_state()

    def _expert_toggled(self, enabled: bool) -> None:
        self._apply_expert_mode(enabled, persist=True)

    def _apply_expert_mode(self, enabled: bool, *, persist: bool) -> None:
        self.left_rail.setVisible(enabled)
        self.summary_column.setVisible(enabled)
        self.expert_sidebar.setVisible(enabled)
        self.ocr_card.setVisible(enabled and self.settings.values.processing_mode != "text_only")
        self.statuses_card.setVisible(enabled)
        self.recent_styles_card.setVisible(enabled)
        if enabled:
            self.setMinimumSize(1240, 760)
            self.resize(1320, 820)
        else:
            self.setMinimumSize(980, 640)
            self.resize(1100, 760)
        if persist and self.settings.values.expert_mode != enabled:
            self.settings.update(expert_mode=enabled)
        self.expert_debug_label.setVisible(enabled and bool(self.expert_debug_label.text().strip()))

    def _update_message_counter(self) -> None:
        count = len(self.customer_text.toPlainText())
        self.message_count_label.setText(f"{count}/4000")

    def _update_attachment_label(self) -> None:
        if self.settings.values.processing_mode == "text_only":
            self.attachment_label.setText("Режим только текста")
            self.remove_screenshot_button.setVisible(False)
            return
        if self.current_image_path:
            self.attachment_label.setText(f"Скриншот: {self.current_image_path.name}")
            self.remove_screenshot_button.setVisible(True)
        else:
            self.attachment_label.setText("Скриншот не добавлен")
            self.remove_screenshot_button.setVisible(False)

    def _manual_ocr_only(self) -> None:
        if self.settings.values.processing_mode == "text_only":
            QMessageBox.information(self, "Режим только текста", "OCR со скриншота недоступен в режиме только текста.")
            return
        if not self.current_image_path:
            QMessageBox.information(self, "Нет скриншота", "Сначала добавьте скриншот.")
            return
        if not self.settings.values.use_ocr:
            QMessageBox.information(self, "OCR выключен", "Включите OCR в настройках, чтобы распознавать текст со скриншота.")
            return
        self._start_ocr()

    def _set_image_preview(self, pixmap) -> None:
        if pixmap is None or pixmap.isNull():
            self.expert_image_label.setText("Скриншот не добавлен")
            self.expert_image_label.setPixmap(QPixmap())
            return
        scaled = pixmap.scaled(
            self.expert_image_label.size() if self.expert_image_label.width() > 10 else self.expert_image_label.maximumSize(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.expert_image_label.setText("")
        self.expert_image_label.setPixmap(scaled)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.current_image_path:
            pixmap = load_pixmap(self.current_image_path)
            if pixmap is not None:
                self._set_image_preview(pixmap)

    def dragEnterEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls and Path(urls[0].toLocalFile()).suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls:
            path = Path(urls[0].toLocalFile())
            if path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                self.load_image(path)
                event.acceptProposedAction()
                return
        super().dropEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.StandardKey.Paste):
            clipboard = QApplication.clipboard()
            mime = clipboard.mimeData()
            if mime.hasImage():
                if self.settings.values.processing_mode == "text_only":
                    self._set_status("Скриншот пропущен: сейчас включён режим только текста.")
                    return
                image = clipboard.image()
                self.current_clipboard_image_base64 = qimage_to_base64(image)
                temp_path = self.settings.data_dir / "clipboard_image.png"
                temp_path.write_bytes(qimage_to_png_bytes(image))
                self.load_image(temp_path, from_clipboard=True)
                self._set_status("Скриншот вставлен из буфера обмена.")
                return
        super().keyPressEvent(event)

    def open_image_dialog(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите скриншот",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if filename:
            self.load_image(Path(filename))

    def load_image(self, path: Path, *, from_clipboard: bool = False) -> None:
        if self.settings.values.processing_mode == "text_only":
            QMessageBox.information(
                self,
                "Режим только текста",
                "Сейчас включён режим только текста. Чтобы использовать скриншот, переключите режим в настройках.",
            )
            return
        pixmap = load_pixmap(path)
        if pixmap is None:
            QMessageBox.warning(self, "Не удалось открыть изображение", str(path))
            return
        self.current_image_path = path
        if not from_clipboard:
            self.current_clipboard_image_base64 = None
        self.last_ocr_raw_text = ""
        self.last_preview_payload = None
        self.last_generated_raw_response = ""
        self.last_generated_model = ""
        self.last_generated_style_id = None
        self._negative_feedback_requested = False
        self._set_image_preview(pixmap)
        self._set_ocr_feedback_enabled(False)
        self._refresh_response_actions()
        self._update_attachment_label()
        self._set_status(f"Скриншот добавлен: {path.name}")
        self._refresh_primary_action_state()

    def _clear_image_only(self) -> None:
        self.current_image_path = None
        self.current_clipboard_image_base64 = None
        self.last_ocr_raw_text = ""
        self.ocr_text.clear()
        self.expert_image_label.setText("Скриншот не добавлен")
        self.expert_image_label.setPixmap(QPixmap())
        self._update_attachment_label()
        self._set_ocr_feedback_enabled(False)
        self._refresh_primary_action_state()

    def prepare_answer(self) -> None:
        customer = self.customer_text.toPlainText().strip()
        ocr = self.ocr_text.toPlainText().strip()
        has_image = bool(self.current_image_path or self.current_clipboard_image_base64) and self.settings.values.processing_mode != "text_only"
        if not customer and not ocr and not has_image:
            QMessageBox.information(self, "Нет контекста", "Добавьте сообщение клиента или скриншот, чтобы подготовить ответ.")
            return

        self._autofinalize_after_preview = True
        self.last_preview_payload = None
        self.last_generated_raw_response = ""
        self._negative_feedback_requested = False
        self.response_text.clear()
        self._reset_stage_metrics()
        self._show_empty_knowledge()
        self._refresh_response_actions()

        if has_image and self.settings.values.use_ocr and not ocr:
            self._start_ocr()
            return
        if customer or ocr:
            self._start_final_generation()
            return
        self._start_final_generation()

    def _start_ocr(self) -> None:
        if not self.current_image_path:
            return
        self._set_busy(True, "Распознаю скриншот локально...")
        worker = OCRWorker(self.ocr_manager, self.current_image_path)
        worker.finished.connect(self._ocr_finished)
        worker.failed.connect(self._ocr_failed)
        worker.finished.connect(lambda *_: self._forget_worker(worker))
        worker.failed.connect(lambda *_: self._forget_worker(worker))
        self.workers.append(worker)
        self.threads.append(start_worker(worker))

    def _run_backend_analysis(self, customer_text: str, ocr_text: str) -> None:
        style = self.style_manager.get_style(self.settings.values.selected_style_id)
        self._set_busy(True, "Анализирую обращение через локальный backend...")
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

    def _run_hidden_preview(self) -> None:
        style = self.style_manager.get_style(self.settings.values.selected_style_id)
        self._set_busy(True, "Собираю факты и контекст ответа...")
        worker = BackendPreviewWorker(
            self.backend_client,
            customer_text=self.customer_text.toPlainText().strip(),
            ocr_text=self.ocr_text.toPlainText().strip(),
            selected_style=style.name if style else None,
        )
        worker.finished.connect(self._preview_finished)
        worker.failed.connect(self._preview_failed)
        worker.finished.connect(lambda *_: self._forget_worker(worker))
        worker.failed.connect(lambda *_: self._forget_worker(worker))
        self.workers.append(worker)
        self.threads.append(start_worker(worker))

    def _start_final_generation(self, preview_payload: dict | None = None) -> None:
        customer = self.customer_text.toPlainText().strip()
        ocr = self.ocr_text.toPlainText().strip()
        text_only = self.settings.values.processing_mode == "text_only"
        has_image = bool(self.current_image_path or self.current_clipboard_image_base64) and not text_only
        if not customer and not ocr and not has_image:
            return

        model = self.model_combo.currentText().strip() or self.settings.values.preferred_model
        style = self.style_manager.get_style(self.settings.values.selected_style_id)
        image_base64 = None if text_only else self.current_clipboard_image_base64
        if self.current_image_path and not text_only:
            image_base64 = image_path_to_base64(self.current_image_path)
        self._set_busy(True, "Готовлю итоговый ответ через FastAPI...")
        worker = BackendGenerateWorker(
            self.backend_client,
            customer_text=customer,
            ocr_text=ocr,
            selected_style=style.name if style else None,
            model=model,
            image_base64=image_base64,
        )
        style_id = style.id if style else None
        style_profile = style.profile if style else None
        worker.finished.connect(
            lambda payload, elapsed_ms: self._backend_generation_finished(
                payload,
                model,
                style_id,
                style_profile,
                elapsed_ms,
            )
        )
        worker.failed.connect(
            lambda message, elapsed_ms, customer_text=customer, ocr_text=ocr, m=model, sid=style_id, sprofile=style_profile, img=image_base64: self._backend_generation_failed(
                message,
                elapsed_ms,
                customer_text,
                ocr_text,
                m,
                sid,
                sprofile,
                img,
            )
        )
        worker.finished.connect(lambda *_: self._forget_worker(worker))
        worker.failed.connect(lambda *_: self._forget_worker(worker))
        self.workers.append(worker)
        self.threads.append(start_worker(worker))

    def _start_local_generation_fallback(
        self,
        customer_text: str,
        ocr_text: str,
        model: str,
        style_id: int | None,
        style_profile: dict | None,
        image_base64: str | None,
    ) -> None:
        selected_style = self.style_manager.get_style(style_id) if style_id else None
        style_prompt = self.style_manager.build_style_prompt(selected_style)
        quality_rules = self.learning_manager.build_quality_rules(style_profile)
        payload = self.last_preview_payload or {}
        topic_hint = str(payload.get("topic", "")).strip() or (self.last_case_analysis.topic if self.last_case_analysis else None)
        knowledge_facts = payload.get("knowledge_facts", []) if isinstance(payload, dict) else []
        if not isinstance(knowledge_facts, list):
            knowledge_facts = []

        self._set_busy(True, "Готовлю итоговый ответ локально...")
        worker = GenerateWorker(
            self.ai_manager,
            customer_text,
            ocr_text,
            style_prompt,
            quality_rules,
            model,
            image_base64,
            topic_hint=topic_hint,
            knowledge_facts=[str(item) for item in knowledge_facts][:2],
        )
        worker.finished.connect(
            lambda text, elapsed_ms: self._generation_finished(
                text,
                model,
                style_id,
                style_profile,
                elapsed_ms,
                source_label="локально (fallback)",
            )
        )
        worker.failed.connect(self._worker_failed)
        worker.finished.connect(lambda *_: self._forget_worker(worker))
        worker.failed.connect(lambda *_: self._forget_worker(worker))
        self.workers.append(worker)
        self.threads.append(start_worker(worker))

    def copy_reply(self) -> None:
        text = self.response_text.toPlainText().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
        self._set_status("Ответ скопирован в буфер обмена.")

    def save_reply_to_style(self) -> None:
        text = self.response_text.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Ответ пустой", "Сначала подготовьте или отредактируйте ответ.")
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
                    reply_style_label=updated.name,
                ).topic,
            )
            self.settings.update(selected_style_id=updated.id)
            self._refresh_style_summary()
            self._set_status(f"Ответ сохранён в стиль: {updated.name}")
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
        self.last_preview_payload = None
        self._negative_feedback_requested = False
        self._reset_stage_metrics()
        self._set_ocr_feedback_enabled(False)
        self._refresh_response_actions()
        self._show_empty_summary()
        self._clear_image_only()
        self._set_status("Экран очищен.")

    def open_settings(self, tab_index: int | None = None) -> None:
        dialog = SettingsDialog(
            self.settings,
            self.style_manager,
            self.database,
            self.ai_manager,
            self.ocr_manager,
            self,
        )
        if tab_index is not None and 0 <= tab_index < dialog.tabs.count():
            dialog.tabs.setCurrentIndex(tab_index)
        dialog.settingsChanged.connect(self._settings_changed)
        dialog.exec()

    def _ocr_finished(self, text: str, elapsed_ms: float) -> None:
        self._set_stage_metric("ocr_ms", elapsed_ms)
        self.last_ocr_raw_text = text or ""
        learned = self.learning_manager.apply_ocr_memory(text or "")
        self.ocr_text.setPlainText(learned.text)
        self._set_ocr_feedback_enabled(bool(text))
        customer = self.customer_text.toPlainText().strip()
        if self._autofinalize_after_preview:
            self._start_final_generation()
            return
        if customer or learned.text:
            self._run_backend_analysis(customer, learned.text)
        else:
            self._set_status(f"OCR завершён • {self._format_duration(elapsed_ms)}")
            self._set_busy(False)
            self._start_final_generation()

    def _ocr_failed(self, message: str, elapsed_ms: float) -> None:
        self._set_stage_metric("ocr_ms", elapsed_ms)
        self._set_expert_debug(message)
        if self._autofinalize_after_preview:
            self._set_status("Не удалось распознать скриншот. Пытаюсь подготовить ответ по доступному контексту.")
            self._start_final_generation()
            return
        self._worker_failed(message)

    def _backend_analysis_finished(self, payload: dict, elapsed_ms: float) -> None:
        self._set_stage_metric("analyze_ms", elapsed_ms)
        self._show_analysis_payload(payload, "FastAPI")
        if self._autofinalize_after_preview:
            self._run_hidden_preview()
            return
        self._set_busy(False)
        self._set_status(f"Аналитика обновлена • {self._format_duration(elapsed_ms)}")

    def _backend_analysis_failed(
        self,
        message: str,
        elapsed_ms: float,
        customer_text: str,
        ocr_text: str,
        style_profile: dict | None,
    ) -> None:
        self._set_stage_metric("analyze_ms", elapsed_ms)
        style = self.style_manager.get_style(self.settings.values.selected_style_id)
        analysis = self.case_analyzer.analyze(
            customer_text,
            ocr_text,
            style_profile=style_profile,
            reply_style_label=style.name if style else None,
        )
        self._show_case_analysis(analysis, "Локально")
        self._set_expert_debug(message)
        if self._autofinalize_after_preview:
            self._set_status("FastAPI недоступен. Продолжаю по локальному анализу.")
            self._start_final_generation()
            return
        self._set_busy(False)
        self._set_status("FastAPI недоступен. Показан локальный анализ.")

    def _preview_finished(self, payload: dict, elapsed_ms: float) -> None:
        self._set_stage_metric("preview_ms", elapsed_ms)
        self.last_preview_payload = payload
        self._show_analysis_payload(payload, "FastAPI")
        if self._autofinalize_after_preview:
            self._start_final_generation(payload)
            return
        self._set_busy(False)
        self._set_status(f"Контекст ответа обновлён • {self._format_duration(elapsed_ms)}")

    def _preview_failed(self, message: str, elapsed_ms: float) -> None:
        self._set_stage_metric("preview_ms", elapsed_ms)
        self._set_expert_debug(message)
        if self._autofinalize_after_preview:
            self._set_status("Не удалось усилить ответ локальными знаниями. Готовлю ответ по основному контексту.")
            self._start_final_generation()
            return
        self._worker_failed(message)

    def _generation_finished(
        self,
        text: str,
        model: str,
        style_id: int | None,
        style_profile: dict | None,
        elapsed_ms: float,
        source_label: str = "локально",
        analysis_payload: dict | None = None,
        analysis_source: str | None = None,
    ) -> None:
        try:
            self._set_stage_metric("generate_ms", elapsed_ms)
            self.response_text.setPlainText(text)
            self.last_generated_raw_response = text
            self.last_generated_model = model
            self.last_generated_style_id = style_id
            self._refresh_response_actions()

            if analysis_payload:
                analysis = self._analysis_from_payload(analysis_payload)
            else:
                selected_style = self.style_manager.get_style(style_id) if style_id else None
                analysis = self.case_analyzer.analyze(
                    self.customer_text.toPlainText(),
                    self.ocr_text.toPlainText(),
                    style_profile=style_profile,
                    reply_style_label=selected_style.name if selected_style else None,
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
            if analysis_payload:
                self._show_analysis_payload(analysis_payload, analysis_source or source_label)
            else:
                self._show_case_analysis(analysis, "Локально")
            self._set_status(f"Ответ подготовлен {source_label} • {self._format_duration(elapsed_ms)}")
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка после генерации", str(exc))
            self._set_status("Ответ получен, но не удалось сохранить аналитику.")
            self._set_expert_debug(str(exc))
        finally:
            self._autofinalize_after_preview = False
            self._set_busy(False)

    def _backend_generation_finished(
        self,
        payload: dict,
        fallback_model: str,
        style_id: int | None,
        style_profile: dict | None,
        elapsed_ms: float,
    ) -> None:
        response_text = str(payload.get("response_text", "")).strip()
        if not response_text:
            self._worker_failed("FastAPI вернул пустой итоговый ответ.")
            return
        model = str(payload.get("model", "")).strip() or fallback_model
        self.last_preview_payload = {**(self.last_preview_payload or {}), **payload}
        self._show_knowledge_payload(payload)
        self._generation_finished(
            response_text,
            model,
            style_id,
            style_profile,
            elapsed_ms,
            source_label="через FastAPI",
            analysis_payload=payload,
            analysis_source="FastAPI",
        )

    def _backend_generation_failed(
        self,
        message: str,
        elapsed_ms: float,
        customer_text: str,
        ocr_text: str,
        model: str,
        style_id: int | None,
        style_profile: dict | None,
        image_base64: str | None,
    ) -> None:
        self._set_stage_metric("generate_ms", elapsed_ms)
        self._set_expert_debug(message)
        self._set_status("FastAPI недоступен для генерации. Перехожу на локальную генерацию.")
        self._set_busy(False)
        self._start_local_generation_fallback(
            customer_text,
            ocr_text,
            model,
            style_id,
            style_profile,
            image_base64,
        )

    def _worker_failed(self, message: str) -> None:
        self._autofinalize_after_preview = False
        self._set_busy(False)
        self._set_expert_debug(message)
        friendly = "Не удалось подготовить ответ. Проверьте локальную модель или backend."
        QMessageBox.warning(self, "Ошибка", friendly)
        self._set_status(friendly)

    def _set_busy(self, busy: bool, message: str | None = None) -> None:
        self._busy = busy
        self.primary_action_button.setEnabled(not busy and self._has_context())
        self.clear_button.setEnabled(not busy)
        self.screenshot_button.setEnabled(not busy and self.settings.values.processing_mode != "text_only")
        self.remove_screenshot_button.setEnabled(not busy and bool(self.current_image_path))
        self.theme_button.setEnabled(not busy)
        self.expert_toggle.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy)
        self.model_combo.setEnabled(not busy)
        self.topic_override_toggle.setEnabled(not busy and self.last_case_analysis is not None)
        self.topic_override_combo.setEnabled(not busy and self.last_case_analysis is not None)
        self.topic_override_save_button.setEnabled(not busy and self.last_case_analysis is not None)
        if busy:
            self.primary_action_button.setText("Готовлю ответ…")
        else:
            self.primary_action_button.setText("Подготовить ответ  →")
            self.primary_action_button.setIcon(self._render_icon("magic", size=16, color="#FFFFFF"))
            self.primary_action_button.setIconSize(QSize(16, 16))
        self._refresh_response_actions()
        self._set_ocr_feedback_enabled(bool(self.last_ocr_raw_text))
        if message:
            self._set_status(message)

    def _set_ocr_feedback_enabled(self, enabled: bool) -> None:
        visible = enabled and self.settings.values.expert_mode
        self.ocr_feedback_correct_button.setVisible(visible)
        self.ocr_feedback_save_button.setVisible(visible)
        self.ocr_feedback_correct_button.setEnabled(visible and not self._busy)
        self.ocr_feedback_save_button.setEnabled(visible and not self._busy)

    def _refresh_response_actions(self) -> None:
        has_response = bool(self.response_text.toPlainText().strip())
        has_generated = bool(self.last_generated_raw_response)
        self.copy_button.setEnabled(has_response and not self._busy)
        self.save_to_style_button.setEnabled(has_response and not self._busy)
        self.feedback_positive_button.setEnabled(has_generated and not self._busy)
        self.feedback_negative_button.setEnabled(has_generated and not self._busy)
        self.response_feedback_save_button.setVisible(self._negative_feedback_requested and has_generated)
        self.response_feedback_save_button.setEnabled(self._negative_feedback_requested and has_generated and not self._busy)
        for button in [
            self.answer_copy_icon,
            self.answer_save_icon,
            self.answer_like_icon,
            self.answer_dislike_icon,
            self.answer_rerun_icon,
        ]:
            button.setEnabled((has_response or button is self.answer_rerun_icon) and not self._busy)

    def _toggle_negative_feedback(self) -> None:
        if not self.last_generated_raw_response:
            return
        self._negative_feedback_requested = not self._negative_feedback_requested
        self._refresh_response_actions()
        if self._negative_feedback_requested:
            self.response_text.setFocus()
            self._set_status("Исправьте текст ответа и сохраните исправленную версию.")

    def mark_ocr_correct(self) -> None:
        text = self.ocr_text.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Нет OCR-текста", "Сначала распознайте текст со скриншота.")
            return
        self._save_ocr_feedback("correct", text)
        self._set_status("OCR отмечен как корректный.")

    def save_corrected_ocr_text(self) -> None:
        corrected_text = self.ocr_text.toPlainText().strip()
        if not corrected_text:
            QMessageBox.information(self, "Нет текста", "Сначала исправьте OCR-текст.")
            return
        if not self.last_ocr_raw_text:
            QMessageBox.information(self, "Нет исходного OCR", "Сначала выполните OCR, затем сохраните исправленный текст.")
            return
        self._save_ocr_feedback("corrected", corrected_text)
        self._set_status("Исправленный OCR-текст сохранён.")

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
            QMessageBox.information(self, "Нет ответа", "Сначала подготовьте ответ.")
            return
        self._save_response_feedback("correct", text)
        learned = self._auto_learn_from_response(text, store_example=False)
        self._negative_feedback_requested = False
        self._refresh_response_actions()
        if learned:
            self._set_status(f"Ответ подтверждён и усилил стиль: {learned.name}")
        else:
            self._set_status("Ответ подтверждён.")

    def save_corrected_response(self) -> None:
        corrected_text = self.response_text.toPlainText().strip()
        if not corrected_text or not self.last_generated_raw_response:
            QMessageBox.information(self, "Нет исходного ответа", "Сначала подготовьте ответ, затем исправьте его при необходимости.")
            return
        self._save_response_feedback("corrected", corrected_text)
        learned = self._auto_learn_from_response(corrected_text, store_example=True)
        self._negative_feedback_requested = False
        self._refresh_response_actions()
        if learned:
            self._set_status(f"Исправленный ответ сохранён и усилил стиль: {learned.name}")
        else:
            self._set_status("Исправленный ответ сохранён.")

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
            reply_style_label=style.name,
        )
        updated = self.style_manager.learn_from_confirmed_interaction(
            style_id,
            self.customer_text.toPlainText(),
            final_response,
            analysis.topic,
            store_example=store_example,
        )
        self.settings.update(selected_style_id=updated.id)
        self._refresh_style_summary()
        return updated

    def _toggle_topic_override(self) -> None:
        if not self.last_case_analysis:
            return
        visible = not self.topic_override_container.isVisible()
        self.topic_override_container.setVisible(visible)
        if visible:
            self.topic_override_combo.setFocus()

    def save_topic_correction(self) -> None:
        if not self.last_case_analysis:
            QMessageBox.information(self, "Нет анализа", "Сначала выполните анализ обращения.")
            return
        corrected_topic = self.topic_override_combo.currentText().strip()
        if not corrected_topic:
            QMessageBox.information(self, "Нет темы", "Введите или выберите тему.")
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
        corrected = CaseAnalysis(
            topic=corrected_topic,
            signals=list(self.last_case_analysis.signals),
            extracted=dict(self.last_case_analysis.extracted),
            customer_tone=self.last_case_analysis.customer_tone,
            escalation_risk=self.last_case_analysis.escalation_risk,
            priority=self.last_case_analysis.priority,
            reply_style_label=self.last_case_analysis.reply_style_label,
        )
        self._show_case_analysis(corrected, "Подтверждено")
        self.topic_override_container.setVisible(False)
        self._set_status(f"Тема сохранена и усилила стиль: {corrected_topic}")

    def update_case_summary(self) -> None:
        text = self.customer_text.toPlainText().strip()
        ocr = self.ocr_text.toPlainText().strip()
        if not text and not ocr:
            self._show_empty_summary()
            self.last_case_analysis = None
            self.last_case_source = "Ожидание"
            self._refresh_primary_action_state()
            return
        style = self.style_manager.get_style(self.settings.values.selected_style_id)
        analysis = self.case_analyzer.analyze(
            text,
            ocr,
            style_profile=style.profile if style else None,
            reply_style_label=style.name if style else None,
        )
        self._show_case_analysis(analysis, "Локально")
        self._refresh_primary_action_state()

    def _show_empty_summary(self) -> None:
        self.summary_source_label.setText("Ожидание")
        self.summary_topic_value.setText("Тема не определена")
        self.summary_tone_value.setText("Нейтральный")
        self.summary_risk_value.setText("Низкий")
        self.summary_priority_value.setText("Обычный")
        self.summary_style_value.setText(self._current_style_name())
        self._apply_semantic_label(self.summary_topic_value, "neutral")
        self._apply_semantic_label(self.summary_tone_value, "neutral")
        self._apply_semantic_label(self.summary_risk_value, "positive")
        self._apply_semantic_label(self.summary_priority_value, "neutral")
        self._apply_semantic_label(self.summary_style_value, "accent")
        self.summary_signal_chips.set_items([])
        self.summary_details_label.setText("Появится после анализа обращения.")
        self.analytics_chips.set_items([])
        self.topic_override_toggle.setEnabled(False)
        self.topic_override_container.setVisible(False)
        self.topic_override_combo.setCurrentText("")
        self._refresh_style_summary()
        self._show_empty_knowledge()

    def _show_case_analysis(self, analysis: CaseAnalysis, source: str) -> None:
        self.last_case_analysis = analysis
        self.last_case_source = source
        self.summary_source_label.setText(source)
        self.summary_topic_value.setText(analysis.topic or "Тема не определена")
        self.summary_tone_value.setText(analysis.customer_tone)
        self.summary_risk_value.setText(analysis.escalation_risk)
        self.summary_priority_value.setText(analysis.priority)
        self.summary_style_value.setText(analysis.reply_style_label or self._current_style_name())
        self._apply_semantic_label(self.summary_topic_value, "positive")
        tone_state = "negative" if analysis.customer_tone in {"Негативный", "Резкий"} else "neutral"
        self._apply_semantic_label(self.summary_tone_value, tone_state)
        if analysis.escalation_risk == "Высокий":
            risk_state = "negative"
        elif analysis.escalation_risk == "Средний":
            risk_state = "warning"
        else:
            risk_state = "positive"
        self._apply_semantic_label(self.summary_risk_value, risk_state)
        if analysis.priority == "Высокий":
            priority_state = "negative"
        elif analysis.priority == "Повышенный":
            priority_state = "warning"
        else:
            priority_state = "neutral"
        self._apply_semantic_label(self.summary_priority_value, priority_state)
        self._apply_semantic_label(self.summary_style_value, "accent")
        self.summary_signal_chips.set_items(analysis.signals[:3])

        detail_parts: list[str] = []
        if analysis.extracted.get("amounts"):
            detail_parts.append("Суммы: " + ", ".join(analysis.extracted["amounts"][:3]))
        if analysis.extracted.get("dates"):
            detail_parts.append("Даты: " + ", ".join(analysis.extracted["dates"][:3]))
        if analysis.extracted.get("mcc_codes"):
            detail_parts.append("MCC: " + ", ".join(analysis.extracted["mcc_codes"][:4]))
        self.summary_details_label.setText(" • ".join(detail_parts) if detail_parts else "Явных признаков пока нет.")
        self.analytics_chips.set_items(
            [
                f"Тема: {analysis.topic}",
                f"Тон: {analysis.customer_tone}",
                f"Риск: {analysis.escalation_risk}",
                f"Приоритет: {analysis.priority}",
                f"Стиль: {analysis.reply_style_label or self._current_style_name()}",
            ]
        )
        self.topic_override_toggle.setEnabled(True)
        self._sync_topic_override_value(analysis.topic)

    def _analysis_from_payload(self, payload: dict) -> CaseAnalysis:
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
            customer_tone=str(payload.get("customer_tone", "Нейтральный")),
            escalation_risk=str(payload.get("escalation_risk", "Низкий")),
            priority=str(payload.get("priority", "Обычный")),
            reply_style_label=str(payload.get("reply_style_label", "")).strip() or self._current_style_name(),
        )

        return analysis

    def _show_analysis_payload(self, payload: dict, source: str) -> None:
        analysis = self._analysis_from_payload(payload)
        self._show_case_analysis(analysis, source)
        if "knowledge_matches" in payload or "knowledge_facts" in payload:
            self._show_knowledge_payload(payload)

    def _show_empty_knowledge(self) -> None:
        if not hasattr(self, "knowledge_status_label"):
            return
        self.knowledge_status_label.setText("Ожидание")
        self.knowledge_details_label.setText("Факты появятся после подготовки ответа.")

    def _show_knowledge_payload(self, payload: dict) -> None:
        if not hasattr(self, "knowledge_status_label"):
            return

        matches = payload.get("knowledge_matches", [])
        facts = payload.get("knowledge_facts", [])
        status = str(payload.get("knowledge_status", "")).strip()
        if not isinstance(matches, list):
            matches = []
        if not isinstance(facts, list):
            facts = []

        clean_facts = [str(item).strip() for item in facts if str(item).strip()][:2]
        clean_matches = [item for item in matches if isinstance(item, dict)]

        if clean_matches:
            first = clean_matches[0]
            title = str(first.get("title", "")).strip() or "Локальная статья"
            product = str(first.get("product", "")).strip() or "product"
            score = first.get("score", 0)
            matched_terms = first.get("matched_terms", [])
            if not isinstance(matched_terms, list):
                matched_terms = []
            terms = ", ".join(str(item) for item in matched_terms[:5])
            detail_parts = [
                title,
                f"Продукт: {product} · score: {score}",
            ]
            if clean_facts:
                detail_parts.append("Факты: " + " ".join(clean_facts))
            if terms:
                detail_parts.append("Совпадения: " + terms)
            self.knowledge_status_label.setText("Факты найдены")
            self.knowledge_details_label.setText("\n".join(detail_parts))
            return

        if clean_facts:
            self.knowledge_status_label.setText("Факты найдены")
            self.knowledge_details_label.setText("Факты: " + " ".join(clean_facts))
            return

        if status == "article_without_facts":
            self.knowledge_status_label.setText("Статья найдена")
            self.knowledge_details_label.setText("Есть совпадение по статье, но явные факты для ответа не выделены.")
            return

        self.knowledge_status_label.setText("Факты не найдены")
        self.knowledge_details_label.setText("Ответ будет осторожнее: без выдуманных условий, сроков и тарифов.")

    def _sync_topic_override_value(self, topic: str | None = None) -> None:
        if not self.last_case_analysis:
            self.topic_override_container.setVisible(False)
            return
        selected_topic = (topic or self.last_case_analysis.topic).strip()
        existing_index = self.topic_override_combo.findText(selected_topic)
        if existing_index < 0:
            self.topic_override_combo.addItem(selected_topic)
            existing_index = self.topic_override_combo.findText(selected_topic)
        self.topic_override_combo.setCurrentIndex(existing_index)

    def _refresh_primary_action_state(self) -> None:
        self.primary_action_button.setEnabled(not self._busy and self._has_context())
        self.primary_action_button.setToolTip(
            "Собрать тему, локальные факты и сразу подготовить итоговый ответ."
        )
        self.remove_screenshot_button.setEnabled(not self._busy and bool(self.current_image_path))

    def _has_context(self) -> bool:
        has_text = bool(self.customer_text.toPlainText().strip() or self.ocr_text.toPlainText().strip())
        has_image = bool(self.current_image_path or self.current_clipboard_image_base64) and self.settings.values.processing_mode != "text_only"
        return has_text or has_image

    def _current_style_name(self) -> str:
        style = self.style_manager.get_style(self.settings.values.selected_style_id)
        return style.name if style else "Не выбран"

    def _refresh_style_summary(self) -> None:
        style = self.style_manager.get_style(self.settings.values.selected_style_id)
        if not style:
            self.current_style_name.setText("Не выбран")
            self.current_style_tone.setText("Стиль ответа ещё не выбран.")
            self.current_style_pill.setText("Не выбран")
            for label in self.recent_styles_labels:
                label.setText("—")
            return
        self.current_style_name.setText(style.name)
        tone = str(style.profile.get("tone", "нейтральный"))
        paragraph_style = str(style.profile.get("paragraph_style", "короткие абзацы"))
        self.current_style_tone.setText(f"{tone.capitalize()} • {paragraph_style}")
        self.current_style_pill.setText(style.name)
        recent = [item.name for item in self.style_manager.list_styles()[:3]]
        for index, label in enumerate(self.recent_styles_labels):
            label.setText(recent[index] if index < len(recent) else "—")

    def _set_status(self, message: str) -> None:
        self.status_message.setText(message)

    def _set_expert_debug(self, message: str) -> None:
        clean = message.strip()
        self.expert_debug_label.setText(clean)
        self.expert_debug_label.setVisible(bool(clean) and self.settings.values.expert_mode)

    @staticmethod
    def _apply_semantic_label(label: QLabel, semantic: str) -> None:
        label.setProperty("semantic", semantic)
        label.style().unpolish(label)
        label.style().polish(label)

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
            apply_theme(
                app,
                self.settings.values.theme,
                self.settings.values.corner_radius,
                self.settings.values.button_style,
            )
        self._apply_theme_button_state()
        self._apply_window_settings()
        self._apply_expert_mode(self.settings.values.expert_mode, persist=False)
        self.apply_processing_mode()
        self.refresh_status()
        self._refresh_style_summary()
        self.update_case_summary()

    def _forget_worker(self, worker) -> None:
        if worker in self.workers:
            self.workers.remove(worker)
