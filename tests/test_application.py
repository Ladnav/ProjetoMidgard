"""Tests for the executable Midgard Studio shell."""

from PySide6.QtWidgets import QLabel

from midgard import __version__
from midgard.application import create_application
from midgard.settings import SettingsStore
from midgard.ui.theme import THEME_SETTING_KEY, Theme


def test_application_exposes_all_required_pages(tmp_path) -> None:
    """The main window contains the approved navigation destinations."""
    app, window, settings = create_application([], data_directory=tmp_path)

    assert window.page_names == (
        "Dashboard",
        "Profiles",
        "Runtime",
        "Statistics",
        "Settings",
        "Logs",
        "About",
    )
    assert window.page_stack.count() == 7
    assert window.current_page_name == "Dashboard"

    window.select_page("About")
    app.processEvents()

    assert window.current_page_name == "About"
    assert any(f"Version {__version__}" in label.text() for label in window.findChildren(QLabel))
    window.close()
    window.profile_store.close()
    settings.close()


def test_theme_selection_is_applied_and_persisted(tmp_path) -> None:
    """Changing themes updates Qt and the SQLite-backed preference."""
    app, window, settings = create_application([], data_directory=tmp_path)

    window.set_theme(Theme.LIGHT)
    app.processEvents()

    assert settings.get(THEME_SETTING_KEY) == Theme.LIGHT.value
    assert "#f3f6f9" in app.styleSheet()
    window.close()
    window.profile_store.close()
    settings.close()


def test_saved_theme_is_loaded_on_next_start(tmp_path) -> None:
    """Application startup restores the theme from the SQLite settings database."""
    stored_settings = SettingsStore(tmp_path / "midgard-studio.db")
    stored_settings.set(THEME_SETTING_KEY, Theme.LIGHT.value)
    stored_settings.close()

    app, window, settings = create_application([], data_directory=tmp_path)

    assert "#f3f6f9" in app.styleSheet()
    window.close()
    window.profile_store.close()
    settings.close()


def test_application_initialization_writes_a_log_file(tmp_path) -> None:
    """Starting the shell initializes the basic rotating application logger."""
    _app, window, settings = create_application([], data_directory=tmp_path)
    log_path = tmp_path / "logs" / "midgard-studio.log"

    assert log_path.is_file()
    assert "Midgard Studio" in log_path.read_text(encoding="utf-8")
    window.close()
    window.profile_store.close()
    settings.close()
