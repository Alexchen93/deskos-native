from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from deskos.core.models import Freshness
from deskos.services.telemetry import PsutilTelemetryCollector, discover_cpu_temperature


class FakePsutil:
    def __init__(self) -> None:
        self.network = [(100, 200), (300, 500), (500, 900)]

    def cpu_percent(self, interval=None):
        assert interval is None
        return 12.5

    def virtual_memory(self):
        return SimpleNamespace(percent=50.0, used=500, total=1000)

    def disk_usage(self, path):
        assert path == "/"
        return SimpleNamespace(percent=25.0, used=250, total=1000)

    def boot_time(self):
        return datetime(2026, 10, 12, 11, 0, tzinfo=UTC).timestamp()

    def net_io_counters(self):
        received, sent = self.network.pop(0)
        return SimpleNamespace(bytes_recv=received, bytes_sent=sent)

    def sensors_temperatures(self, fahrenheit=False):
        assert fahrenheit is False
        return {"coretemp": [SimpleNamespace(label="Package id 0", current=48.25)]}


class StepMonotonic:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        value = self.value
        self.value += 2.0
        return value


def test_collector_samples_rates_notifies_and_bounds_history() -> None:
    psutil = FakePsutil()
    collector = PsutilTelemetryCollector(
        interval_seconds=2,
        history_minutes=1 / 15,
        clock=lambda: datetime(2026, 10, 12, 12, 0, tzinfo=UTC),
        monotonic=StepMonotonic(),
        psutil_module=psutil,
    )
    seen = []
    unsubscribe = collector.subscribe(seen.append)

    first = collector.collect_once()
    second = collector.collect_once()
    unsubscribe()
    third = collector.collect_once()

    assert first.rx_bytes_per_second is None
    assert second.rx_bytes_per_second == 100.0
    assert second.tx_bytes_per_second == 150.0
    assert second.cpu_temp_c == 48.25
    assert second.freshness is Freshness.FRESH
    assert len(collector.history()) == collector.history_capacity == 2
    assert collector.latest() is third
    assert seen == [first, second]


def test_cpu_temperature_is_none_when_no_real_sensor_exists(tmp_path) -> None:
    class NoSensors:
        def sensors_temperatures(self, fahrenheit=False):
            return {}

    assert discover_cpu_temperature(NoSensors(), tmp_path) is None


def test_cpu_temperature_ignores_non_cpu_sensor_groups(tmp_path) -> None:
    class GpuOnly:
        def sensors_temperatures(self, fahrenheit=False):
            return {"amdgpu": [SimpleNamespace(label="edge", current=61.0)]}

    assert discover_cpu_temperature(GpuOnly(), tmp_path) is None


def test_cpu_temperature_reads_cpu_sysfs_zone(tmp_path) -> None:
    zone = tmp_path / "thermal_zone0"
    zone.mkdir()
    (zone / "type").write_text("cpu-thermal", encoding="utf-8")
    (zone / "temp").write_text("42375", encoding="utf-8")

    class NoSensors:
        def sensors_temperatures(self, fahrenheit=False):
            return {}

    assert discover_cpu_temperature(NoSensors(), tmp_path) == 42.375
