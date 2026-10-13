from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Protocol
from urllib.parse import urlparse


class SettingsStore(Protocol):
    def get_setting(self, key: str, default: Any = None) -> Any: ...

    def set_setting(self, key: str, value: Any) -> None: ...


@dataclass(frozen=True, slots=True)
class DeskOSSettings:
    weather_display_name: str = "Taipei"
    weather_latitude: float = 25.0330
    weather_longitude: float = 121.5654
    rss_urls: tuple[str, ...] = ("https://www.raspberrypi.com/news/feed/",)
    focus_minutes: int = 25
    rest_minutes: int = 5
    use_24_hour_time: bool = True
    low_power_3d: bool = False

    def validated(self) -> DeskOSSettings:
        name = self.weather_display_name.strip()
        if not name:
            raise ValueError("weather display name must not be empty")
        latitude = float(self.weather_latitude)
        longitude = float(self.weather_longitude)
        if not -90 <= latitude <= 90:
            raise ValueError("weather latitude must be between -90 and 90")
        if not -180 <= longitude <= 180:
            raise ValueError("weather longitude must be between -180 and 180")
        urls = tuple(url.strip() for url in self.rss_urls if url.strip())
        if not urls:
            raise ValueError("at least one RSS URL is required")
        if any(urlparse(url).scheme not in {"http", "https"} for url in urls):
            raise ValueError("RSS URLs must use http or https")
        focus = int(self.focus_minutes)
        rest = int(self.rest_minutes)
        if not 1 <= focus <= 180:
            raise ValueError("focus duration must be between 1 and 180 minutes")
        if not 1 <= rest <= 60:
            raise ValueError("rest duration must be between 1 and 60 minutes")
        return replace(
            self,
            weather_display_name=name,
            weather_latitude=latitude,
            weather_longitude=longitude,
            rss_urls=urls,
            focus_minutes=focus,
            rest_minutes=rest,
            use_24_hour_time=bool(self.use_24_hour_time),
            low_power_3d=bool(self.low_power_3d),
        )


class SettingsRepository:
    STORAGE_KEY = "deskos.settings"

    def __init__(self, store: SettingsStore) -> None:
        self._store = store

    def load(self) -> DeskOSSettings:
        defaults = DeskOSSettings()
        value = self._store.get_setting(self.STORAGE_KEY, None)
        if value is None:
            self.save(defaults)
            return defaults
        if not isinstance(value, dict):
            return defaults
        try:
            return DeskOSSettings(
                weather_display_name=str(
                    value.get("weather_display_name", defaults.weather_display_name)
                ),
                weather_latitude=float(value.get("weather_latitude", defaults.weather_latitude)),
                weather_longitude=float(value.get("weather_longitude", defaults.weather_longitude)),
                rss_urls=tuple(value.get("rss_urls", defaults.rss_urls)),
                focus_minutes=int(value.get("focus_minutes", defaults.focus_minutes)),
                rest_minutes=int(value.get("rest_minutes", defaults.rest_minutes)),
                use_24_hour_time=bool(value.get("use_24_hour_time", defaults.use_24_hour_time)),
                low_power_3d=bool(value.get("low_power_3d", defaults.low_power_3d)),
            ).validated()
        except (TypeError, ValueError):
            return defaults

    def save(self, settings: DeskOSSettings) -> DeskOSSettings:
        validated = settings.validated()
        self._store.set_setting(
            self.STORAGE_KEY,
            {
                "weather_display_name": validated.weather_display_name,
                "weather_latitude": validated.weather_latitude,
                "weather_longitude": validated.weather_longitude,
                "rss_urls": list(validated.rss_urls),
                "focus_minutes": validated.focus_minutes,
                "rest_minutes": validated.rest_minutes,
                "use_24_hour_time": validated.use_24_hour_time,
                "low_power_3d": validated.low_power_3d,
            },
        )
        return validated
