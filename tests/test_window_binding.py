"""Tests for the dynamic window binding and injection features."""

from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QDialog, QMessageBox

from midgard.application import create_application
from midgard.vision.capture import list_windows_by_title, rename_window


def test_list_windows_by_title_mock() -> None:
    """The list_windows_by_title helper returns visible window handles."""
    with patch("ctypes.windll.user32.EnumWindows") as mock_enum:
        # Mocking EnumWindows to avoid actual native calls on headless environments
        mock_enum.return_value = True
        res = list_windows_by_title("nonexistent")
        assert isinstance(res, list)


def test_rename_window_invalid_handle() -> None:
    """The rename_window helper safely fails when given invalid HWND."""
    with patch("ctypes.windll.user32.IsWindow", return_value=False):
        success = rename_window(99999, "New Title")
        assert not success


def test_gui_inject_window_rename_action(tmp_path) -> None:
    """ProfilesPage inject button opens the window selection dialog and renames the window."""
    QMessageBox.information = MagicMock()
    QMessageBox.warning = MagicMock()
    QMessageBox.critical = MagicMock()

    app, window, settings = create_application([], data_directory=tmp_path)
    store = window.profile_store
    pid = store.create_profile("Odin")

    page = window._pages["Profiles"]
    page._reload_profiles()
    app.processEvents()

    # Set mock search query
    page.window_title_input.setText("Ragnarok")

    mock_windows = [(12345, 9999, "Ragnarok Client 1"), (67890, 8888, "Ragnarok Client 2")]

    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
    mock_dialog.selected_hwnd = 12345
    mock_dialog.selected_pid = 9999
    mock_dialog.selected_title = "Ragnarok Client 1"

    with (
        patch("midgard.ui.pages.list_windows_by_title_with_pid", return_value=mock_windows),
        patch("midgard.ui.pages.WindowListDialog", return_value=mock_dialog),
    ):
        # Trigger inject action
        page._inject_window_rename()
        app.processEvents()

        # Check if PID format title is saved
        assert page.window_title_input.text() == "Odin [PID: 9999]"
        db_profile = store.get_profile(pid)
        assert db_profile.window_title == "Odin [PID: 9999]"

    window.close()
    store.close()
    settings.close()
