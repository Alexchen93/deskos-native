# ruff: noqa: E402
from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from urllib.parse import urlparse

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from deskos.config import AppConfig
from deskos.core.models import FeedItem, TelemetrySnapshot, WeatherSnapshot
from deskos.paths import DATABASE_PATH, ensure_data_dir
from deskos.services import (
    FeedSource,
    FocusTimer,
    OpenMeteoWeatherService,
    PsutilTelemetryCollector,
    RssAtomFeedService,
    SQLiteRepository,
)
from deskos.ui.window import DeskOSWindow


class DeskOSApplication(Gtk.Application):
    """Own the native window and all local service lifecycles."""

    WEATHER_REFRESH_SECONDS = 30 * 60
    FEED_REFRESH_SECONDS = 30 * 60

    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__(
            application_id="uk.priveate.DeskOS",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.config = config or AppConfig.from_environment()
        ensure_data_dir()
        self.repository = SQLiteRepository(DATABASE_PATH)
        self.telemetry = PsutilTelemetryCollector()
        self.focus = FocusTimer(self.repository)
        self.weather = OpenMeteoWeatherService(
            self.repository,
            latitude=self.config.weather_latitude,
            longitude=self.config.weather_longitude,
            location=self.config.weather_location,
        )
        sources = tuple(FeedSource(_source_name(url), url) for url in self.config.feed_urls)
        self.feeds = RssAtomFeedService(sources, self.repository)
        self.window: DeskOSWindow | None = None
        self._unsubscribe_telemetry: Callable[[], None] | None = None
        self._timeout_ids: list[int] = []
        self.connect("activate", self._on_activate)
        self.connect("shutdown", self._on_shutdown)

    def _on_activate(self, _application: Gtk.Application) -> None:
        if self.window is None:
            self.window = DeskOSWindow(
                self,
                low_power=self.config.low_power,
                on_focus_start=self._focus_start,
                on_focus_pause=self._focus_pause,
                on_focus_reset=self._focus_reset,
            )
            if self.config.windowed:
                self.window.set_default_size(800, 480)
            else:
                # Labwc keeps a non-resizable GTK window at its requested size
                # even after a fullscreen request. Allow resizing and repeat the
                # request after mapping so the Pi's full 1024×600 output is used.
                self.window.set_resizable(True)
                self.window.set_decorated(False)
                self.window.fullscreen()
            start_page = os.environ.get("DESKOS_START_PAGE")
            if start_page:
                self.window.navigate(start_page)
            self._start_services()
        self.window.present()
        if not self.config.windowed:
            GLib.idle_add(self._ensure_fullscreen)

    def _ensure_fullscreen(self) -> bool:
        if self.window is not None:
            self.window.fullscreen()
        return False

    def _start_services(self) -> None:
        assert self.window is not None
        self.window.update_focus(self.focus.state())
        cached_weather = self.weather.latest()
        if cached_weather is not None:
            self.window.update_weather(cached_weather)
        cached_feed = self.feeds.latest()
        if cached_feed:
            self.window.update_feed(cached_feed)

        self._unsubscribe_telemetry = self.telemetry.subscribe(self._telemetry_from_worker)
        self.telemetry.start()
        self._refresh_weather()
        self._refresh_feed()
        self._timeout_ids.extend(
            (
                GLib.timeout_add_seconds(1, self._tick_focus),
                GLib.timeout_add_seconds(self.WEATHER_REFRESH_SECONDS, self._refresh_weather),
                GLib.timeout_add_seconds(self.FEED_REFRESH_SECONDS, self._refresh_feed),
            )
        )

    def _telemetry_from_worker(self, snapshot: TelemetrySnapshot) -> None:
        GLib.idle_add(self._apply_telemetry, snapshot)

    def _apply_telemetry(self, snapshot: TelemetrySnapshot) -> bool:
        if self.window is not None:
            self.window.update_telemetry(snapshot)
        return False

    def _refresh_weather(self) -> bool:
        self.weather.refresh_async(self._weather_from_worker)
        return True

    def _weather_from_worker(self, snapshot: WeatherSnapshot) -> None:
        GLib.idle_add(self._apply_weather, snapshot)

    def _apply_weather(self, snapshot: WeatherSnapshot) -> bool:
        if self.window is not None:
            self.window.update_weather(snapshot)
        return False

    def _refresh_feed(self) -> bool:
        self.feeds.refresh_async(self._feed_from_worker)
        return True

    def _feed_from_worker(self, items: Sequence[FeedItem]) -> None:
        GLib.idle_add(self._apply_feed, tuple(items))

    def _apply_feed(self, items: Sequence[FeedItem]) -> bool:
        if self.window is not None:
            self.window.update_feed(items)
        return False

    def _tick_focus(self) -> bool:
        if self.window is not None:
            self.window.update_focus(self.focus.state())
        return True

    def _focus_start(self) -> None:
        if self.window is not None:
            self.window.update_focus(self.focus.start())

    def _focus_pause(self) -> None:
        if self.window is not None:
            self.window.update_focus(self.focus.pause())

    def _focus_reset(self) -> None:
        if self.window is not None:
            self.window.update_focus(self.focus.reset())

    def _on_shutdown(self, _application: Gtk.Application) -> None:
        if self._unsubscribe_telemetry is not None:
            self._unsubscribe_telemetry()
            self._unsubscribe_telemetry = None
        self.telemetry.stop(timeout=3)
        for timeout_id in self._timeout_ids:
            if timeout_id:
                GLib.source_remove(timeout_id)
        self._timeout_ids.clear()


def _source_name(url: str) -> str:
    hostname = urlparse(url).hostname or "Tech Feed"
    return hostname.removeprefix("www.")
