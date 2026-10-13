from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from deskos.services.storage import SQLiteRepository


def test_repository_initializes_schema_and_round_trips_data(tmp_path) -> None:
    path = tmp_path / "deskos.sqlite3"
    repository = SQLiteRepository(path)
    when = datetime(2026, 10, 12, 12, 30, tzinfo=UTC)

    repository.set_setting("units", {"temperature": "celsius"})
    repository.set_cache("weather:test", {"temperature": 21.5}, updated_at=when)
    event_id = repository.append_event("focus.completed", {"count": 3}, occurred_at=when)

    assert repository.get_setting("units") == {"temperature": "celsius"}
    assert repository.get_setting("missing", "fallback") == "fallback"
    cached = repository.get_cache("weather:test")
    assert cached is not None
    assert cached.value == {"temperature": 21.5}
    assert cached.updated_at == when
    events = repository.list_events(kind="focus.completed")
    assert [(event.id, event.payload, event.occurred_at) for event in events] == [
        (event_id, {"count": 3}, when)
    ]

    with sqlite3.connect(path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert {"settings", "cache", "events"}.issubset(tables)


def test_repository_creates_missing_parent_directory(tmp_path) -> None:
    path = tmp_path / "nested" / "data" / "deskos.sqlite3"
    repository = SQLiteRepository(path)
    repository.set_setting("ready", True)
    assert path.is_file()
    assert repository.get_setting("ready") is True


def test_repository_updates_and_deletes_values(tmp_path) -> None:
    repository = SQLiteRepository(tmp_path / "deskos.sqlite3")
    repository.set_setting("theme", "light")
    repository.set_setting("theme", "dark")
    repository.set_cache("example", [1])
    repository.set_cache("example", [2])

    assert repository.get_setting("theme") == "dark"
    assert repository.get_cache("example").value == [2]

    repository.delete_setting("theme")
    repository.delete_cache("example")
    assert repository.get_setting("theme") is None
    assert repository.get_cache("example") is None
