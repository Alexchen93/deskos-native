from __future__ import annotations

import json
import threading
from datetime import UTC, datetime

from deskos.core.models import Freshness
from deskos.services.storage import SQLiteRepository
from deskos.services.weather import OpenMeteoWeatherService


class Response:
    def __init__(self, payload: dict) -> None:
        self._payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size: int) -> bytes:
        return self._payload[:size]


def test_refresh_passes_timeout_and_caches_last_good_snapshot(tmp_path) -> None:
    calls = []

    def opener(url, *, timeout):
        calls.append((url, timeout))
        return Response(
            {
                "current": {
                    "temperature_2m": 22.5,
                    "apparent_temperature": 23.0,
                    "precipitation_probability": 10,
                    "weather_code": 2,
                }
            }
        )

    repository = SQLiteRepository(tmp_path / "deskos.sqlite3")
    now = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
    service = OpenMeteoWeatherService(
        repository,
        latitude=25.03,
        longitude=121.56,
        location="Taipei",
        timeout_seconds=3.5,
        opener=opener,
        clock=lambda: now,
    )

    snapshot = service.refresh()
    assert snapshot.freshness is Freshness.FRESH
    assert snapshot.temperature_c == 22.5
    assert calls[0][1] == 3.5
    assert "current=" in calls[0][0]

    restored = OpenMeteoWeatherService(
        repository,
        latitude=25.03,
        longitude=121.56,
        location="Taipei",
        opener=opener,
    )
    assert restored.latest().freshness is Freshness.STALE
    assert restored.latest().temperature_c == 22.5


def test_failure_returns_stale_cache_and_async_callback(tmp_path) -> None:
    repository = SQLiteRepository(tmp_path / "deskos.sqlite3")
    good = OpenMeteoWeatherService(
        repository,
        latitude=1,
        longitude=2,
        location="Test",
        opener=lambda *args, **kwargs: Response(
            {"current": {"temperature_2m": 20, "weather_code": 1}}
        ),
    )
    good.refresh()

    def failing(*args, **kwargs):
        raise TimeoutError("request timed out")

    service = OpenMeteoWeatherService(
        repository,
        latitude=1,
        longitude=2,
        location="Test",
        opener=failing,
    )
    finished = threading.Event()
    received = []

    service.refresh_async(lambda snapshot: (received.append(snapshot), finished.set()))

    assert finished.wait(1)
    assert received[0].freshness is Freshness.STALE
    assert received[0].temperature_c == 20
    assert "timed out" in received[0].error
