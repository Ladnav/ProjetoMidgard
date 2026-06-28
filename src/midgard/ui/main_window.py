"""Main Midgard Studio window and navigation shell."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from midgard.logging_setup import get_logger
from midgard.settings import SettingsStore
from midgard.ui.pages import AboutPage, LogsPage, Page, SettingsPage
from midgard.ui.theme import THEME_SETTING_KEY, Theme

PAGE_NAMES = (
    "Dashboard",
    "Profiles",
    "Runtime",
    "Statistics",
    "Settings",
    "Logs",
    "About",
)


class MainWindow(QMainWindow):
    """Top-level application window with persistent appearance settings."""

    def __init__(
        self,
        settings: SettingsStore,
        initial_theme: Theme,
        apply_theme: Callable[[Theme], None],
        log_path: Path,
        version: str,
    ) -> None:
        super().__init__()
        self._logger = get_logger("ui")
        self._settings = settings
        self._apply_theme = apply_theme
        self._buttons: dict[str, QPushButton] = {}
        self._pages: dict[str, QWidget] = {}
        self.active_launchers = []

        self.setWindowTitle("Midgard Studio")
        self.setMinimumSize(960, 640)
        self.resize(1180, 760)
        self._build_interface(initial_theme, log_path, version)
        self.statusBar().showMessage("Ready — graphical foundation only")
        self.select_page("Dashboard")

    @property
    def page_names(self) -> tuple[str, ...]:
        """Return the ordered navigation labels."""
        return PAGE_NAMES

    @property
    def current_page_name(self) -> str:
        """Return the title of the visible page."""
        page = self.page_stack.currentWidget()
        return str(page.property("pageName")) if page is not None else ""

    def _build_interface(self, initial_theme: Theme, log_path: Path, version: str) -> None:
        central = QWidget()
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("pageStack")
        root_layout.addWidget(self.page_stack, 1)
        self.setCentralWidget(central)

        page_widgets: dict[str, QWidget] = {
            "Dashboard": Page(
                "Dashboard",
                "A clear starting point for the Midgard Studio workspace.",
                "Studio foundation ready",
                "No automation is configured or running. Future capabilities will be added "
                "only through approved tasks.",
            ),
            "Profiles": Page(
                "Profiles",
                "Character profiles will be managed here.",
                "No profiles yet",
                "Profile storage and behavior remain an open design decision.",
            ),
            "Runtime": Page(
                "Runtime",
                "Runtime status will appear here when that capability is approved.",
                "Runtime not implemented",
                "This page is intentionally informational and contains no runtime logic.",
            ),
            "Statistics": Page(
                "Statistics",
                "Future operational metrics will be presented here.",
                "No statistics available",
                "Data collection and reporting have not been designed or implemented.",
            ),
            "Settings": SettingsPage(initial_theme),
            "Logs": LogsPage(log_path),
            "About": AboutPage(version),
        }

        for name in PAGE_NAMES:
            page = page_widgets[name]
            page.setProperty("pageName", name)
            self._pages[name] = page
            self.page_stack.addWidget(page)

        settings_page = self._pages["Settings"]
        if isinstance(settings_page, SettingsPage):
            settings_page.theme_selected.connect(self.set_theme)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(232)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 28, 18, 20)
        sidebar_layout.setSpacing(6)

        brand = QLabel("MIDGARD")
        brand.setObjectName("brandMark")
        brand_subtitle = QLabel("STUDIO")
        brand_subtitle.setObjectName("brandSubtitle")
        sidebar_layout.addWidget(brand)
        sidebar_layout.addWidget(brand_subtitle)
        sidebar_layout.addSpacing(28)

        button_group = QButtonGroup(self)
        button_group.setExclusive(True)
        for name in PAGE_NAMES:
            button = QPushButton(name)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda checked=False, page_name=name: self.select_page(page_name)
            )
            button_group.addButton(button)
            self._buttons[name] = button
            sidebar_layout.addWidget(button)

        sidebar_layout.addStretch(1)
        footer = QLabel("FOUNDATION BUILD")
        footer.setObjectName("sidebarFooter")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(footer)
        return sidebar

    def select_page(self, name: str) -> None:
        """Display a page by navigation name."""
        page = self._pages.get(name)
        button = self._buttons.get(name)
        if page is None or button is None:
            raise ValueError(f"Unknown page: {name}")
        self.page_stack.setCurrentWidget(page)
        button.setChecked(True)
        self._logger.info("Opened %s page", name)

    def set_theme(self, value: str | Theme) -> None:
        """Apply and persist a supported visual theme."""
        theme = value if isinstance(value, Theme) else Theme.from_value(value)
        self._apply_theme(theme)
        self._settings.set(THEME_SETTING_KEY, theme.value)

        settings_page = self._pages.get("Settings")
        if isinstance(settings_page, SettingsPage):
            settings_page.set_theme(theme)
        self._logger.info("Applied %s theme", theme.value)
