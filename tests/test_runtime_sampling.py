"""Tests for runtime telemetry throttling, runtime accounting, and stat formatting."""

import sys

import pytest
from PySide6.QtWidgets import QApplication

from midgard.profile import ProfileStore
from midgard.ui.pages import RuntimePage, _format_duration


@pytest.fixture
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication(sys.argv)
    return instance


@pytest.fixture
def page(app, tmp_path):
    store = ProfileStore(tmp_path / "sampling.db")
    profile_id = store.create_profile("Sampler")
    runtime_page = RuntimePage(store)
    runtime_page.refresh_profiles()
    index = runtime_page.profile_combo.findData(profile_id)
    runtime_page.profile_combo.setCurrentIndex(index)
    yield runtime_page, store, profile_id
    store.close()


def test_status_updates_labels_every_message(page) -> None:
    """Label refreshes are not throttled; only persistence is."""
    runtime_page, _store, _pid = page
    for xp in (10, 20, 30):
        runtime_page._on_status_received({"hp_pct": 90, "xp_gained": xp, "loot_collected": 1})
    assert "30" in runtime_page.xp_card.value_label.text()


def test_sampling_is_throttled_to_one_per_interval(page) -> None:
    """The engine emits ~20 status messages/second; only one is recorded.

    Regression test: unthrottled persistence wrote roughly 72k rows per hour and
    shrank the live chart to a few seconds of history.
    """
    runtime_page, store, profile_id = page

    for i in range(25):
        runtime_page._on_status_received({"hp_pct": 80, "xp_gained": i * 10, "loot_collected": i})

    samples = store.get_stat_samples(profile_id)
    assert len(samples) == 1, f"expected a single throttled sample, stored {len(samples)}"
    assert len(runtime_page.live_chart.xp_data) == 1


def test_runtime_seconds_uses_elapsed_time_not_message_count(page) -> None:
    """Runtime must accumulate wall time, not a flat 1.0 per status message.

    Regression test: adding 1.0 per message at ~20 messages/second overstated
    the session duration by a factor of ~20.
    """
    runtime_page, store, profile_id = page

    for i in range(30):
        runtime_page._on_status_received({"hp_pct": 80, "xp_gained": i, "loot_collected": 0})

    profile = store.get_profile(profile_id)
    # 30 rapid messages span well under a second of real time.
    assert profile.stats.runtime_seconds < 2.0


def test_hp_bar_reflects_health_and_flags_low_state(page) -> None:
    runtime_page, _store, _pid = page

    runtime_page._on_status_received({"hp_pct": 95, "xp_gained": 0, "loot_collected": 0})
    assert runtime_page.hp_bar.value() == 95
    assert runtime_page.hp_bar.property("level") == "ok"

    runtime_page._on_status_received({"hp_pct": 20, "xp_gained": 0, "loot_collected": 0})
    assert runtime_page.hp_bar.value() == 20
    assert runtime_page.hp_bar.property("level") == "low"


def test_hp_bar_clamps_out_of_range_values(page) -> None:
    runtime_page, _store, _pid = page
    runtime_page._on_status_received({"hp_pct": 150, "xp_gained": 0, "loot_collected": 0})
    assert runtime_page.hp_bar.value() == 100


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0s"),
        (45, "45s"),
        (600, "10m 00s"),
        (750, "12m 30s"),
        (3600, "1h 00m"),
        (11100, "3h 05m"),
        (-5, "0s"),
    ],
)
def test_format_duration(seconds, expected) -> None:
    assert _format_duration(seconds) == expected
