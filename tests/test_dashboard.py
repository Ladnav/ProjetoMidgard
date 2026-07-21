"""Tests for the operational Dashboard page."""

import sys

import pytest
from PySide6.QtWidgets import QApplication

from midgard.profile import ProfileStore
from midgard.ui.pages import DashboardPage


@pytest.fixture
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication(sys.argv)
    return instance


@pytest.fixture
def store(tmp_path):
    s = ProfileStore(tmp_path / "dash.db")
    yield s
    s.close()


def test_dashboard_empty_state(app, store) -> None:
    """With no profiles the aggregates read zero and the empty hint shows."""
    page = DashboardPage(store)
    assert page.profiles_card.value_label.text() == "0"
    assert page.xp_card.value_label.text() == "0"
    assert page.runtime_card.value_label.text() == "0s"
    # isVisible() needs a shown window; check the explicit hidden flag instead.
    assert not page._empty_label.isHidden()


def test_dashboard_aggregates_across_profiles(app, store) -> None:
    """Totals sum every profile's stats and compact formatting is applied."""
    a = store.create_profile("Alpha")
    b = store.create_profile("Beta")
    store.update_stats(
        a, experience_gained=1_500_000, deaths=1, loot_count=800, runtime_seconds=3600
    )
    store.update_stats(b, experience_gained=500_000, deaths=2, loot_count=200, runtime_seconds=1800)

    page = DashboardPage(store)

    assert page.profiles_card.value_label.text() == "2"
    assert page.xp_card.value_label.text() == "2.0M"  # 1.5M + 0.5M
    assert page.loot_card.value_label.text() == "1.0k"  # 800 + 200
    assert page.deaths_card.value_label.text() == "3"
    assert page.runtime_card.value_label.text() == "1h 30m"  # 5400s
    assert page._empty_label.isHidden()


def test_dashboard_lists_enabled_modules(app, store) -> None:
    """Each profile row reflects which automation modules are configured on."""
    from PySide6.QtWidgets import QLabel

    pid = store.create_profile("Gamma")
    store.set_rule(pid, "healing", "heal.enabled", "true")
    store.set_rule(pid, "combat", "combat.enabled", "true")

    page = DashboardPage(store)
    row = page._build_profile_row(store.get_profile(pid))

    chips = [c.text() for c in row.findChildren(QLabel)]
    enabled_chips = [c for c in chips if c.startswith("●")]  # filled circle
    disabled_chips = [c for c in chips if c.startswith("○")]  # hollow circle

    assert any("Healing" in c for c in enabled_chips)
    assert any("Combat" in c for c in enabled_chips)
    assert any("Looting" in c for c in disabled_chips)


def test_dashboard_refreshes_after_new_profile(app, store) -> None:
    """Refreshing picks up newly created profiles (drives showEvent path)."""
    page = DashboardPage(store)
    assert page.profiles_card.value_label.text() == "0"

    store.create_profile("Delta")
    page._refresh()

    assert page.profiles_card.value_label.text() == "1"
    assert page._empty_label.isHidden()
