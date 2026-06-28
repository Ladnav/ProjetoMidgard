"""Midgard Studio process bootstrap."""

import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication

from midgard import __version__
from midgard.logging_setup import configure_logging, get_logger
from midgard.settings import SettingsStore
from midgard.ui.main_window import MainWindow
from midgard.ui.theme import THEME_SETTING_KEY, Theme, stylesheet


def application_data_directory() -> Path:
    """Return the operating-system-specific writable application data directory."""
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    if location:
        return Path(location)
    return Path.home() / ".midgard-studio"


def create_application(
    arguments: Sequence[str] | None = None,
    *,
    data_directory: Path | None = None,
) -> tuple[QApplication, MainWindow, SettingsStore]:
    """Build the Qt application and its local services without starting the event loop."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(list(arguments) if arguments is not None else sys.argv)

    app.setOrganizationName("Project Midgard")
    app.setApplicationName("Midgard Studio")
    app.setApplicationVersion(__version__)

    local_data = data_directory or application_data_directory()
    log_path = configure_logging(local_data / "logs")
    logger = get_logger("application")
    settings = SettingsStore(local_data / "midgard-studio.db")
    initial_theme = Theme.from_value(settings.get(THEME_SETTING_KEY, Theme.DARK.value))

    def apply_theme(theme: Theme) -> None:
        app.setStyleSheet(stylesheet(theme))

    apply_theme(initial_theme)
    window = MainWindow(
        settings=settings,
        initial_theme=initial_theme,
        apply_theme=apply_theme,
        log_path=log_path,
        version=__version__,
    )
    app.aboutToQuit.connect(settings.close)
    logger.info("Midgard Studio %s initialized", __version__)
    logger.info("Application data directory: %s", local_data)
    return app, window, settings


def main() -> int:
    """Launch Midgard Studio."""
    app, window, _settings = create_application()
    window.show()
    return app.exec()
