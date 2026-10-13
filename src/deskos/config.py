from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppConfig:
    windowed: bool
    low_power: bool
    weather_location: str
    weather_latitude: float
    weather_longitude: float
    feed_urls: tuple[str, ...]

    @classmethod
    def from_environment(cls) -> AppConfig:
        feed_urls = tuple(
            value.strip()
            for value in os.environ.get(
                "DESKOS_FEED_URLS",
                "https://www.raspberrypi.com/news/feed/",
            ).split(",")
            if value.strip()
        )
        return cls(
            windowed=os.environ.get("DESKOS_WINDOWED", "0") == "1",
            low_power=os.environ.get("DESKOS_LOW_POWER", "0") == "1",
            weather_location=os.environ.get("DESKOS_WEATHER_LOCATION", "Taipei"),
            weather_latitude=float(os.environ.get("DESKOS_WEATHER_LAT", "25.0330")),
            weather_longitude=float(os.environ.get("DESKOS_WEATHER_LON", "121.5654")),
            feed_urls=feed_urls,
        )
