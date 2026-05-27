import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from app.core.backend_launcher import LocalBackendLauncher
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
    project_root = Path(__file__).resolve().parent.parent
    icon_path = project_root / "assets" / "app_icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    settings = SettingsManager()
    apply_theme(app, settings.values.theme, settings.values.corner_radius, settings.values.button_style)
    install_network_guard(allow_localhost=not settings.values.network_disabled)
    backend_launcher = LocalBackendLauncher(project_root)
    if not settings.values.network_disabled:
        backend_launcher.ensure_running()
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
    try:
        return app.exec()
    finally:
        backend_launcher.stop()
