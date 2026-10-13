from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlencode
from urllib.request import urlopen

from deskos.core.models import Freshness, WeatherSnapshot


class CacheStore(Protocol):
    def get_cache(self, key: str) -> Any: ...

    def set_cache(
        self,
        key: str,
        value: Any,
        *,
        updated_at: datetime | None = None,
    ) -> None: ...


class OpenMeteoWeatherService:
    API_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(
        self,
        store: CacheStore,
        *,
        latitude: float,
        longitude: float,
        location: str,
        timeout_seconds: float = 5.0,
        opener: Callable[..., Any] = urlopen,
        clock: Callable[[], datetime] | None = None,
        cache_key: str | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._store = store
        self._latitude = latitude
        self._longitude = longitude
        self._location = location
        self._timeout = timeout_seconds
        self._opener = opener
        self._clock = clock or (lambda: datetime.now(UTC))
        self._cache_key = cache_key or f"weather:{latitude:.4f}:{longitude:.4f}"
        self._lock = threading.RLock()
        self._latest = self._load_cached()

    def latest(self) -> WeatherSnapshot | None:
        with self._lock:
            return self._latest

    def refresh(self) -> WeatherSnapshot:
        try:
            payload = self._fetch_json()
            snapshot = self._snapshot_from_payload(payload)
        except Exception as error:
            with self._lock:
                cached = self._latest
            if cached is not None and cached.freshness in (Freshness.FRESH, Freshness.STALE):
                snapshot = WeatherSnapshot(
                    observed_at=cached.observed_at,
                    freshness=Freshness.STALE,
                    location=cached.location,
                    temperature_c=cached.temperature_c,
                    apparent_temperature_c=cached.apparent_temperature_c,
                    precipitation_probability=cached.precipitation_probability,
                    weather_code=cached.weather_code,
                    error=str(error),
                )
            else:
                snapshot = WeatherSnapshot(
                    observed_at=self._aware_now(),
                    freshness=Freshness.ERROR,
                    location=self._location,
                    temperature_c=None,
                    apparent_temperature_c=None,
                    precipitation_probability=None,
                    weather_code=None,
                    error=str(error),
                )
            with self._lock:
                self._latest = snapshot
            return snapshot

        with self._lock:
            self._latest = snapshot
        self._store.set_cache(
            self._cache_key,
            _serialize_snapshot(snapshot),
            updated_at=snapshot.observed_at,
        )
        return snapshot

    def refresh_async(self, callback: Callable[[WeatherSnapshot], None]) -> None:
        def worker() -> None:
            snapshot = self.refresh()
            try:
                callback(snapshot)
            except Exception:
                pass

        threading.Thread(target=worker, name="deskos-weather", daemon=True).start()

    def _fetch_json(self) -> dict[str, Any]:
        query = urlencode(
            {
                "latitude": self._latitude,
                "longitude": self._longitude,
                "current": (
                    "temperature_2m,apparent_temperature,precipitation_probability,weather_code"
                ),
                "timezone": "auto",
            }
        )
        response = self._opener(f"{self.API_URL}?{query}", timeout=self._timeout)
        with response:
            raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ValueError("weather response exceeded 1 MB")
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("weather response must be a JSON object")
        return value

    def _snapshot_from_payload(self, payload: dict[str, Any]) -> WeatherSnapshot:
        current = payload.get("current")
        if not isinstance(current, dict):
            raise ValueError("weather response is missing current conditions")
        return WeatherSnapshot(
            observed_at=self._aware_now(),
            freshness=Freshness.FRESH,
            location=self._location,
            temperature_c=_optional_float(current.get("temperature_2m")),
            apparent_temperature_c=_optional_float(current.get("apparent_temperature")),
            precipitation_probability=_optional_float(current.get("precipitation_probability")),
            weather_code=_optional_int(current.get("weather_code")),
        )

    def _load_cached(self) -> WeatherSnapshot | None:
        try:
            record = self._store.get_cache(self._cache_key)
            if record is None or not isinstance(record.value, dict):
                return None
            return _deserialize_snapshot(record.value, freshness=Freshness.STALE)
        except (AttributeError, KeyError, TypeError, ValueError):
            return None

    def _aware_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def _serialize_snapshot(snapshot: WeatherSnapshot) -> dict[str, Any]:
    return {
        "observed_at": snapshot.observed_at.isoformat(),
        "location": snapshot.location,
        "temperature_c": snapshot.temperature_c,
        "apparent_temperature_c": snapshot.apparent_temperature_c,
        "precipitation_probability": snapshot.precipitation_probability,
        "weather_code": snapshot.weather_code,
    }


def _deserialize_snapshot(value: dict[str, Any], *, freshness: Freshness) -> WeatherSnapshot:
    observed_at = datetime.fromisoformat(str(value["observed_at"]))
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    return WeatherSnapshot(
        observed_at=observed_at.astimezone(UTC),
        freshness=freshness,
        location=str(value["location"]),
        temperature_c=_optional_float(value.get("temperature_c")),
        apparent_temperature_c=_optional_float(value.get("apparent_temperature_c")),
        precipitation_probability=_optional_float(value.get("precipitation_probability")),
        weather_code=_optional_int(value.get("weather_code")),
    )


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)
