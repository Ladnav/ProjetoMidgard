"""Tests for the OCR-based experience tracker."""

from unittest.mock import MagicMock

from PIL import Image

from midgard.runtime.experience import ExperienceTracker


def _tracker(**overrides) -> ExperienceTracker:
    rules = {
        "experience.enabled": "true",
        "experience.x": "0",
        "experience.y": "0",
        "experience.w": "50",
        "experience.h": "10",
        "experience.interval": "0.0",  # sample on every call in tests
    }
    rules.update(overrides)
    tracker = ExperienceTracker(rules)
    tracker.recognizer = MagicMock()
    return tracker


def _image() -> Image.Image:
    return Image.new("RGB", (80, 20), color=(0, 0, 0))


def test_disabled_tracker_does_nothing() -> None:
    tracker = _tracker(**{"experience.enabled": "false"})
    assert tracker.evaluate(_image()) is None
    assert tracker.total_gained == 0


def test_first_reading_only_sets_baseline() -> None:
    """The initial sample must not be counted as a gain."""
    tracker = _tracker()
    tracker.recognizer.parse_image.return_value = "1000"

    assert tracker.evaluate(_image()) is None
    assert tracker.total_gained == 0
    assert tracker.last_value == 1000


def test_positive_delta_accumulates() -> None:
    tracker = _tracker()
    tracker.recognizer.parse_image.return_value = "1000"
    tracker.evaluate(_image())  # baseline

    tracker.recognizer.parse_image.return_value = "1250"
    log = tracker.evaluate(_image())
    assert log is not None and "+250" in log
    assert tracker.total_gained == 250

    tracker.recognizer.parse_image.return_value = "1300"
    tracker.evaluate(_image())
    assert tracker.total_gained == 300


def test_unchanged_value_reports_nothing() -> None:
    tracker = _tracker()
    tracker.recognizer.parse_image.return_value = "500"
    tracker.evaluate(_image())

    assert tracker.evaluate(_image()) is None
    assert tracker.total_gained == 0


def test_counter_reset_is_treated_as_level_up_not_negative_gain() -> None:
    """A drop (level up) must re-baseline instead of subtracting experience."""
    tracker = _tracker()
    tracker.recognizer.parse_image.return_value = "9000"
    tracker.evaluate(_image())

    tracker.recognizer.parse_image.return_value = "120"
    log = tracker.evaluate(_image())

    assert log is not None and "level up" in log.lower()
    assert tracker.total_gained == 0
    assert tracker.level_ups == 1
    assert tracker.last_value == 120

    # Subsequent gains continue from the new baseline.
    tracker.recognizer.parse_image.return_value = "300"
    tracker.evaluate(_image())
    assert tracker.total_gained == 180


def test_implausible_jump_is_ignored_when_max_delta_set() -> None:
    tracker = _tracker(**{"experience.max_delta": "1000"})
    tracker.recognizer.parse_image.return_value = "100"
    tracker.evaluate(_image())

    tracker.recognizer.parse_image.return_value = "999999"
    log = tracker.evaluate(_image())

    assert log is not None and "implausible" in log.lower()
    assert tracker.total_gained == 0


def test_unreadable_region_returns_none() -> None:
    tracker = _tracker()
    tracker.recognizer.parse_image.return_value = ""
    assert tracker.evaluate(_image()) is None
    assert tracker.last_value is None


def test_interval_throttles_sampling() -> None:
    """With an interval configured, a second immediate call is skipped."""
    tracker = _tracker(**{"experience.interval": "60.0"})
    tracker.recognizer.parse_image.return_value = "100"

    tracker.evaluate(_image())  # baseline, consumes the interval slot
    tracker.recognizer.parse_image.return_value = "900"
    assert tracker.evaluate(_image()) is None
    assert tracker.total_gained == 0


def test_read_value_clamps_region_to_image_bounds() -> None:
    """A region larger than the frame is clipped instead of raising."""
    tracker = _tracker(**{"experience.w": "9999", "experience.h": "9999"})
    tracker.recognizer.parse_image.return_value = "42"
    assert tracker.read_value(_image()) == 42
