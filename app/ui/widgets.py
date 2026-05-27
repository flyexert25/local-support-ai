from __future__ import annotations

from html import escape
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.utils.image_utils import SUPPORTED_IMAGE_EXTENSIONS


class StatusPill(QLabel):
    def __init__(self, text: str, ok: bool = True) -> None:
        super().__init__()
        self.setObjectName("StatusPill")
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setMinimumHeight(28)
        self.set_state(text, ok)

    def set_state(self, text: str, ok: bool) -> None:
        self.setProperty("ok", ok)
        dot_color = "#2F9E66" if ok else "#D9822B"
        self.setText(f'<span style="color:{dot_color};">●</span> {escape(text)}')
        self.style().unpolish(self)
        self.style().polish(self)


class DotStatusLabel(QLabel):
    def __init__(self, text: str, ok: bool = True) -> None:
        super().__init__()
        self.setObjectName("DotStatus")
        self.setTextFormat(Qt.TextFormat.RichText)
        self.set_state(text, ok)

    def set_state(self, text: str, ok: bool) -> None:
        dot_color = "#2F9E66" if ok else "#D9822B"
        self.setText(f'<span style="color:{dot_color};">●</span> {escape(text)}')


class ScreenshotDropZone(QFrame):
    imageDropped = pyqtSignal(Path)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self._pixmap_label = QLabel("Перетащите скриншот сюда\nили вставьте через Ctrl+V")
        self._pixmap_label.setObjectName("Hint")
        self._pixmap_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pixmap_label.setMinimumHeight(180)
        self._pixmap_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(self._pixmap_label)

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        if pixmap is None or pixmap.isNull():
            self._pixmap_label.setText("Перетащите скриншот сюда\nили вставьте через Ctrl+V")
            self._pixmap_label.setPixmap(QPixmap())
            return
        self._pixmap_label.setText("")
        self._pixmap_label.setPixmap(pixmap)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._event_has_image(event):
            self.setProperty("active", True)
            self.style().unpolish(self)
            self.style().polish(self)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._set_inactive()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_inactive()
        urls = event.mimeData().urls()
        if not urls:
            event.ignore()
            return
        path = Path(urls[0].toLocalFile())
        if path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
            self.imageDropped.emit(path)
            event.acceptProposedAction()
        else:
            event.ignore()

    @staticmethod
    def _event_has_image(event: QDragEnterEvent) -> bool:
        urls = event.mimeData().urls()
        if not urls:
            return False
        return Path(urls[0].toLocalFile()).suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS

    def _set_inactive(self) -> None:
        self.setProperty("active", False)
        self.style().unpolish(self)
        self.style().polish(self)


class AnalyticsChips(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(6)
        self.setVisible(False)

    def set_items(self, items: list[str]) -> None:
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for item in items:
            chip = QLabel(item)
            chip.setObjectName("InsightChip")
            chip.setMinimumHeight(24)
            chip.setProperty("semantic", self._chip_semantic(item))
            chip.style().unpolish(chip)
            chip.style().polish(chip)
            self.layout.addWidget(chip)
        self.layout.addStretch(1)
        self.setVisible(bool(items))

    @staticmethod
    def _chip_semantic(text: str) -> str:
        clean = text.strip().lower()
        if clean.startswith("тема:"):
            return "positive"
        if clean.startswith("тон:"):
            if "негатив" in clean or "резк" in clean:
                return "negative"
            return "positive"
        if clean.startswith("риск:"):
            if "высок" in clean:
                return "negative"
            if "средн" in clean:
                return "warning"
            return "positive"
        if clean.startswith("приоритет:"):
            if "высок" in clean:
                return "negative"
            if "повыш" in clean:
                return "warning"
            return "positive"
        if clean.startswith("стиль:"):
            return "accent"
        return "neutral"


class CaseInsightPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("InsightPanel")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        self.topic_label = QLabel("Тема не определена")
        self.topic_label.setObjectName("InsightTopic")
        self.source_label = QLabel("Локально")
        self.source_label.setObjectName("InsightSource")
        top_row.addWidget(self.topic_label, 1)
        top_row.addWidget(self.source_label)
        layout.addLayout(top_row)

        self.meta_container = QWidget()
        self.meta_layout = QVBoxLayout(self.meta_container)
        self.meta_layout.setContentsMargins(0, 0, 0, 0)
        self.meta_layout.setSpacing(6)
        layout.addWidget(self.meta_container)

        self.chips = AnalyticsChips()
        layout.addWidget(self.chips)

        self.details_label = QLabel("Подробности появятся после анализа обращения.")
        self.details_label.setObjectName("InsightDetails")
        self.details_label.setWordWrap(True)
        layout.addWidget(self.details_label)

        self.raw_context = QTextEdit()
        self.raw_context.setReadOnly(True)
        self.raw_context.setObjectName("ExpertContext")
        self.raw_context.setMaximumHeight(120)
        layout.addWidget(self.raw_context)
        self.set_placeholder()

    def set_placeholder(self, text: str = "Подробности появятся после анализа обращения.") -> None:
        self.topic_label.setText("Тема не определена")
        self.source_label.setText("Ожидание")
        self._set_meta_rows([])
        self.chips.set_items([])
        self.details_label.setText(text)
        self.raw_context.clear()

    def set_analysis(
        self,
        topic: str,
        signals: list[str],
        extracted: dict[str, list[str]],
        source: str = "Локально",
        customer_tone: str | None = None,
        escalation_risk: str | None = None,
        priority: str | None = None,
        reply_style_label: str | None = None,
    ) -> None:
        self.topic_label.setText(topic or "Тема не определена")
        self.source_label.setText(source or "Локально")

        rows = [
            ("Тон клиента", customer_tone or "Нейтральный"),
            ("Риск эскалации", escalation_risk or "Низкий"),
            ("Приоритет", priority or "Обычный"),
            ("Стиль ответа", reply_style_label or "Не выбран"),
        ]
        self._set_meta_rows(rows)
        self.chips.set_items(signals[:4])

        detail_parts: list[str] = []
        if extracted.get("amounts"):
            detail_parts.append("Суммы: " + ", ".join(extracted["amounts"][:3]))
        if extracted.get("dates"):
            detail_parts.append("Даты: " + ", ".join(extracted["dates"][:3]))
        if extracted.get("mcc_codes"):
            detail_parts.append("MCC: " + ", ".join(extracted["mcc_codes"][:4]))

        if detail_parts:
            self.details_label.setText(" • ".join(detail_parts))
            self.raw_context.setPlainText("\n".join(detail_parts))
        elif signals:
            self.details_label.setText("Выделены ключевые признаки обращения.")
            self.raw_context.setPlainText("\n".join(signals))
        else:
            self.details_label.setText("Явных признаков пока нет.")
            self.raw_context.clear()

    def _set_meta_rows(self, rows: list[tuple[str, str]]) -> None:
        while self.meta_layout.count():
            item = self.meta_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for title, value in rows:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(10)
            left = QLabel(title)
            left.setObjectName("InsightMetaLabel")
            right = QLabel(value)
            right.setObjectName("InsightMetaValue")
            right.setWordWrap(True)
            right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row_layout.addWidget(left, 1)
            row_layout.addWidget(right, 1)
            self.meta_layout.addWidget(row)


class ToggleSwitch(QAbstractButton):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(46, 26)
        self._offset = 1.0 if self.isChecked() else 0.0
        self._animation = QPropertyAnimation(self, b"offset", self)
        self._animation.setDuration(160)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._start_animation)

    def sizeHint(self) -> QSize:
        return QSize(46, 26)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        is_light_theme = self.palette().window().color().lightness() > 180

        if not self.isEnabled():
            if is_light_theme:
                track_color = QColor("#E5E7EB")
                knob_color = QColor("#9CA3AF")
                border_color = QColor("#CBD5E1")
            else:
                track_color = QColor("#2A3038") if self.isChecked() else QColor("#242932")
                knob_color = QColor("#A7B0BC")
                border_color = QColor("#38404D")
        else:
            if is_light_theme:
                track_color = QColor("#6366F1") if self.isChecked() else QColor("#E5E7EB")
                knob_color = QColor("#FFFFFF") if self.isChecked() else QColor("#6B7280")
                border_color = QColor("#6366F1") if self.isChecked() else QColor("#C7CFDC")
            else:
                track_color = QColor("#6366F1") if self.isChecked() else QColor("#303745")
                knob_color = QColor("#F7FAFC")
                border_color = QColor("#7A7EF3") if self.isChecked() else QColor("#414A59")

        painter.setPen(border_color)
        painter.setBrush(track_color)
        painter.drawRoundedRect(1, 1, 44, 24, 12, 12)

        x = int(3 + self._offset * 20)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(knob_color)
        painter.drawEllipse(x, 3, 20, 20)

    def _start_animation(self, checked: bool) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._offset)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def get_offset(self) -> float:
        return self._offset

    def set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor)
        self.update()

    offset = pyqtProperty(float, fget=get_offset, fset=set_offset)
