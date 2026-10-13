from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Freshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class TelemetrySnapshot:
    observed_at: datetime
    freshness: Freshness
    hostname: str
    cpu_percent: float | None
    memory_percent: float | None
    memory_used_bytes: int | None
    memory_total_bytes: int | None
    cpu_temp_c: float | None
    disk_percent: float | None
    disk_used_bytes: int | None
    disk_total_bytes: int | None
    rx_bytes_per_second: float | None
    tx_bytes_per_second: float | None
    uptime_seconds: float | None
    fan_target_percent: float | None = None
    fan_source: str = "unavailable"


@dataclass(frozen=True, slots=True)
class WeatherSnapshot:
    observed_at: datetime
    freshness: Freshness
    location: str
    temperature_c: float | None
    apparent_temperature_c: float | None
    precipitation_probability: float | None
    weather_code: int | None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class FeedItem:
    title: str
    source: str
    url: str
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class FocusState:
    mode: str
    running: bool
    remaining_seconds: int
    completed_sessions: int
