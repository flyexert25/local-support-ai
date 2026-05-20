from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication


BASE_STYLE_SHEET = """
* {
    font-family: 'Segoe UI', 'Inter', Arial;
    font-size: 13px;
}
"""

DARK_STYLE_SHEET = BASE_STYLE_SHEET + """
QMainWindow, QDialog {
    background: #111318;
    color: #E8EAED;
}
QWidget#TopBar {
    background: #171A21;
    border-bottom: 1px solid #252A35;
}
QLabel#Title {
    font-size: 18px;
    font-weight: 700;
}
QLabel#Subtle, QLabel#Hint {
    color: #9AA4B2;
}
QLabel#StatusPill {
    background: #17251D;
    border: 1px solid #294A35;
    border-radius: 9px;
    color: #D9F7E6;
    font-weight: 600;
    padding: 5px 10px;
}
QLabel#StatusPill[ok="false"] {
    background: #2B2116;
    border: 1px solid #5C4020;
    color: #FFE2B8;
}
QFrame#Panel {
    background: #181C24;
    border: 1px solid #2A303C;
    border-radius: 8px;
}
QFrame#DropZone {
    background: #151922;
    border: 1px dashed #3D4656;
    border-radius: 8px;
}
QFrame#DropZone[active="true"] {
    border-color: #61D394;
    background: #18221D;
}
QPushButton {
    background: #242B36;
    color: #F4F7FA;
    border: 1px solid #333B49;
    border-radius: 6px;
    padding: 8px 12px;
}
QPushButton:hover {
    background: #2E3745;
}
QPushButton:pressed {
    background: #202733;
}
QPushButton#Primary {
    background: #2F7CF6;
    border-color: #2F7CF6;
}
QPushButton#Primary:hover {
    background: #438BFF;
}
QPushButton#Danger {
    background: #392129;
    border-color: #61313F;
}
QPushButton#Ghost {
    background: #1B2230;
    color: #D9E2F2;
    border: 1px solid #344055;
    padding: 6px 10px;
}
QPushButton#Ghost:hover {
    background: #232C3B;
}
QToolButton {
    background: #242B36;
    color: #F4F7FA;
    border: 1px solid #333B49;
    border-radius: 6px;
    padding: 7px;
}
QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #10131A;
    color: #F4F7FA;
    border: 1px solid #303745;
    border-radius: 6px;
    padding: 7px;
    selection-background-color: #2F7CF6;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QCheckBox {
    color: #E8EAED;
    spacing: 8px;
}
QTabWidget::pane {
    border: 1px solid #2A303C;
    border-radius: 8px;
}
QTabBar::tab {
    background: #181C24;
    color: #AEB7C4;
    padding: 9px 14px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:selected {
    background: #242B36;
    color: #FFFFFF;
}
QProgressBar {
    border: 1px solid #303745;
    border-radius: 5px;
    background: #10131A;
    text-align: center;
}
QProgressBar::chunk {
    background: #61D394;
    border-radius: 5px;
}
"""

LIGHT_STYLE_SHEET = BASE_STYLE_SHEET + """
QMainWindow, QDialog {
    background: #F4F6FA;
    color: #172033;
}
QWidget#TopBar {
    background: #FFFFFF;
    border-bottom: 1px solid #DCE3EE;
}
QLabel#Title {
    font-size: 18px;
    font-weight: 700;
    color: #172033;
}
QLabel#Subtle, QLabel#Hint {
    color: #687386;
}
QLabel#StatusPill {
    background: #F1F8F4;
    border: 1px solid #CFE8D8;
    border-radius: 9px;
    color: #234235;
    font-weight: 600;
    padding: 5px 10px;
}
QLabel#StatusPill[ok="false"] {
    background: #FFF7EC;
    border: 1px solid #F3D9B5;
    color: #62410E;
}
QFrame#Panel {
    background: #FFFFFF;
    border: 1px solid #DCE3EE;
    border-radius: 8px;
}
QFrame#DropZone {
    background: #F8FAFD;
    border: 1px dashed #B8C4D6;
    border-radius: 8px;
}
QFrame#DropZone[active="true"] {
    border-color: #2F9E66;
    background: #EFFAF4;
}
QPushButton {
    background: #EEF2F7;
    color: #172033;
    border: 1px solid #D2DAE8;
    border-radius: 6px;
    padding: 8px 12px;
}
QPushButton:hover {
    background: #E4EAF3;
}
QPushButton:pressed {
    background: #D9E1ED;
}
QPushButton#Primary {
    background: #2F7CF6;
    color: #FFFFFF;
    border-color: #2F7CF6;
}
QPushButton#Primary:hover {
    background: #438BFF;
}
QPushButton#Danger {
    background: #FFF0F2;
    color: #9D2336;
    border-color: #F1C2CA;
}
QPushButton#Ghost {
    background: #F7F9FC;
    color: #2B3A52;
    border: 1px solid #D8E0ED;
    padding: 6px 10px;
}
QPushButton#Ghost:hover {
    background: #EDF2F8;
}
QToolButton {
    background: #EEF2F7;
    color: #172033;
    border: 1px solid #D2DAE8;
    border-radius: 6px;
    padding: 7px;
}
QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #FFFFFF;
    color: #172033;
    border: 1px solid #CED8E6;
    border-radius: 6px;
    padding: 7px;
    selection-background-color: #2F7CF6;
    selection-color: #FFFFFF;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QCheckBox {
    color: #172033;
    spacing: 8px;
}
QTabWidget::pane {
    border: 1px solid #DCE3EE;
    border-radius: 8px;
    background: #FFFFFF;
}
QTabBar::tab {
    background: #EEF2F7;
    color: #687386;
    padding: 9px 14px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:selected {
    background: #FFFFFF;
    color: #172033;
}
QProgressBar {
    border: 1px solid #CED8E6;
    border-radius: 5px;
    background: #FFFFFF;
    text-align: center;
}
QProgressBar::chunk {
    background: #2F9E66;
    border-radius: 5px;
}
"""


def apply_theme(app: QApplication, theme: str = "dark") -> None:
    if theme == "light":
        _apply_light_theme(app)
    else:
        _apply_dark_theme(app)


def apply_dark_theme(app: QApplication) -> None:
    apply_theme(app, "dark")


def _apply_dark_theme(app: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#111318"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#E8EAED"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#10131A"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#181C24"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#242B36"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#F4F7FA"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#F4F7FA"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#242B36"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#F4F7FA"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2F7CF6"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)
    app.setStyleSheet(DARK_STYLE_SHEET)


def _apply_light_theme(app: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#F4F6FA"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#172033"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#EEF2F7"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#172033"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#172033"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#EEF2F7"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#172033"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2F7CF6"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)
    app.setStyleSheet(LIGHT_STYLE_SHEET)
