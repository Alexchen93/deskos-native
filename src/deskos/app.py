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
from deskos.paths import DATABASE_PATH, MODEL_PATH, MODEL_PREVIEW_PATH, ensure_data_dir
from deskos.plugins import PluginEvent, PluginManager, PluginRegistry
from deskos.plugins.builtin import builtin_plugin_specs
from deskos.services import (
    FeedSource,
    FocusTimer,
    OpenMeteoWeatherService,
    PsutilTelemetryCollector,
    RssAtomFeedService,
    SQLiteRepository,
)
from deskos.settings import DeskOSSettings, SettingsRepository
from deskos.ui.window import DeskOSWindow


class DeskOSApplication(Gtk.Application):
    """Own the native shell, plugin catalog, and nonblocking local services."""

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
        self.settings_repository = SettingsRepository(self.repository)
        self.settings = self.settings_repository.load()
        self.telemetry = PsutilTelemetryCollector()
        self.focus = FocusTimer(self.repository, duration_seconds=self.settings.focus_minutes * 60)
        self.weather: OpenMeteoWeatherService
        self.feeds: RssAtomFeedService
        self._service_revision = 0
        self._configure_network_services(self.settings)

        self.registry = PluginRegistry()
        for spec in builtin_plugin_specs(
            model_path=MODEL_PATH,
            preview_path=MODEL_PREVIEW_PATH,
            low_power=self.settings.low_power_3d,
            use_24_hour_time=self.settings.use_24_hour_time,
            focus_minutes=self.settings.focus_minutes,
            rest_minutes=self.settings.rest_minutes,
            on_focus_start=self._focus_start,
            on_focus_pause=self._focus_pause,
            on_focus_reset=self._focus_reset,
        ):
            self.registry.register(spec)
        built_in_ids = tuple(spec.metadata.id for spec in self.registry.all())
        self.registry.discover()
        self.plugins = PluginManager(
            self.registry,
            self.repository,
            default_installed_ids=built_in_ids,
        )

        self.window: DeskOSWindow | None = None
        self._unsubscribe_telemetry: Callable[[], None] | None = None
        self._timeout_ids: list[int] = []
        self.connect("activate", self._on_activate)
        self.connect("shutdown", self._on_shutdown)

    def _configure_network_services(self, settings: DeskOSSettings) -> None:
        self._service_revision += 1
        self.weather = OpenMeteoWeatherService(
            self.repository,
            latitude=settings.weather_latitude,
            longitude=settings.weather_longitude,
            location=settings.weather_display_name,
        )
        sources = tuple(FeedSource(_source_name(url), url) for url in settings.rss_urls)
        self.feeds = RssAtomFeedService(sources, self.repository)

    def _on_activate(self, _application: Gtk.Application) -> None:
        if self.window is None:
            self.window = DeskOSWindow(
                self,
                registry=self.registry,
                plugins=self.plugins,
                repository=self.repository,
                settings=self.settings,
                on_settings_save=self._save_settings,
            )
            if self.config.windowed:
                self.window.set_default_size(1024, 600)
            else:
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
        self._dispatch("settings", self.settings)
        self._dispatch("focus", self.focus.state())
        cached_weather = self.weather.latest()
        if cached_weather is not None:
            self._dispatch("weather", cached_weather)
        cached_feed = self.feeds.latest()
        if cached_feed:
            self._dispatch("feed", tuple(cached_feed))

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

    def _dispatch(self, topic: str, payload: object) -> None:
        if self.window is not None:
            self.window.dispatch_event(PluginEvent(topic, payload))

    def _telemetry_from_worker(self, snapshot: TelemetrySnapshot) -> None:
        GLib.idle_add(self._apply_telemetry, snapshot)

    def _apply_telemetry(self, snapshot: TelemetrySnapshot) -> bool:
        self._dispatch("telemetry", snapshot)
        return False

    def _refresh_weather(self) -> bool:
        revision = self._service_revision
        self.weather.refresh_async(lambda snapshot: self._weather_from_worker(snapshot, revision))
        return True

    def _weather_from_worker(self, snapshot: WeatherSnapshot, revision: int) -> None:
        GLib.idle_add(self._apply_weather, snapshot, revision)

    def _apply_weather(self, snapshot: WeatherSnapshot, revision: int) -> bool:
        if revision == self._service_revision:
            self._dispatch("weather", snapshot)
        return False

    def _refresh_feed(self) -> bool:
        revision = self._service_revision
        self.feeds.refresh_async(lambda items: self._feed_from_worker(tuple(items), revision))
        return True

    def _feed_from_worker(self, items: Sequence[FeedItem], revision: int) -> None:
        GLib.idle_add(self._apply_feed, tuple(items), revision)

    def _apply_feed(self, items: Sequence[FeedItem], revision: int) -> bool:
        if revision == self._service_revision:
            self._dispatch("feed", tuple(items))
        return False

    def _tick_focus(self) -> bool:
        self._dispatch("focus", self.focus.state())
        return True

    def _focus_start(self) -> None:
        self._dispatch("focus", self.focus.start())

    def _focus_pause(self) -> None:
        self._dispatch("focus", self.focus.pause())

    def _focus_reset(self) -> None:
        self._dispatch("focus", self.focus.reset())

    def _save_settings(self, settings: DeskOSSettings) -> None:
        previous = self.settings
        self.settings = self.settings_repository.save(settings)
        settings = self.settings
        network_changed = (
            previous.weather_display_name != settings.weather_display_name
            or previous.weather_latitude != settings.weather_latitude
            or previous.weather_longitude != settings.weather_longitude
            or previous.rss_urls != settings.rss_urls
        )
        focus_changed = (
            previous.focus_minutes != settings.focus_minutes
            or previous.rest_minutes != settings.rest_minutes
        )
        if network_changed:
            self._configure_network_services(settings)
            self._refresh_weather()
            self._refresh_feed()
        if focus_changed:
            state = self.focus.state()
            duration = settings.focus_minutes if state.mode == "focus" else settings.rest_minutes
            self.focus.set_mode(state.mode, duration_seconds=duration * 60)
        if self.window is not None:
            self.window.update_settings(settings)
        self._tick_focus()

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
