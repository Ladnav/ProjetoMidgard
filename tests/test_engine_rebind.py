"""Tests for engine window re-binding and cached settings lookups."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from midgard.runtime.engine import RuntimeEngine


def _engine() -> RuntimeEngine:
    engine = RuntimeEngine(
        profile_id=1,
        database_path=Path("unused.db"),
        studio_port=0,
        use_dummy_input=True,
    )
    engine._sock = MagicMock()
    engine.window_title = "Ragnarok [PID: 4242]"
    engine.profile_name = "Thor"
    return engine


def test_rebind_reattaches_and_updates_dependent_modules() -> None:
    """A successful re-bind refreshes the HWND held by input and modules."""
    engine = _engine()
    engine.combat_module = MagicMock()
    engine.navigation_module = MagicMock()
    engine.input_adapter = MagicMock()
    engine.capture_failures = 7

    new_service = MagicMock()
    new_service.hwnd = 999

    with patch(
        "midgard.runtime.engine.WindowCaptureService.from_title", return_value=new_service
    ) as from_title:
        assert engine._rebind_window() is True
        from_title.assert_called_once_with("Ragnarok [PID: 4242]")

    assert engine.capture_service is new_service
    assert engine.combat_module.hwnd == 999
    assert engine.navigation_module.hwnd == 999
    engine.input_adapter.set_hwnd.assert_called_once_with(999)
    assert engine.capture_failures == 0


def test_rebind_falls_back_to_profile_name() -> None:
    """When the stored title no longer resolves, the profile name is tried."""
    engine = _engine()
    new_service = MagicMock()
    new_service.hwnd = 5

    def side_effect(title: str):
        if title == "Thor":
            return new_service
        raise ValueError("not found")

    with patch("midgard.runtime.engine.WindowCaptureService.from_title", side_effect=side_effect):
        assert engine._rebind_window() is True

    assert engine.capture_service is new_service


def test_rebind_returns_false_when_no_window_matches() -> None:
    engine = _engine()
    with patch(
        "midgard.runtime.engine.WindowCaptureService.from_title",
        side_effect=ValueError("gone"),
    ):
        assert engine._rebind_window() is False


def test_rebind_is_rate_limited() -> None:
    """Consecutive attempts are throttled so a dead client cannot spin the loop."""
    engine = _engine()
    with patch(
        "midgard.runtime.engine.WindowCaptureService.from_title",
        side_effect=ValueError("gone"),
    ) as from_title:
        assert engine._rebind_window() is False
        first_calls = from_title.call_count

        # Immediate retry must be skipped entirely.
        assert engine._rebind_window() is False
        assert from_title.call_count == first_calls


def test_desktop_fallback_setting_is_cached() -> None:
    """The settings database is not reopened on every tick."""
    engine = _engine()
    store = MagicMock()
    store.get.return_value = "true"

    with patch("midgard.settings.SettingsStore", return_value=store) as store_cls:
        assert engine._desktop_fallback_enabled() is True
        assert store_cls.call_count == 1

        # Subsequent calls within the cache window reuse the value.
        assert engine._desktop_fallback_enabled() is True
        assert store_cls.call_count == 1
