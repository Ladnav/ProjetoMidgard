"""Tests for the SQLite-backed character profiles store."""

import sqlite3
from pathlib import Path

import pytest

from midgard.profile import ProfileStats, ProfileStore


@pytest.fixture
def store(tmp_path: Path) -> ProfileStore:
    """Fixture to create a ProfileStore instance in a temporary file."""
    db_path = tmp_path / "midgard-test.db"
    store_inst = ProfileStore(db_path)
    yield store_inst
    store_inst.close()


def test_create_and_fetch_profile(store: ProfileStore) -> None:
    """We can create a profile and retrieve it with correct metadata and empty stats/rules."""
    profile_id = store.create_profile("Thor", "Swordman", "Ragnarok Online")
    assert profile_id == 1

    profile = store.get_profile(profile_id)
    assert profile is not None
    assert profile.id == profile_id
    assert profile.name == "Thor"
    assert profile.character_class == "Swordman"
    assert profile.window_title == "Ragnarok Online"
    assert profile.rules == {}
    assert isinstance(profile.stats, ProfileStats)
    assert profile.stats.experience_gained == 0


def test_get_profile_by_name(store: ProfileStore) -> None:
    """We can retrieve a profile using its unique name."""
    profile_id = store.create_profile("Odin", "Acolyte")
    profile = store.get_profile_by_name("Odin")

    assert profile is not None
    assert profile.id == profile_id
    assert profile.name == "Odin"
    assert profile.character_class == "Acolyte"

    assert store.get_profile_by_name("Nonexistent") is None


def test_list_profiles(store: ProfileStore) -> None:
    """We can list all profiles sorted by name."""
    store.create_profile("Zeke", "Merchant")
    store.create_profile("Alice", "Mage")

    profiles = store.list_profiles()
    assert len(profiles) == 2
    assert profiles[0].name == "Alice"
    assert profiles[1].name == "Zeke"


def test_profile_rules_persistence_and_update(store: ProfileStore) -> None:
    """Rules can be set, updated, and retrieved correctly under specific categories."""
    profile_id = store.create_profile("Loki", "Thief")

    # Set initial rule
    store.set_rule(profile_id, "healing", "use_potion_hp", "70")
    rules = store.get_rules(profile_id, "healing")
    assert rules == {"use_potion_hp": "70"}

    # Update rule (conflict resolution)
    store.set_rule(profile_id, "healing", "use_potion_hp", "80")
    rules = store.get_rules(profile_id, "healing")
    assert rules == {"use_potion_hp": "80"}

    # Fetch complete profile to verify rules are loaded
    profile = store.get_profile(profile_id)
    assert profile is not None
    assert profile.rules == {"healing": {"use_potion_hp": "80"}}


def test_profile_statistics_update(store: ProfileStore) -> None:
    """We can update session tracking metrics for a profile."""
    profile_id = store.create_profile("Freya", "Archer")

    store.update_stats(
        profile_id=profile_id,
        experience_gained=5000,
        deaths=2,
        loot_count=150,
        runtime_seconds=3600.5,
    )

    profile = store.get_profile(profile_id)
    assert profile is not None
    assert profile.stats.experience_gained == 5000
    assert profile.stats.deaths == 2
    assert profile.stats.loot_count == 150
    assert profile.stats.runtime_seconds == 3600.5


def test_profile_cascade_delete(store: ProfileStore, tmp_path: Path) -> None:
    """Deleting a profile also deletes all its stats and rules via foreign keys."""
    profile_id = store.create_profile("Balder", "Swordman")
    store.set_rule(profile_id, "loot", "pickup_cards", "true")

    # Verify they exist in DB
    with sqlite3.connect(store.database_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM profile_rules").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM profile_stats").fetchone()[0] == 1

    # Delete the profile
    store.delete_profile(profile_id)

    # Verify cascading delete
    with sqlite3.connect(store.database_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM profile_rules").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM profile_stats").fetchone()[0] == 0
