"""SQLite-backed application settings."""

import sqlite3
from pathlib import Path


class SettingsStore:
    """Persist small application preferences in a local SQLite database."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.database_path)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT (
                        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                    )
                )
                """
            )

    def get(self, key: str, default: str | None = None) -> str | None:
        """Return a stored value, or ``default`` when the key is absent."""
        row = self._connection.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        ).fetchone()
        return default if row is None else str(row[0])

    def set(self, key: str, value: str) -> None:
        """Insert or update a setting atomically."""
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO app_settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                """,
                (key, value),
            )

    def close(self) -> None:
        """Close the database connection."""
        self._connection.close()
