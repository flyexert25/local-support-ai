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
    background: #0B1020;
    color: #F3F4F6;
}
QWidget#TopBar {
    background: #0B1020;
    border-bottom: 1px solid rgba(255,255,255,0.08);
}
QScrollArea#ExpertSidebarScroll {
    background: transparent;
    border: none;
}
QScrollArea#ExpertSidebarScroll > QWidget > QWidget {
    background: transparent;
}
QLabel#Title {
    font-size: 17px;
    font-weight: 700;
}
QLabel#Subtle, QLabel#Hint {
    color: #9CA3AF;
}
QLabel#RecentStylePrimary {
    color: #818CF8;
}
QLabel#DotStatus {
    color: #B9C3D5;
    font-weight: 600;
}
QLabel#StatusPill {
    background: rgba(99,102,241,0.10);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 10px;
    color: #D1D5DB;
    font-weight: 600;
    padding: 5px 10px;
}
QLabel#StatusPill[ok="false"] {
    background: rgba(156,163,175,0.10);
    border: 1px solid rgba(255,255,255,0.12);
    color: #9CA3AF;
}
QFrame#Panel {
    background: #111827;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
}
QFrame#Panel[flat_section="true"] {
    background: transparent;
    border: none;
    border-radius: 0px;
}
QFrame#SectionDivider {
    background: rgba(255,255,255,0.08);
}
QFrame#ProfileDivider {
    background: rgba(255,255,255,0.10);
}
QFrame#SettingsDivider {
    background: rgba(255,255,255,0.10);
}
QLabel#ChartPreview {
    border: none;
    background: transparent;
    padding: 2px;
}
QFrame#Rail {
    background: #151A22;
    border: 1px solid #2A3342;
    border-radius: 18px;
}
QLabel#PanelTitle {
    color: #F2F5FA;
    font-weight: 700;
}
QFrame#InsightPanel {
    background: #151A22;
    border: 1px solid #273142;
    border-radius: 14px;
}
QLabel#InsightTopic {
    color: #F4F7FA;
    font-weight: 700;
}
QLabel#InsightSource {
    color: #9AA4B2;
    background: #101722;
    border: 1px solid #293447;
    border-radius: 8px;
    padding: 3px 8px;
}
QLabel#InsightChip {
    color: #D1D5DB;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 10px;
    padding: 3px 9px;
}
QLabel#InsightChip[semantic="positive"] {
    color: #8EF0B8;
    background: #162A22;
    border: 1px solid #2D5B45;
}
QLabel#InsightChip[semantic="negative"] {
    color: #FF9AA2;
    background: #2A181C;
    border: 1px solid #5C3038;
}
QLabel#InsightChip[semantic="warning"] {
    color: #FFD08A;
    background: #2A2115;
    border: 1px solid #5D4727;
}
QLabel#InsightChip[semantic="accent"] {
    color: #A5B4FC;
    background: rgba(99,102,241,0.12);
    border: 1px solid rgba(99,102,241,0.30);
}
QLabel#InsightDetails {
    color: #9AA4B2;
}
QLabel#InsightMetaLabel {
    color: #8F9CB0;
}
QLabel#InsightMetaValue {
    color: #F2F5FA;
    font-weight: 600;
}
QLabel#InsightMetaValue[semantic="positive"] {
    color: #38D47A;
}
QLabel#InsightMetaValue[semantic="negative"] {
    color: #FF707A;
}
QLabel#InsightMetaValue[semantic="warning"] {
    color: #F2B84A;
}
QLabel#InsightMetaValue[semantic="accent"] {
    color: #B6AEFF;
}
QLabel#StatusDot {
    color: #6B7280;
    font-size: 16px;
    font-weight: 700;
}
QLabel#StatusDot[state="ok"] {
    color: #34D399;
}
QLabel#StatusDot[state="warning"] {
    color: #FBBF24;
}
QLabel#StatusDot[state="error"] {
    color: #F87171;
}
QLabel#StatusRowTitle {
    color: #F3F4F6;
    font-weight: 700;
}
QWidget#StatusRow {
    padding: 2px 0px;
}
QTextEdit#ExpertContext {
    background: #10151D;
    border: 1px solid #283344;
    border-radius: 12px;
    color: #DCE5F2;
    padding: 8px;
}
QFrame#DropZone {
    background: #151922;
    border: 1px dashed #3D4656;
    border-radius: 14px;
}
QFrame#DropZone[active="true"] {
    border-color: #61D394;
    background: #18221D;
}
QPushButton {
    background: #242B36;
    color: #F4F7FA;
    border: 1px solid #333B49;
    border-radius: 10px;
    padding: 9px 14px;
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
QPushButton#Secondary {
    background: #1D2634;
    color: #EAF1FF;
    border-color: #35445C;
}
QPushButton#Secondary:hover {
    background: #253149;
    border-color: #466087;
}
QPushButton#Danger {
    background: #392129;
    border-color: #61313F;
}
QPushButton#Ghost {
    background: rgba(255,255,255,0.02);
    color: #D1D5DB;
    border: 1px solid rgba(255,255,255,0.10);
    padding: 7px 11px;
}
QPushButton#Ghost:hover {
    background: rgba(255,255,255,0.06);
}
QPushButton#Tiny {
    background: rgba(255,255,255,0.02);
    color: #9CA3AF;
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 10px;
    padding: 6px 10px;
}
QPushButton#Tiny:hover {
    background: #202938;
}
QPushButton#HeroButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5F63E8, stop:1 #565BD9);
    color: #FFFFFF;
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 14px;
    font-weight: 700;
    padding: 12px 22px;
}
QPushButton#HeroButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #666AEC, stop:1 #5C61DD);
}
QPushButton#HeroButton:pressed {
    background: #5056CF;
}
QPushButton#RailButton {
    background: transparent;
    border: none;
    border-radius: 12px;
    padding: 10px;
}
QPushButton#RailButton:hover {
    background: #1E2531;
}
QPushButton#RailButton:checked {
    background: rgba(107, 92, 247, 0.18);
    border: 1px solid rgba(124, 135, 255, 0.45);
}
QPushButton#IconButton {
    background: transparent;
    border: none;
    border-radius: 10px;
    padding: 6px;
    min-width: 28px;
}
QPushButton#IconButton[variant="action"] {
    border-radius: 8px;
    padding: 4px;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
}
QPushButton#IconButton:hover {
    background: #1E2531;
}
QToolButton {
    background: #242B36;
    color: #F4F7FA;
    border: 1px solid #333B49;
    border-radius: 6px;
    padding: 7px;
}
QToolButton#SectionToggle {
    background: #1B2230;
    color: #E7EDF8;
    border: 1px solid #354156;
    border-radius: 7px;
    font-weight: 600;
    padding: 8px 12px;
    text-align: left;
}
QToolButton#SectionToggle:hover {
    background: #222B3A;
    border-color: #46556F;
}
QToolButton#SectionToggle:checked {
    background: #202A39;
    border-color: #5474A3;
}
QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #10131A;
    color: #F4F7FA;
    border: 1px solid #303745;
    border-radius: 12px;
    padding: 9px;
    selection-background-color: #2F7CF6;
}
QFrame#InputBox {
    background: #10131A;
    border: 1px solid #303745;
    border-radius: 14px;
}
QPlainTextEdit#CustomerEditor {
    background: transparent;
    border: none;
    border-radius: 12px;
    padding: 10px;
}
QFrame#ResponseBox {
    background: #10131A;
    border: 1px solid #303745;
    border-radius: 14px;
}
QPlainTextEdit#ResponseEditor {
    background: transparent;
    border: none;
    border-radius: 12px;
    padding: 10px;
}
QPlainTextEdit#OcrPreviewEditor {
    font-size: 12px;
    color: #D1D5DB;
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
QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #334155;
    border-radius: 6px;
    min-height: 36px;
}
QScrollBar::handle:vertical:hover {
    background: #475569;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
"""

LIGHT_STYLE_SHEET = BASE_STYLE_SHEET + """
QMainWindow, QDialog {
    background: #F5F7FB;
    color: #111827;
}
QWidget#AppShell {
    background: #F5F7FB;
}
QWidget#TopBar {
    background: #FFFFFF;
    border-bottom: 1px solid #E5E7EB;
}
QScrollArea#ExpertSidebarScroll {
    background: transparent;
    border: none;
}
QScrollArea#ExpertSidebarScroll > QWidget > QWidget {
    background: transparent;
}
QLabel#Title {
    font-size: 17px;
    font-weight: 700;
    color: #172033;
}
QLabel#Subtle, QLabel#Hint {
    color: #6B7280;
}
QLabel#RecentStylePrimary {
    color: #6366F1;
}
QLabel#DotStatus {
    color: #44536A;
    font-weight: 600;
}
QLabel#LogoMark {
    color: #172033;
    font-size: 20px;
    font-weight: 700;
}
QLabel#StatusPill {
    background: #F8FAFC;
    border: 1px solid #E5E7EB;
    border-radius: 10px;
    color: #6B7280;
    font-weight: 600;
    padding: 5px 10px;
}
QLabel#StatusPill[ok="false"] {
    background: #F8FAFC;
    border: 1px solid #E5E7EB;
    color: #6B7280;
}
QFrame#Panel {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 16px;
}
QFrame#Panel[flat_section="true"] {
    background: transparent;
    border: none;
    border-radius: 0px;
}
QFrame#SectionDivider {
    background: #E5E7EB;
}
QFrame#ProfileDivider {
    background: #E5E7EB;
}
QFrame#SettingsDivider {
    background: #E5E7EB;
}
QLabel#ChartPreview {
    border: none;
    background: transparent;
    padding: 2px;
}
QFrame#Rail {
    background: #F7F8FC;
    border: 1px solid #E3E7F0;
    border-radius: 18px;
}
QLabel#PanelTitle {
    color: #172033;
    font-weight: 700;
}
QFrame#InsightPanel {
    background: #F8FAFD;
    border: 1px solid #D9E2EF;
    border-radius: 14px;
}
QLabel#InsightTopic {
    color: #172033;
    font-weight: 700;
}
QLabel#InsightSource {
    color: #627089;
    background: #FFFFFF;
    border: 1px solid #DCE4F0;
    border-radius: 8px;
    padding: 3px 8px;
}
QLabel#InsightChip {
    color: #4B5563;
    background: #F8FAFC;
    border: 1px solid #E5E7EB;
    border-radius: 10px;
    padding: 3px 9px;
}
QLabel#InsightChip[semantic="positive"] {
    color: #0F8A4B;
    background: #EAF8F0;
    border: 1px solid #BFE7CD;
}
QLabel#InsightChip[semantic="negative"] {
    color: #B62D3C;
    background: #FFF0F3;
    border: 1px solid #F2C7CF;
}
QLabel#InsightChip[semantic="warning"] {
    color: #A9670D;
    background: #FFF7E9;
    border: 1px solid #F2DEB8;
}
QLabel#InsightChip[semantic="accent"] {
    color: #6366F1;
    background: #EEF2FF;
    border: 1px solid #DDE3FF;
}
QLabel#InsightDetails {
    color: #687386;
}
QLabel#InsightMetaLabel {
    color: #6E7D93;
}
QLabel#InsightMetaValue {
    color: #172033;
    font-weight: 600;
}
QLabel#InsightMetaValue[semantic="positive"] {
    color: #169B59;
}
QLabel#InsightMetaValue[semantic="negative"] {
    color: #CC3344;
}
QLabel#InsightMetaValue[semantic="warning"] {
    color: #C27A12;
}
QLabel#InsightMetaValue[semantic="accent"] {
    color: #5A4CF2;
}
QLabel#StatusDot {
    color: #94A3B8;
    font-size: 16px;
    font-weight: 700;
}
QLabel#StatusDot[state="ok"] {
    color: #16A34A;
}
QLabel#StatusDot[state="warning"] {
    color: #D97706;
}
QLabel#StatusDot[state="error"] {
    color: #DC2626;
}
QLabel#StatusRowTitle {
    color: #111827;
    font-weight: 700;
}
QWidget#StatusRow {
    padding: 2px 0px;
}
QTextEdit#ExpertContext {
    background: #FFFFFF;
    border: 1px solid #DCE6F3;
    border-radius: 12px;
    color: #33445D;
    padding: 8px;
}
QFrame#DropZone {
    background: #F8FAFD;
    border: 1px dashed #B8C4D6;
    border-radius: 14px;
}
QFrame#DropZone[active="true"] {
    border-color: #2F9E66;
    background: #EFFAF4;
}
QPushButton {
    background: #EEF2F7;
    color: #172033;
    border: 1px solid #D2DAE8;
    border-radius: 10px;
    padding: 9px 14px;
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
QPushButton#Secondary {
    background: #FFFFFF;
    color: #23405F;
    border-color: #C8D6EA;
}
QPushButton#Secondary:hover {
    background: #EFF5FC;
    border-color: #AFC5E4;
}
QPushButton#Danger {
    background: #FFF0F2;
    color: #9D2336;
    border-color: #F1C2CA;
}
QPushButton#Ghost {
    background: #F8FAFC;
    color: #4B5563;
    border: 1px solid #E5E7EB;
    padding: 7px 12px;
}
QPushButton#Ghost:hover {
    background: #F3F4F6;
}
QPushButton#Tiny {
    background: #F8FAFC;
    color: #6B7280;
    border: 1px solid #E5E7EB;
    border-radius: 10px;
    padding: 6px 10px;
}
QPushButton#Tiny:hover {
    background: #F3F4F6;
}
QPushButton#HeroButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366F1, stop:1 #5A5EE1);
    color: #FFFFFF;
    border: 1px solid #C9CCFF;
    border-radius: 14px;
    font-weight: 700;
    padding: 12px 22px;
}
QPushButton#HeroButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6A6DEE, stop:1 #6064E4);
}
QPushButton#HeroButton:pressed {
    background: #5459D8;
}
QPushButton#RailButton {
    background: transparent;
    color: #8A94A6;
    border: none;
    border-radius: 12px;
    padding: 10px;
}
QPushButton#RailButton:hover {
    background: #EFF2F7;
    color: #44536A;
}
QPushButton#RailButton:checked {
    background: #F1EEFF;
    color: #5A4CF2;
    border: 1px solid #DED7FF;
}
QPushButton#IconButton {
    background: transparent;
    color: #44536A;
    border: none;
    border-radius: 10px;
    padding: 6px;
    min-width: 28px;
}
QPushButton#IconButton[variant="action"] {
    border-radius: 8px;
    padding: 4px;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
}
QPushButton#IconButton:hover {
    background: #F1F4F9;
}
QToolButton {
    background: #EEF2F7;
    color: #172033;
    border: 1px solid #D2DAE8;
    border-radius: 6px;
    padding: 7px;
}
QToolButton#SectionToggle {
    background: #F7F9FC;
    color: #233149;
    border: 1px solid #D8E0ED;
    border-radius: 7px;
    font-weight: 600;
    padding: 8px 12px;
    text-align: left;
}
QToolButton#SectionToggle:hover {
    background: #EEF3F9;
    border-color: #C8D4E6;
}
QToolButton#SectionToggle:checked {
    background: #ECF4FF;
    border-color: #AFC8F0;
}
QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #FFFFFF;
    color: #172033;
    border: 1px solid #CED8E6;
    border-radius: 12px;
    padding: 9px;
    selection-background-color: #2F7CF6;
    selection-color: #FFFFFF;
}
QFrame#InputBox {
    background: #FFFFFF;
    border: 1px solid #CED8E6;
    border-radius: 14px;
}
QPlainTextEdit#CustomerEditor {
    background: transparent;
    border: none;
    border-radius: 12px;
    padding: 10px;
}
QFrame#ResponseBox {
    background: #FFFFFF;
    border: 1px solid #CED8E6;
    border-radius: 14px;
}
QPlainTextEdit#ResponseEditor {
    background: transparent;
    border: none;
    border-radius: 12px;
    padding: 10px;
}
QPlainTextEdit#OcrPreviewEditor {
    font-size: 12px;
    color: #4B5563;
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
QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #C7D2E0;
    border-radius: 6px;
    min-height: 36px;
}
QScrollBar::handle:vertical:hover {
    background: #94A3B8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
"""


RADIUS_PRESETS = {
    "soft": {
        "panel": 18,
        "rail": 22,
        "insight": 16,
        "control": 12,
        "input": 16,
        "chip": 12,
        "hero": 16,
        "icon": 12,
    },
    "medium": {
        "panel": 16,
        "rail": 18,
        "insight": 14,
        "control": 10,
        "input": 14,
        "chip": 10,
        "hero": 14,
        "icon": 10,
    },
    "hard": {
        "panel": 10,
        "rail": 14,
        "insight": 10,
        "control": 8,
        "input": 10,
        "chip": 8,
        "hero": 10,
        "icon": 8,
    },
}


def _appearance_overrides(theme: str, corner_radius: str, button_style: str) -> str:
    radius = RADIUS_PRESETS.get(corner_radius, RADIUS_PRESETS["medium"])
    is_light = theme == "light"

    if is_light:
        button_base = "#F8FAFC"
        button_hover = "#F3F4F6"
        button_border = "#DDE5F0"
        button_text = "#374151"
        ghost_bg = "#F8FAFC"
        ghost_hover = "#F3F4F6"
        primary_bg = "#6366F1"
        primary_hover = "#6A6DEE"
        hero_bg = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366F1, stop:1 #5A5EE1)"
        hero_hover = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6A6DEE, stop:1 #6064E4)"
    else:
        button_base = "#1F2937"
        button_hover = "#263244"
        button_border = "rgba(255,255,255,0.12)"
        button_text = "#F3F4F6"
        ghost_bg = "rgba(255,255,255,0.03)"
        ghost_hover = "rgba(255,255,255,0.07)"
        primary_bg = "#6366F1"
        primary_hover = "#6B6EF5"
        hero_bg = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366F1, stop:1 #565BD9)"
        hero_hover = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6B6EF5, stop:1 #5F63E8)"

    if button_style == "solid":
        ghost_bg = "#EEF2FF" if is_light else "#1E1B4B"
        ghost_hover = "#E0E7FF" if is_light else "#28206A"
        button_base = "#EEF2FF" if is_light else "#1E1B4B"
        button_hover = "#E0E7FF" if is_light else "#28206A"
        button_border = "#C7D2FE" if is_light else "rgba(129,140,248,0.38)"
        button_text = "#312E81" if is_light else "#EEF2FF"
    elif button_style == "minimal":
        ghost_bg = "transparent"
        ghost_hover = "rgba(99,102,241,0.08)" if is_light else "rgba(99,102,241,0.14)"
        button_base = "transparent"
        button_hover = ghost_hover
        button_border = "#E5E7EB" if is_light else "rgba(255,255,255,0.10)"
        button_text = "#374151" if is_light else "#D1D5DB"
        primary_bg = "#4F46E5"
        primary_hover = "#5B55E8"
        hero_bg = "#5B5FE8"
        hero_hover = "#6366F1"

    return f"""
QFrame#Panel {{
    border-radius: {radius["panel"]}px;
}}
QFrame#Rail {{
    border-radius: {radius["rail"]}px;
}}
QFrame#InsightPanel {{
    border-radius: {radius["insight"]}px;
}}
QFrame#InputBox,
QFrame#ResponseBox,
QTextEdit#ExpertContext,
QFrame#DropZone {{
    border-radius: {radius["input"]}px;
}}
QLabel#StatusPill,
QLabel#InsightChip,
QLabel#InsightSource {{
    border-radius: {radius["chip"]}px;
}}
QPushButton,
QToolButton {{
    border-radius: {radius["control"]}px;
}}
QPushButton#Ghost,
QPushButton#Tiny,
QToolButton#SectionToggle {{
    border-radius: {radius["control"]}px;
}}
QPushButton#HeroButton {{
    border-radius: {radius["hero"]}px;
}}
QPushButton#RailButton,
QPushButton#IconButton {{
    border-radius: {radius["icon"]}px;
}}
QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    border-radius: {radius["input"]}px;
}}
QPushButton {{
    background: {button_base};
    color: {button_text};
    border-color: {button_border};
}}
QPushButton:hover {{
    background: {button_hover};
}}
QPushButton#Primary {{
    background: {primary_bg};
    border-color: {primary_bg};
    color: #FFFFFF;
}}
QPushButton#Primary:hover {{
    background: {primary_hover};
    border-color: {primary_hover};
}}
QPushButton#Ghost,
QPushButton#Tiny {{
    background: {ghost_bg};
    color: {button_text};
    border-color: {button_border};
}}
QPushButton#Ghost:hover,
QPushButton#Tiny:hover {{
    background: {ghost_hover};
}}
QPushButton#HeroButton {{
    background: {hero_bg};
}}
QPushButton#HeroButton:hover {{
    background: {hero_hover};
}}
"""


def _theme_style_sheet(theme: str, corner_radius: str, button_style: str) -> str:
    base = LIGHT_STYLE_SHEET if theme == "light" else DARK_STYLE_SHEET
    return base + _appearance_overrides(theme, corner_radius, button_style)


def apply_theme(
    app: QApplication,
    theme: str = "dark",
    corner_radius: str = "medium",
    button_style: str = "soft",
) -> None:
    if theme == "light":
        _apply_light_theme(app, corner_radius, button_style)
    else:
        _apply_dark_theme(app, corner_radius, button_style)


def apply_dark_theme(app: QApplication) -> None:
    apply_theme(app, "dark")


def _apply_dark_theme(app: QApplication, corner_radius: str = "medium", button_style: str = "soft") -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#0B1020"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#F3F4F6"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#111827"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#111827"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#111827"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#F3F4F6"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#F3F4F6"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#111827"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#F3F4F6"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#6366F1"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)
    app.setStyleSheet(_theme_style_sheet("dark", corner_radius, button_style))


def _apply_light_theme(app: QApplication, corner_radius: str = "medium", button_style: str = "soft") -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#F5F7FB"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#111827"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#F8FAFC"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#111827"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#111827"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#F8FAFC"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#111827"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#6366F1"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)
    app.setStyleSheet(_theme_style_sheet("light", corner_radius, button_style))
