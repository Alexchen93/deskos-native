from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CacheRecord:
    key: str
    value: Any
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class EventRecord:
    id: int
    kind: str
    payload: Any
    occurred_at: datetime


class SQLiteRepository:
    """Small thread-safe repository for durable, low-frequency application data."""

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        if self._path != ":memory:":
            Path(self._path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize_schema(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_events_kind_time
                    ON events(kind, occurred_at DESC);
                """
            )

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT value_json FROM settings WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return default
        return json.loads(row["value_json"])

    def set_setting(self, key: str, value: Any) -> None:
        encoded = _encode(value)
        updated_at = _format_datetime(datetime.now(UTC))
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO settings(key, value_json, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (key, encoded, updated_at),
            )

    def delete_setting(self, key: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM settings WHERE key = ?", (key,))

    def get_cache(self, key: str) -> CacheRecord | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT key, value_json, updated_at FROM cache WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        return CacheRecord(
            key=row["key"],
            value=json.loads(row["value_json"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )

    def set_cache(
        self,
        key: str,
        value: Any,
        *,
        updated_at: datetime | None = None,
    ) -> None:
        timestamp = updated_at or datetime.now(UTC)
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO cache(key, value_json, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (key, _encode(value), _format_datetime(timestamp)),
            )

    def delete_cache(self, key: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM cache WHERE key = ?", (key,))

    def append_event(
        self,
        kind: str,
        payload: Any,
        *,
        occurred_at: datetime | None = None,
    ) -> int:
        timestamp = occurred_at or datetime.now(UTC)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO events(kind, payload_json, occurred_at) VALUES (?, ?, ?)",
                (kind, _encode(payload), _format_datetime(timestamp)),
            )
            return int(cursor.lastrowid)

    def list_events(self, *, kind: str | None = None, limit: int = 100) -> list[EventRecord]:
        if limit < 1:
            return []
        query = "SELECT id, kind, payload_json, occurred_at FROM events"
        parameters: list[Any] = []
        if kind is not None:
            query += " WHERE kind = ?"
            parameters.append(kind)
        query += " ORDER BY occurred_at DESC, id DESC LIMIT ?"
        parameters.append(limit)
        with self._lock, self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [
            EventRecord(
                id=row["id"],
                kind=row["kind"],
                payload=json.loads(row["payload_json"]),
                occurred_at=_parse_datetime(row["occurred_at"]),
            )
            for row in rows
        ]


def _encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
