import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from app.core.settings_manager import SettingsManager
from app.core.privacy_guard import install_network_guard
from app.storage.database import Database
from app.styles.style_manager import StyleManager
from app.ai.ai_manager import AIManager
from app.ocr.ocr_manager import OCRManager
from app.ui.main_window import MainWindow
from app.ui.theme import apply_theme


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Local Support AI")
    app.setOrganizationName("Local Support AI")
    icon_path = Path(__file__).resolve().parent.parent / "assets" / "app_icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    settings = SettingsManager()
    apply_theme(app, settings.values.theme)
    install_network_guard(allow_localhost=not settings.values.network_disabled)
    database = Database(settings.database_path)
    style_manager = StyleManager(database)
    ai_manager = AIManager(settings)
    ocr_manager = OCRManager(settings)

    window = MainWindow(
        settings=settings,
        database=database,
        style_manager=style_manager,
        ai_manager=ai_manager,
        ocr_manager=ocr_manager,
    )
    window.show()
    return app.exec()
