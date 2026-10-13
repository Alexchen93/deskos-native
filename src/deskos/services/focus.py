from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from deskos.core.models import FocusState


class SettingsStore(Protocol):
    def get_setting(self, key: str, default: Any = None) -> Any: ...

    def set_setting(self, key: str, value: Any) -> None: ...


class FocusTimer:
    """A wall-clock timer whose deadline is durable across views and restarts."""

    STORAGE_KEY = "focus.timer.state"

    def __init__(
        self,
        store: SettingsStore,
        *,
        duration_seconds: int = 25 * 60,
        mode: str = "focus",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        self._store = store
        self._duration_seconds = duration_seconds
        self._default_mode = mode
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.RLock()
        self._data = self._restore()

    def state(self) -> FocusState:
        with self._lock:
            self._settle_if_finished()
            return self._public_state()

    def start(self) -> FocusState:
        with self._lock:
            self._settle_if_finished()
            if not self._data["running"] and self._data["remaining_seconds"] > 0:
                now = self._now_epoch()
                self._data["running"] = True
                self._data["deadline"] = now + self._data["remaining_seconds"]
                self._save()
            return self._public_state()

    def pause(self) -> FocusState:
        with self._lock:
            self._settle_if_finished()
            if self._data["running"]:
                self._data["remaining_seconds"] = self._remaining_from_deadline()
                self._data["running"] = False
                self._data["deadline"] = None
                self._save()
            return self._public_state()

    def reset(self) -> FocusState:
        with self._lock:
            self._data.update(
                running=False,
                remaining_seconds=self._duration_seconds,
                deadline=None,
            )
            self._save()
            return self._public_state()

    def set_mode(self, mode: str, *, duration_seconds: int | None = None) -> FocusState:
        """Switch timer mode and reset it; useful for focus/break selection."""
        if not mode:
            raise ValueError("mode must not be empty")
        if duration_seconds is not None and duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        with self._lock:
            if duration_seconds is not None:
                self._duration_seconds = duration_seconds
            self._data.update(
                mode=mode,
                running=False,
                remaining_seconds=self._duration_seconds,
                deadline=None,
            )
            self._save()
            return self._public_state()

    def _restore(self) -> dict[str, Any]:
        fallback = {
            "mode": self._default_mode,
            "running": False,
            "remaining_seconds": self._duration_seconds,
            "completed_sessions": 0,
            "deadline": None,
        }
        try:
            stored = self._store.get_setting(self.STORAGE_KEY, None)
        except (KeyError, TypeError, ValueError):
            return fallback
        if not isinstance(stored, dict):
            return fallback
        try:
            restored = {
                "mode": str(stored.get("mode") or self._default_mode),
                "running": bool(stored.get("running", False)),
                "remaining_seconds": max(0, int(stored["remaining_seconds"])),
                "completed_sessions": max(0, int(stored.get("completed_sessions", 0))),
                "deadline": (
                    float(stored["deadline"]) if stored.get("deadline") is not None else None
                ),
            }
        except (KeyError, TypeError, ValueError):
            return fallback
        if restored["running"] and restored["deadline"] is None:
            restored["running"] = False
        return restored

    def _settle_if_finished(self) -> None:
        if not self._data["running"]:
            return
        remaining = self._remaining_from_deadline()
        if remaining > 0:
            return
        self._data["running"] = False
        self._data["remaining_seconds"] = 0
        self._data["deadline"] = None
        if self._data["mode"] == "focus":
            self._data["completed_sessions"] += 1
        self._save()

    def _remaining_from_deadline(self) -> int:
        deadline = self._data["deadline"]
        if deadline is None:
            return int(self._data["remaining_seconds"])
        return max(0, int(deadline - self._now_epoch() + 0.999999))

    def _public_state(self) -> FocusState:
        remaining = (
            self._remaining_from_deadline()
            if self._data["running"]
            else int(self._data["remaining_seconds"])
        )
        return FocusState(
            mode=self._data["mode"],
            running=self._data["running"],
            remaining_seconds=remaining,
            completed_sessions=self._data["completed_sessions"],
        )

    def _save(self) -> None:
        self._store.set_setting(self.STORAGE_KEY, dict(self._data))

    def _now_epoch(self) -> float:
        value = self._clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.timestamp()
