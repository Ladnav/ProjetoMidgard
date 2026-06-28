"""Tests for the Midgard Studio GUI Color & Position Picker."""

from unittest.mock import MagicMock, patch

from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QDialog, QMessageBox

from midgard.application import create_application
from midgard.ui.picker import PickDialog


def test_pick_dialog_captures_coordinates_and_color() -> None:
    """PickDialog captures coordinates and colors upon clicking the target area."""
    pixmap = QPixmap(50, 50)
    pixmap.fill(QColor(10, 20, 30))  # Fill with custom RGB color

    dialog = PickDialog(pixmap)

    # Simulate user clicking coordinates (15, 25)
    dialog._on_clicked(15, 25, 10, 20, 30)

    assert dialog.selected_x == 15
    assert dialog.selected_y == 25
    assert dialog.selected_r == 10
    assert dialog.selected_g == 20
    assert dialog.selected_b == 30


def test_profiles_page_picker_integration(tmp_path) -> None:
    """ProfilesPage picker button triggers screen capture and populates coordinates and colors."""
    # Mock QMessageBox popups
    QMessageBox.information = MagicMock()
    QMessageBox.warning = MagicMock()
    QMessageBox.critical = MagicMock()

    app, window, settings = create_application([], data_directory=tmp_path)
    store = window.profile_store

    # Create character profile
    store.create_profile("Thor")

    profiles_page = window._pages["Profiles"]
    profiles_page._reload_profiles()
    app.processEvents()

    # Create a test pixmap representing a mock screenshot
    mock_pixmap = QPixmap(100, 100)
    mock_pixmap.fill(QColor(255, 128, 64))

    # Mock the capture method to return our test pixmap
    profiles_page._capture_game_window = MagicMock(return_value=mock_pixmap)

    with patch("midgard.ui.pages.PickDialog") as MockPickDialog:
        mock_inst = MagicMock()
        mock_inst.exec.return_value = QDialog.Accepted
        mock_inst.selected_x = 42
        mock_inst.selected_y = 84
        mock_inst.selected_r = 255
        mock_inst.selected_g = 128
        mock_inst.selected_b = 64
        MockPickDialog.return_value = mock_inst

        # 1. Trigger Healing Picker
        profiles_page._pick_hp_crop()
        app.processEvents()

        # Check that coordinates and expected color were updated
        assert profiles_page.heal_hp_x.value() == 42
        assert profiles_page.heal_hp_y.value() == 84

        # 2. Trigger Combat Picker
        profiles_page._pick_combat_color()
        app.processEvents()

        # Check that combat target color was updated
        assert profiles_page.combat_target_r.value() == 255
        assert profiles_page.combat_target_g.value() == 128
        assert profiles_page.combat_target_b.value() == 64

        # 3. Trigger Verify Crops modal check
        with patch("PySide6.QtWidgets.QDialog.exec", return_value=QDialog.Accepted):
            profiles_page._verify_healing_crops()
            app.processEvents()

    # Close resources
    window.close()
    store.close()
    settings.close()
