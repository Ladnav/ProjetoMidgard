"""Tests for SQLite-backed application settings."""

import sqlite3

from midgard.settings import SettingsStore


def test_setting_persists_across_store_instances(tmp_path) -> None:
    """A saved preference remains available after the connection is reopened."""
    database_path = tmp_path / "settings.db"
    store = SettingsStore(database_path)
    store.set("appearance.theme", "light")
    store.close()

    reopened_store = SettingsStore(database_path)

    assert reopened_store.get("appearance.theme") == "light"
    assert reopened_store.get("missing", "fallback") == "fallback"
    reopened_store.close()


def test_settings_schema_is_created(tmp_path) -> None:
    """Initializing the store creates only the required settings table."""
    database_path = tmp_path / "settings.db"
    store = SettingsStore(database_path)
    store.close()

    with sqlite3.connect(database_path) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()

    assert tables == [("app_settings",)]
