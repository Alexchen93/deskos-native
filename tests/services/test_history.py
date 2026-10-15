from __future__ import annotations

from datetime import UTC, datetime, timedelta

from deskos.core.models import Freshness, TelemetrySnapshot, WeatherSnapshot
from deskos.services.history import HistorySample, MetricHistory, downsample_history
from deskos.services.storage import SQLiteRepository


def _telemetry(observed_at: datetime, *, cpu_percent: float | None, cpu_temp_c: float | None):
    return TelemetrySnapshot(
        observed_at=observed_at,
        freshness=Freshness.FRESH,
        hostname="deskpi",
        cpu_percent=cpu_percent,
        memory_percent=None,
        memory_used_bytes=None,
        memory_total_bytes=None,
        cpu_temp_c=cpu_temp_c,
        disk_percent=None,
        disk_used_bytes=None,
        disk_total_bytes=None,
        rx_bytes_per_second=None,
        tx_bytes_per_second=None,
        uptime_seconds=None,
    )


def _weather(observed_at: datetime, temperature_c: float | None) -> WeatherSnapshot:
    return WeatherSnapshot(
        observed_at=observed_at,
        freshness=Freshness.FRESH,
        location="Taipei",
        temperature_c=temperature_c,
        apparent_temperature_c=None,
        precipitation_probability=None,
        weather_code=None,
    )


def test_metric_history_samples_cpu_at_a_low_frequency_and_orders_charts_oldest_first(
    tmp_path,
) -> None:
    history = MetricHistory(SQLiteRepository(tmp_path / "deskos.sqlite3"))
    started = datetime(2026, 10, 14, 12, tzinfo=UTC)

    assert history.record_telemetry(_telemetry(started, cpu_percent=20, cpu_temp_c=45))
    assert not history.record_telemetry(
        _telemetry(started + timedelta(seconds=30), cpu_percent=40, cpu_temp_c=47)
    )
    assert history.record_telemetry(
        _telemetry(started + timedelta(minutes=1), cpu_percent=60, cpu_temp_c=49)
    )
    assert history.record_telemetry(
        _telemetry(started + timedelta(minutes=2), cpu_percent=80, cpu_temp_c=51)
    )

    assert [sample.value for sample in history.cpu_usage()] == [20.0, 60.0, 80.0]
    assert [sample.value for sample in history.cpu_temperatures()] == [45.0, 49.0, 51.0]
    assert [sample.observed_at for sample in history.cpu_usage()] == [
        started,
        started + timedelta(minutes=1),
        started + timedelta(minutes=2),
    ]


def test_metric_history_samples_weather_and_ignores_missing_temperature(tmp_path) -> None:
    history = MetricHistory(SQLiteRepository(tmp_path / "deskos.sqlite3"))
    started = datetime(2026, 10, 14, 12, tzinfo=UTC)

    assert not history.record_weather(_weather(started, None))
    assert history.record_weather(_weather(started, 24.5))
    assert not history.record_weather(_weather(started + timedelta(minutes=10), 25.0))
    assert history.record_weather(_weather(started + timedelta(minutes=20), 25.5))

    assert [sample.value for sample in history.weather_temperatures()] == [24.5, 25.5]


def test_downsample_history_keeps_first_last_and_chronological_order() -> None:
    started = datetime(2026, 10, 14, 12, tzinfo=UTC)
    source = tuple(
        HistorySample(started + timedelta(minutes=index), float(index)) for index in range(9)
    )

    sampled = downsample_history(source, 3)

    assert [sample.value for sample in sampled] == [0.0, 4.0, 8.0]
    assert downsample_history(source, 1) == (source[-1],)
