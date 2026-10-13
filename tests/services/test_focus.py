from __future__ import annotations

from datetime import UTC, datetime, timedelta

from deskos.services.focus import FocusTimer
from deskos.services.storage import SQLiteRepository


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


def test_timer_uses_deadline_and_restores_running_state(tmp_path) -> None:
    clock = MutableClock(datetime(2026, 10, 12, 12, 0, tzinfo=UTC))
    repository = SQLiteRepository(tmp_path / "deskos.sqlite3")
    timer = FocusTimer(repository, duration_seconds=120, clock=clock)

    assert timer.start().running is True
    clock.advance(31)
    assert timer.state().remaining_seconds == 89

    restored = FocusTimer(repository, duration_seconds=120, clock=clock)
    assert restored.state().running is True
    assert restored.state().remaining_seconds == 89


def test_pause_reset_and_completion_are_persisted(tmp_path) -> None:
    clock = MutableClock(datetime(2026, 10, 12, 12, 0, tzinfo=UTC))
    repository = SQLiteRepository(tmp_path / "deskos.sqlite3")
    timer = FocusTimer(repository, duration_seconds=10, clock=clock)

    timer.start()
    clock.advance(4)
    paused = timer.pause()
    assert paused.running is False
    assert paused.remaining_seconds == 6

    clock.advance(100)
    assert timer.state().remaining_seconds == 6
    timer.start()
    clock.advance(6)
    completed = timer.state()
    assert completed.running is False
    assert completed.remaining_seconds == 0
    assert completed.completed_sessions == 1

    restored = FocusTimer(repository, duration_seconds=10, clock=clock)
    assert restored.state() == completed
    assert restored.reset().remaining_seconds == 10
