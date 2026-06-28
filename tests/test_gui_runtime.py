"""Tests for the Midgard Studio Runtime Controller GUI."""

from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QMessageBox

from midgard.application import create_application


def test_runtime_gui_page_integration(tmp_path) -> None:
    """The RuntimePage allows selecting a profile, starting the engine launcher, and stopping it."""
    # Mock QMessageBox popups
    QMessageBox.information = MagicMock()
    QMessageBox.warning = MagicMock()
    QMessageBox.critical = MagicMock()

    app, window, settings = create_application([], data_directory=tmp_path)
    store = window.profile_store

    # 1. Create a character profile
    store.create_profile("Odin")

    # 2. Get pages
    profiles_page = window._pages["Profiles"]
    runtime_page = window._pages["Runtime"]

    # Reload profiles inside GUI pages
    profiles_page._reload_profiles()
    runtime_page.refresh_profiles()
    app.processEvents()

    assert runtime_page.profile_combo.count() == 1
    assert runtime_page.profile_combo.currentText() == "Odin"

    # Mock the launcher to prevent spawning real subprocesses in headless tests
    mock_launcher = MagicMock()
    mock_launcher.is_alive.return_value = True

    # Use patch to replace RuntimeLauncher with our mock
    with patch("midgard.ui.pages.RuntimeLauncher", return_value=mock_launcher):
        # Trigger start click
        runtime_page._start_runtime()
        app.processEvents()

        # Verify buttons states
        assert not runtime_page.start_btn.isEnabled()
        assert runtime_page.pause_btn.isEnabled()
        assert runtime_page.stop_btn.isEnabled()

        # Simulate receiving a log event from the engine via the worker signals
        # We can call the handler directly to test GUI text terminal append
        runtime_page._on_log_received("Connection established", "INFO")
        app.processEvents()
        assert "Connection established" in runtime_page.terminal.toPlainText()

        # Simulate receiving status event
        status_data = {"type": "status", "hp_pct": 78, "xp_gained": 120, "loot_collected": 5}
        runtime_page._on_status_received(status_data)
        app.processEvents()
        assert "HP: 78%" in runtime_page.hp_lbl.text()
        assert "XP Gained: 120" in runtime_page.xp_lbl.text()
        assert "Loot: 5" in runtime_page.loot_lbl.text()

        # Toggle pause state
        runtime_page._pause_runtime()
        assert mock_launcher.send_command.called
        assert mock_launcher.send_command.call_args[0][0] == "pause"
        assert runtime_page.pause_btn.text() == "Resume"

        # Click Stop
        runtime_page._stop_runtime()
        assert mock_launcher.send_command.call_args[0][0] == "stop"

    # Clean up launcher
    runtime_page._cleanup_launcher()
    window.close()
    store.close()
    settings.close()
