"""Low-frequency, durable metric history built on DeskOS event storage."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from deskos.core.models import TelemetrySnapshot, WeatherSnapshot


@dataclass(frozen=True, slots=True)
class HistorySample:
    """One numeric point suitable for a compact chart."""

    observed_at: datetime
    value: float


class EventStore(Protocol):
    def append_event(
        self,
        kind: str,
        payload: Any,
        *,
        occurred_at: datetime | None = None,
    ) -> int: ...

    def list_events(self, *, kind: str | None = None, limit: int = 100) -> Sequence[Any]: ...


class MetricHistory:
    """Persist sparse metric samples and return chart-sized, oldest-first series."""

    WEATHER_TEMPERATURE_KIND = "metrics.weather_temperature"
    DEVICE_CPU_KIND = "metrics.device_cpu"
    WEATHER_SAMPLE_INTERVAL = timedelta(minutes=20)
    DEVICE_SAMPLE_INTERVAL = timedelta(minutes=1)
    CHART_POINTS = 48
    EVENT_SCAN_LIMIT = CHART_POINTS * 4

    def __init__(self, store: EventStore) -> None:
        self._store = store
        self._last_sample_at: dict[str, datetime] = {}

    def record_weather(self, snapshot: WeatherSnapshot) -> bool:
        """Store one temperature reading at most every weather sampling interval."""
        value = _finite_float(snapshot.temperature_c)
        if value is None or not self._should_sample(
            self.WEATHER_TEMPERATURE_KIND, snapshot.observed_at
        ):
            return False
        self._store.append_event(
            self.WEATHER_TEMPERATURE_KIND,
            {"temperature_c": value},
            occurred_at=snapshot.observed_at,
        )
        self._last_sample_at[self.WEATHER_TEMPERATURE_KIND] = _aware(snapshot.observed_at)
        return True

    def record_telemetry(self, snapshot: TelemetrySnapshot) -> bool:
        """Store CPU temperature and usage together, avoiding collector-rate writes."""
        temperature_c = _finite_float(snapshot.cpu_temp_c)
        cpu_percent = _finite_float(snapshot.cpu_percent)
        if (
            temperature_c is None
            and cpu_percent is None
            or not self._should_sample(self.DEVICE_CPU_KIND, snapshot.observed_at)
        ):
            return False
        self._store.append_event(
            self.DEVICE_CPU_KIND,
            {"cpu_temp_c": temperature_c, "cpu_percent": cpu_percent},
            occurred_at=snapshot.observed_at,
        )
        self._last_sample_at[self.DEVICE_CPU_KIND] = _aware(snapshot.observed_at)
        return True

    def weather_temperatures(self) -> tuple[HistorySample, ...]:
        return self._series(self.WEATHER_TEMPERATURE_KIND, "temperature_c")

    def cpu_temperatures(self) -> tuple[HistorySample, ...]:
        return self._series(self.DEVICE_CPU_KIND, "cpu_temp_c")

    def cpu_usage(self) -> tuple[HistorySample, ...]:
        return self._series(self.DEVICE_CPU_KIND, "cpu_percent")

    def _should_sample(self, kind: str, observed_at: datetime) -> bool:
        current = _aware(observed_at)
        previous = self._last_sample_at.get(kind)
        if previous is None:
            records = self._store.list_events(kind=kind, limit=1)
            if records:
                previous = _aware(records[0].occurred_at)
            self._last_sample_at[kind] = previous or current - self._interval_for(kind)
        return current - self._last_sample_at[kind] >= self._interval_for(kind)

    def _series(self, kind: str, key: str) -> tuple[HistorySample, ...]:
        samples: list[HistorySample] = []
        for record in reversed(self._store.list_events(kind=kind, limit=self.EVENT_SCAN_LIMIT)):
            payload = getattr(record, "payload", None)
            value = _finite_float(payload.get(key) if isinstance(payload, dict) else None)
            if value is not None:
                samples.append(HistorySample(_aware(record.occurred_at), value))
        return tuple(downsample_history(samples, self.CHART_POINTS))

    def _interval_for(self, kind: str) -> timedelta:
        return (
            self.WEATHER_SAMPLE_INTERVAL
            if kind == self.WEATHER_TEMPERATURE_KIND
            else self.DEVICE_SAMPLE_INTERVAL
        )


def downsample_history(
    samples: Sequence[HistorySample],
    max_points: int,
) -> tuple[HistorySample, ...]:
    """Retain evenly distributed points, including both chronological endpoints."""
    if max_points < 1:
        raise ValueError("max_points must be positive")
    if len(samples) <= max_points:
        return tuple(samples)
    if max_points == 1:
        return (samples[-1],)
    last_index = len(samples) - 1
    return tuple(
        samples[round(index * last_index / (max_points - 1))] for index in range(max_points)
    )


def _finite_float(value: object) -> float | None:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed and abs(parsed) != float("inf") else None


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
