"""Profile model and SQLite-backed storage manager."""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProfileStats:
    """Statistics tracked during automation sessions."""

    experience_gained: int = 0
    deaths: int = 0
    loot_count: int = 0
    runtime_seconds: float = 0.0


@dataclass
class Profile:
    """Representation of a character profile and its automation settings."""

    id: int | None
    name: str
    character_class: str = "Novice"
    window_title: str = "Ragnarok"
    rules: dict[str, dict[str, str]] = field(default_factory=dict)
    stats: ProfileStats = field(default_factory=ProfileStats)


class ProfileStore:
    """Manages profile creation, settings rules, and statistics in SQLite."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.database_path)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self) -> None:
        with self._connection:
            # Enable Foreign Keys in case sqlite3 didn't apply it globally
            self._connection.execute("PRAGMA foreign_keys = ON")

            # 1. Profiles Table
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    character_class TEXT DEFAULT 'Novice',
                    window_title TEXT DEFAULT 'Ragnarok',
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                )
                """
            )

            # 2. Profile Rules Table
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS profile_rules (
                    profile_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    rule_key TEXT NOT NULL,
                    rule_value TEXT NOT NULL,
                    PRIMARY KEY (profile_id, category, rule_key),
                    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                )
                """
            )

            # 3. Profile Statistics Table
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS profile_stats (
                    profile_id INTEGER PRIMARY KEY,
                    experience_gained INTEGER DEFAULT 0,
                    deaths INTEGER DEFAULT 0,
                    loot_count INTEGER DEFAULT 0,
                    runtime_seconds REAL DEFAULT 0.0,
                    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                )
                """
            )

    def create_profile(
        self, name: str, character_class: str = "Novice", window_title: str = "Ragnarok"
    ) -> int:
        """Create a new character profile and initialize its statistics record."""
        with self._connection:
            cursor = self._connection.execute(
                """
                INSERT INTO profiles (name, character_class, window_title)
                VALUES (?, ?, ?)
                """,
                (name, character_class, window_title),
            )
            profile_id = cursor.lastrowid
            assert profile_id is not None

            # Initialize empty stats
            self._connection.execute(
                "INSERT INTO profile_stats (profile_id) VALUES (?)", (profile_id,)
            )
            return profile_id

    def get_profile(self, profile_id: int) -> Profile | None:
        """Fetch a complete profile by its ID, including rules and stats."""
        # 1. Fetch metadata
        meta_row = self._connection.execute(
            "SELECT id, name, character_class, window_title FROM profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()

        if not meta_row:
            return None

        # 2. Fetch stats
        stats_row = self._connection.execute(
            """
            SELECT experience_gained, deaths, loot_count, runtime_seconds
            FROM profile_stats WHERE profile_id = ?
            """,
            (profile_id,),
        ).fetchone()

        stats = (
            ProfileStats(
                experience_gained=stats_row[0],
                deaths=stats_row[1],
                loot_count=stats_row[2],
                runtime_seconds=stats_row[3],
            )
            if stats_row
            else ProfileStats()
        )

        # 3. Fetch rules
        rules: dict[str, dict[str, str]] = {}
        rules_cursor = self._connection.execute(
            "SELECT category, rule_key, rule_value FROM profile_rules WHERE profile_id = ?",
            (profile_id,),
        )
        for category, key, value in rules_cursor:
            if category not in rules:
                rules[category] = {}
            rules[category][key] = value

        return Profile(
            id=meta_row[0],
            name=meta_row[1],
            character_class=meta_row[2],
            window_title=meta_row[3],
            rules=rules,
            stats=stats,
        )

    def get_profile_by_name(self, name: str) -> Profile | None:
        """Fetch a complete profile by its unique name."""
        meta_row = self._connection.execute(
            "SELECT id FROM profiles WHERE name = ?", (name,)
        ).fetchone()
        if not meta_row:
            return None
        return self.get_profile(meta_row[0])

    def list_profiles(self) -> list[Profile]:
        """Return all profiles in the database."""
        cursor = self._connection.execute("SELECT id FROM profiles ORDER BY name")
        return [self.get_profile(row[0]) for row in cursor.fetchall() if self.get_profile(row[0])]

    def set_rule(self, profile_id: int, category: str, key: str, value: str) -> None:
        """Save or update an automation rule configuration key-value pair."""
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO profile_rules (profile_id, category, rule_key, rule_value)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(profile_id, category, rule_key) DO UPDATE SET
                    rule_value = excluded.rule_value
                """,
                (profile_id, category, key, value),
            )
            self._connection.execute(
                """
                UPDATE profiles
                SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
                """,
                (profile_id,),
            )

    def get_rules(self, profile_id: int, category: str) -> dict[str, str]:
        """Retrieve all rules configured under a specific category for a profile."""
        cursor = self._connection.execute(
            "SELECT rule_key, rule_value FROM profile_rules WHERE profile_id = ? AND category = ?",
            (profile_id, category),
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    def update_stats(
        self,
        profile_id: int,
        experience_gained: int,
        deaths: int,
        loot_count: int,
        runtime_seconds: float,
    ) -> None:
        """Update session tracking metrics for a profile."""
        with self._connection:
            self._connection.execute(
                """
                UPDATE profile_stats
                SET experience_gained = ?,
                    deaths = ?,
                    loot_count = ?,
                    runtime_seconds = ?,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE profile_id = ?
                """,
                (experience_gained, deaths, loot_count, runtime_seconds, profile_id),
            )

    def update_profile_window_title(self, profile_id: int, window_title: str) -> None:
        """Update the target window title for a character profile."""
        with self._connection:
            self._connection.execute(
                """
                UPDATE profiles
                SET window_title = ?,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
                """,
                (window_title, profile_id),
            )

    def delete_profile(self, profile_id: int) -> None:
        """Delete a profile and all its associated rules and stats (cascading)."""
        with self._connection:
            self._connection.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))

    def close(self) -> None:
        """Close the database connection."""
        self._connection.close()
