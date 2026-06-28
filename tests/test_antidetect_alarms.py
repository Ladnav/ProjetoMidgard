"""Tests for Midgard antidetection input protections and IPC alarm notifications."""

from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QMessageBox

from midgard.application import create_application
from midgard.runtime.input import DummyInputAdapter, generate_bezier_path

# ---------------------------------------------------------------------------
# 1. Bezier Path Generation
# ---------------------------------------------------------------------------


def test_bezier_path_start_to_end_coverage() -> None:
    """Bezier path must start near the origin and end at the target point."""
    start = (0, 0)
    end = (200, 150)
    path = generate_bezier_path(start, end, steps=20)

    assert len(path) > 1
    # First point should be near the start
    assert abs(path[0][0] - start[0]) < 5
    assert abs(path[0][1] - start[1]) < 5
    # Last point should equal end
    assert abs(path[-1][0] - end[0]) < 5
    assert abs(path[-1][1] - end[1]) < 5


def test_bezier_path_short_distance_returns_end() -> None:
    """For very close start/end points, path should just return the end point."""
    path = generate_bezier_path((100, 100), (101, 100))
    assert path == [(101, 100)]


def test_bezier_path_contains_intermediate_points() -> None:
    """Path must contain intermediate coordinates between start and end."""
    path = generate_bezier_path((0, 0), (300, 300), steps=15)
    # More than just the start and end
    assert len(path) >= 3


# ---------------------------------------------------------------------------
# 2. Input Adapter — Randomized Hold Times
# ---------------------------------------------------------------------------


def test_tap_key_hold_time_is_randomized() -> None:
    """tap_key must sleep for a randomized duration between press and release."""
    adapter = DummyInputAdapter()

    with (
        patch("midgard.runtime.input.time") as mock_time,
        patch("midgard.runtime.input.random") as mock_random,
    ):
        mock_random.uniform.return_value = 0.07
        mock_time.sleep = MagicMock()

        adapter.tap_key(0x3B)  # F1

        # sleep must have been called once with the randomized duration
        mock_time.sleep.assert_called_once_with(0.07)
        # uniform must have been called with the expected bounds
        mock_random.uniform.assert_called_once_with(0.04, 0.09)

    assert ("press", 0x3B) in adapter.history
    assert ("release", 0x3B) in adapter.history


# ---------------------------------------------------------------------------
# 3. Engine Alarm Emissions
# ---------------------------------------------------------------------------


def test_engine_sends_death_alarm_when_hp_is_zero() -> None:
    """RuntimeEngine._tick should emit a death alarm if the HP pixel is black."""
    from pathlib import Path
    from unittest.mock import MagicMock

    from midgard.runtime.engine import RuntimeEngine

    engine = RuntimeEngine(profile_id=1, database_path=Path(":memory:"), studio_port=0)
    engine._sock = MagicMock()
    engine.xp_gained = 0
    engine.loot_collected = 0
    engine.capture_failures = 0

    # Mock heal module: enabled, with small HP pixel coords
    mock_heal = MagicMock()
    mock_heal.enabled = True
    mock_heal.hp_x = 0
    mock_heal.hp_y = 0
    mock_heal.expected_hp_r = 0
    mock_heal.expected_hp_g = 255
    mock_heal.expected_hp_b = 0
    mock_heal.color_tolerance = 30
    mock_heal.hp_threshold = 70.0
    mock_heal.evaluate.return_value = None
    engine.heal_module = mock_heal

    # Mock capture service returning a black image (HP bar depleted = death)
    from PIL import Image

    black_image = Image.new("RGB", (10, 10), color=(0, 0, 0))
    mock_capture = MagicMock()
    mock_capture.capture.return_value = black_image
    engine.capture_service = mock_capture

    sent_messages = []

    def capture_send(sock, msg):
        sent_messages.append(msg)

    with patch("midgard.runtime.engine.send_message", side_effect=capture_send):
        engine._tick()

    alarm_events = [m for m in sent_messages if m.get("type") == "alarm"]
    assert any(e["alarm_type"] == "death" for e in alarm_events), (
        f"Expected death alarm in {alarm_events}"
    )


def test_engine_sends_disconnect_alarm_after_consecutive_failures() -> None:
    """RuntimeEngine._tick should emit disconnect alarm after 5 consecutive capture errors."""
    from pathlib import Path

    from midgard.runtime.engine import RuntimeEngine

    engine = RuntimeEngine(profile_id=1, database_path=Path(":memory:"), studio_port=0)
    engine._sock = MagicMock()
    engine.xp_gained = 0
    engine.loot_collected = 0
    engine.capture_failures = 4  # Already had 4 prior failures

    # Mock capture service that throws an exception
    mock_capture = MagicMock()
    mock_capture.capture.side_effect = Exception("GDI window not found")
    engine.capture_service = mock_capture

    sent_messages = []

    def capture_send(sock, msg):
        sent_messages.append(msg)

    with patch("midgard.runtime.engine.send_message", side_effect=capture_send):
        engine._tick()

    alarm_events = [m for m in sent_messages if m.get("type") == "alarm"]
    assert any(e["alarm_type"] == "disconnect" for e in alarm_events), (
        f"Expected disconnect alarm in {alarm_events}"
    )


# ---------------------------------------------------------------------------
# 4. GUI Alarm Handler
# ---------------------------------------------------------------------------


def test_gui_runtime_page_handles_alarm_signal(tmp_path) -> None:
    """RuntimePage._on_alarm_received should update status label and append terminal log."""
    QMessageBox.information = MagicMock()
    QMessageBox.warning = MagicMock()
    QMessageBox.critical = MagicMock()

    with patch("PySide6.QtWidgets.QApplication.beep"):
        app, window, settings = create_application([], data_directory=tmp_path)
        runtime_page = window._pages["Runtime"]
        app.processEvents()

        # Trigger death alarm signal
        runtime_page._on_alarm_received("death", "Character death detected! HP is 0%.")
        app.processEvents()

        assert "DEATH" in runtime_page.status_lbl.text().upper()
        assert "ALARM" in runtime_page.terminal.toPlainText()

        # Trigger disconnect alarm signal
        runtime_page._on_alarm_received("disconnect", "Game client disconnected.")
        app.processEvents()

        assert "DISCONNECT" in runtime_page.status_lbl.text().upper()

        window.close()
        settings.close()
