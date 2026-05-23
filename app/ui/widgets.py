from __future__ import annotations

from html import escape
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent, QPainter, QPixmap
from PyQt6.QtWidgets import QAbstractButton, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.utils.image_utils import SUPPORTED_IMAGE_EXTENSIONS


class StatusPill(QLabel):
    def __init__(self, text: str, color: str = "#9AA4B2") -> None:
        super().__init__(text)
        self.setObjectName("StatusPill")
        self.setTextFormat(Qt.TextFormat.RichText)
        self._ok = True
        self.setMinimumHeight(26)
        self.set_state(text, True)

    def set_color(self, color: str) -> None:
        self.set_state(self.text().replace("● ", ""), color.lower() not in {"#f2a65a", "#d9822b", "#a86b14"})

    def set_state(self, text: str, ok: bool) -> None:
        self._ok = ok
        self.setProperty("ok", ok)
        dot_color = "#2F9E66" if ok else "#D9822B"
        self.setText(f'<span style="color:{dot_color};">●</span> {escape(text)}')
        self._apply_style()

    def _apply_style(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)


class ScreenshotDropZone(QFrame):
    imageDropped = pyqtSignal(Path)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self._pixmap_label = QLabel("Перетащите скриншот сюда\nили вставьте через Ctrl+V")
        self._pixmap_label.setObjectName("Hint")
        self._pixmap_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pixmap_label.setMinimumHeight(260)
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


class CaseInsightPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("InsightPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        self.topic_label = QLabel("Предмет не определён")
        self.topic_label.setObjectName("InsightTopic")
        self.source_label = QLabel("Локально")
        self.source_label.setObjectName("InsightSource")
        top_row.addWidget(self.topic_label, 1)
        top_row.addWidget(self.source_label)
        layout.addLayout(top_row)

        self.signals_widget = QWidget()
        self.signals_layout = QHBoxLayout(self.signals_widget)
        self.signals_layout.setContentsMargins(0, 0, 0, 0)
        self.signals_layout.setSpacing(6)
        layout.addWidget(self.signals_widget)

        self.details_label = QLabel("Признаки появятся после ввода текста или OCR.")
        self.details_label.setObjectName("InsightDetails")
        self.details_label.setWordWrap(True)
        layout.addWidget(self.details_label)
        self.set_placeholder()

    def set_placeholder(self, text: str = "Признаки появятся после ввода текста или OCR.") -> None:
        self.topic_label.setText("Предмет не определён")
        self.source_label.setText("Ожидание")
        self._set_chips([])
        self.details_label.setText(text)

    def set_analysis(
        self,
        topic: str,
        signals: list[str],
        extracted: dict[str, list[str]],
        source: str = "Локально",
    ) -> None:
        self.topic_label.setText(topic or "Предмет не определён")
        self.source_label.setText(source)
        self._set_chips(signals[:4])

        details: list[str] = []
        if extracted.get("amounts"):
            details.append("Суммы: " + ", ".join(extracted["amounts"][:3]))
        if extracted.get("dates"):
            details.append("Даты: " + ", ".join(extracted["dates"][:3]))
        if extracted.get("mcc_codes"):
            details.append("MCC: " + ", ".join(extracted["mcc_codes"][:4]))
        self.details_label.setText(" · ".join(details) if details else "Явных деталей пока нет.")

    def _set_chips(self, values: list[str]) -> None:
        while self.signals_layout.count():
            item = self.signals_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if not values:
            values = ["явных признаков пока нет"]
        for value in values:
            chip = QLabel(value)
            chip.setObjectName("InsightChip")
            self.signals_layout.addWidget(chip)
        self.signals_layout.addStretch(1)


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

        if not self.isEnabled():
            track_color = QColor("#2A3038") if self.isChecked() else QColor("#242932")
            knob_color = QColor("#A7B0BC")
            border_color = QColor("#38404D")
        else:
            track_color = QColor("#48A9E6") if self.isChecked() else QColor("#303745")
            knob_color = QColor("#F7FAFC")
            border_color = QColor("#62B7EB") if self.isChecked() else QColor("#414A59")

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
