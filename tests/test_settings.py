from __future__ import annotations

from typing import Any

import pytest

from deskos.settings import DeskOSSettings, SettingsRepository


class _Store:
    def __init__(self, value: Any = None) -> None:
        self.value = value
        self.writes: list[tuple[str, Any]] = []

    def get_setting(self, _key: str, default: Any = None) -> Any:
        return default if self.value is None else self.value

    def set_setting(self, key: str, value: Any) -> None:
        self.value = value
        self.writes.append((key, value))


def test_settings_first_load_persists_defaults_and_next_load_is_durable() -> None:
    store = _Store()
    repository = SettingsRepository(store)

    defaults = repository.load()
    loaded_again = SettingsRepository(store).load()

    assert defaults == DeskOSSettings()
    assert loaded_again == defaults
    assert store.writes == [
        (
            SettingsRepository.STORAGE_KEY,
            {
                "weather_display_name": "Taipei",
                "weather_latitude": 25.033,
                "weather_longitude": 121.5654,
                "rss_urls": ["https://www.raspberrypi.com/news/feed/"],
                "focus_minutes": 25,
                "rest_minutes": 5,
                "use_24_hour_time": True,
                "low_power_3d": False,
            },
        )
    ]


def test_settings_save_normalizes_values_and_round_trips() -> None:
    store = _Store()
    repository = SettingsRepository(store)
    settings = DeskOSSettings(
        weather_display_name="  Lab  ",
        weather_latitude="24.5",  # type: ignore[arg-type]
        weather_longitude="120.5",  # type: ignore[arg-type]
        rss_urls=(" https://example.test/feed ", "https://example.test/second"),
        focus_minutes="30",  # type: ignore[arg-type]
        rest_minutes="10",  # type: ignore[arg-type]
        use_24_hour_time=1,  # type: ignore[arg-type]
    )

    saved = repository.save(settings)

    assert saved == DeskOSSettings(
        weather_display_name="Lab",
        weather_latitude=24.5,
        weather_longitude=120.5,
        rss_urls=("https://example.test/feed", "https://example.test/second"),
        focus_minutes=30,
        rest_minutes=10,
        use_24_hour_time=True,
    )
    assert SettingsRepository(store).load() == saved


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"weather_display_name": " "}, "weather display name"),
        ({"weather_latitude": 91}, "weather latitude"),
        ({"weather_longitude": 181}, "weather longitude"),
        ({"rss_urls": ("ftp://example.test/feed",)}, "RSS URLs"),
        ({"rss_urls": ()}, "at least one RSS URL"),
        ({"focus_minutes": 0}, "focus duration"),
        ({"rest_minutes": 61}, "rest duration"),
    ],
)
def test_settings_validation_rejects_invalid_values(
    changes: dict[str, object], message: str
) -> None:
    values = {
        "weather_display_name": "Taichung",
        "weather_latitude": 24.1477,
        "weather_longitude": 120.6736,
        "rss_urls": ("https://www.raspberrypi.com/news/feed/",),
        "focus_minutes": 25,
        "rest_minutes": 5,
        "use_24_hour_time": True,
        "low_power_3d": False,
    }
    values.update(changes)

    with pytest.raises(ValueError, match=message):
        DeskOSSettings(**values).validated()  # type: ignore[arg-type]


def test_invalid_persisted_settings_fall_back_to_defaults() -> None:
    store = _Store({"rss_urls": ["file:///not-a-feed"], "focus_minutes": 0})

    assert SettingsRepository(store).load() == DeskOSSettings()
