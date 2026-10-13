from __future__ import annotations

import math
import socket
import threading
import time
from collections import deque
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil

from deskos.core.models import Freshness, TelemetrySnapshot


class PsutilTelemetryCollector:
    """Collect process-wide system telemetry without writing samples to storage."""

    def __init__(
        self,
        *,
        interval_seconds: float = 2.0,
        history_minutes: float = 30.0,
        clock: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
        psutil_module: Any = psutil,
        thermal_root: str | Path = "/sys/class/thermal",
    ) -> None:
        if interval_seconds <= 0 or history_minutes <= 0:
            raise ValueError("interval_seconds and history_minutes must be positive")
        capacity = max(1, math.ceil(history_minutes * 60 / interval_seconds))
        self._interval = interval_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        self._monotonic = monotonic or time.monotonic
        self._psutil = psutil_module
        self._thermal_root = Path(thermal_root)
        self._history: deque[TelemetrySnapshot] = deque(maxlen=capacity)
        self._subscribers: list[Callable[[TelemetrySnapshot], None]] = []
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._previous_network: tuple[float, int, int] | None = None

    @property
    def interval_seconds(self) -> float:
        return self._interval

    @property
    def history_capacity(self) -> int:
        return self._history.maxlen or 0

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="deskos-telemetry",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float | None = None) -> None:
        with self._lock:
            thread = self._thread
            self._stop_event.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
        with self._lock:
            if self._thread is thread and (thread is None or not thread.is_alive()):
                self._thread = None

    def collect_once(self) -> TelemetrySnapshot:
        observed_at = self._aware_now()
        values: dict[str, Any] = {
            "cpu_percent": None,
            "memory_percent": None,
            "memory_used_bytes": None,
            "memory_total_bytes": None,
            "disk_percent": None,
            "disk_used_bytes": None,
            "disk_total_bytes": None,
            "uptime_seconds": None,
        }
        failures = 0

        try:
            values["cpu_percent"] = float(self._psutil.cpu_percent(interval=None))
        except (AttributeError, OSError, RuntimeError):
            failures += 1
        try:
            memory = self._psutil.virtual_memory()
            values.update(
                memory_percent=float(memory.percent),
                memory_used_bytes=int(memory.used),
                memory_total_bytes=int(memory.total),
            )
        except (AttributeError, OSError, RuntimeError):
            failures += 1
        try:
            disk = self._psutil.disk_usage("/")
            values.update(
                disk_percent=float(disk.percent),
                disk_used_bytes=int(disk.used),
                disk_total_bytes=int(disk.total),
            )
        except (AttributeError, OSError, RuntimeError):
            failures += 1
        try:
            values["uptime_seconds"] = max(
                0.0, observed_at.timestamp() - float(self._psutil.boot_time())
            )
        except (AttributeError, OSError, RuntimeError, ValueError):
            failures += 1

        rx_rate, tx_rate = self._network_rates()
        cpu_temp = discover_cpu_temperature(self._psutil, self._thermal_root)
        snapshot = TelemetrySnapshot(
            observed_at=observed_at,
            freshness=Freshness.ERROR if failures == 4 else Freshness.FRESH,
            hostname=socket.gethostname(),
            cpu_percent=values["cpu_percent"],
            memory_percent=values["memory_percent"],
            memory_used_bytes=values["memory_used_bytes"],
            memory_total_bytes=values["memory_total_bytes"],
            cpu_temp_c=cpu_temp,
            disk_percent=values["disk_percent"],
            disk_used_bytes=values["disk_used_bytes"],
            disk_total_bytes=values["disk_total_bytes"],
            rx_bytes_per_second=rx_rate,
            tx_bytes_per_second=tx_rate,
            uptime_seconds=values["uptime_seconds"],
        )
        with self._lock:
            self._history.append(snapshot)
            subscribers = tuple(self._subscribers)
        for callback in subscribers:
            try:
                callback(snapshot)
            except Exception:
                continue
        return snapshot

    def latest(self) -> TelemetrySnapshot:
        with self._lock:
            if self._history:
                return self._history[-1]
        return self.collect_once()

    def history(self) -> Sequence[TelemetrySnapshot]:
        with self._lock:
            return tuple(self._history)

    def subscribe(self, callback: Callable[[TelemetrySnapshot], None]) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(callback)
        removed = False

        def unsubscribe() -> None:
            nonlocal removed
            with self._lock:
                if not removed:
                    removed = True
                    try:
                        self._subscribers.remove(callback)
                    except ValueError:
                        pass

        return unsubscribe

    def _run(self) -> None:
        while not self._stop_event.is_set():
            started = self._monotonic()
            self.collect_once()
            elapsed = max(0.0, self._monotonic() - started)
            self._stop_event.wait(max(0.0, self._interval - elapsed))

    def _network_rates(self) -> tuple[float | None, float | None]:
        try:
            counters = self._psutil.net_io_counters()
            current = (self._monotonic(), int(counters.bytes_recv), int(counters.bytes_sent))
        except (AttributeError, OSError, RuntimeError):
            return None, None
        previous = self._previous_network
        self._previous_network = current
        if previous is None:
            return None, None
        elapsed = current[0] - previous[0]
        if elapsed <= 0:
            return None, None
        return (
            max(0.0, (current[1] - previous[1]) / elapsed),
            max(0.0, (current[2] - previous[2]) / elapsed),
        )

    def _aware_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def discover_cpu_temperature(
    psutil_module: Any = psutil,
    thermal_root: str | Path = "/sys/class/thermal",
) -> float | None:
    """Return a real Linux CPU temperature or None when no credible sensor exists."""
    preferred_groups = ("cpu_thermal", "coretemp", "k10temp", "zenpower", "acpitz")
    try:
        groups = psutil_module.sensors_temperatures(fahrenheit=False) or {}
    except (AttributeError, OSError, RuntimeError, NotImplementedError):
        groups = {}

    ordered_names = [name for name in preferred_groups if name in groups]
    ordered_names.extend(name for name in groups if name not in ordered_names)
    for group_name in ordered_names:
        readings = groups.get(group_name) or ()
        label_tokens = ("cpu", "core", "package", "soc")
        preferred = [
            reading
            for reading in readings
            if any(token in str(getattr(reading, "label", "")).lower() for token in label_tokens)
        ]
        candidates = preferred or (list(readings) if group_name in preferred_groups else [])
        for reading in candidates:
            value = _valid_temperature(getattr(reading, "current", None))
            if value is not None:
                return value

    root = Path(thermal_root)
    try:
        zones = sorted(root.glob("thermal_zone*"))
    except OSError:
        return None
    for zone in zones:
        try:
            sensor_type = (zone / "type").read_text(encoding="utf-8").strip().lower()
            cpu_tokens = ("cpu", "soc", "core", "package", "x86_pkg")
            if not any(token in sensor_type for token in cpu_tokens):
                continue
            raw = float((zone / "temp").read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
        if abs(raw) >= 1000:
            raw /= 1000.0
        value = _valid_temperature(raw)
        if value is not None:
            return value
    return None


def _valid_temperature(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed < -20.0 or parsed > 150.0:
        return None
    return parsed
