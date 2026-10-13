"""Top-level DeskOS shell tuned for the 1024×600 Raspberry Pi display."""
# ruff: noqa: E402

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from deskos.core.models import FeedItem, FocusState, TelemetrySnapshot, WeatherSnapshot
from deskos.paths import MODEL_PATH, MODEL_PREVIEW_PATH

from .screens import (
    ClockScreen,
    DeviceMonitorScreen,
    FocusScreen,
    HomeScreen,
    TechFeedScreen,
    WeatherScreen,
)
from .style import install_css


class DeskOSWindow(Gtk.ApplicationWindow):
    """Persistent touch navigation and data-only update boundary for every screen."""

    HOME = "home"
    DISPLAY_WIDTH = 1024
    DISPLAY_HEIGHT = 600
    _NAV_ITEMS = (
        ("home", "首頁"),
        ("clock", "時鐘"),
        ("weather", "天氣"),
        ("feed", "快訊"),
        ("focus", "專注"),
        ("device", "裝置"),
    )

    def __init__(
        self,
        application: Gtk.Application,
        *,
        low_power: bool = False,
        on_focus_start: Callable[[], None] | None = None,
        on_focus_pause: Callable[[], None] | None = None,
        on_focus_reset: Callable[[], None] | None = None,
        model_path: Path = MODEL_PATH,
        preview_path: Path = MODEL_PREVIEW_PATH,
    ) -> None:
        super().__init__(
            application=application,
            title="DeskOS",
            default_width=self.DISPLAY_WIDTH,
            default_height=self.DISPLAY_HEIGHT,
        )
        self.set_resizable(False)
        install_css()

        self._history: list[str] = []
        self._nav_buttons: dict[str, Gtk.Button] = {}
        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        root.append(self._make_sidebar())

        self._stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.CROSSFADE,
            transition_duration=140,
            hexpand=True,
            vexpand=True,
        )
        self.home = HomeScreen(self.navigate)
        self.clock = ClockScreen()
        self.weather = WeatherScreen()
        self.feed = TechFeedScreen()
        self.focus = FocusScreen(on_focus_start, on_focus_pause, on_focus_reset)
        self.device = DeviceMonitorScreen(model_path, preview_path, low_power)
        for name, widget in (
            (self.HOME, self.home),
            ("clock", self.clock),
            ("weather", self.weather),
            ("feed", self.feed),
            ("focus", self.focus),
            ("device", self.device),
        ):
            self._stack.add_named(widget, name)
        self._stack.connect("notify::visible-child-name", self._on_screen_changed)
        root.append(self._stack)
        self.set_child(root)
        self._set_active_navigation(self.HOME)

    def _make_sidebar(self) -> Gtk.Box:
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar.add_css_class("sidebar")

        brand = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        brand.append(Gtk.Label(label="DeskOS", xalign=0, css_classes=["brand-title"]))
        brand.append(Gtk.Label(label="本機控制", xalign=0, css_classes=["brand-subtitle"]))
        sidebar.append(brand)

        nav = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, vexpand=True)
        nav.add_css_class("nav-list")
        for page, label in self._NAV_ITEMS:
            button = Gtk.Button()
            button.add_css_class("nav-button")
            button.set_child(
                Gtk.Label(label=label, xalign=0, hexpand=True, css_classes=["nav-label"])
            )
            button.connect("clicked", lambda _button, destination=page: self.navigate(destination))
            self._nav_buttons[page] = button
            nav.append(button)
        sidebar.append(nav)

        status = Gtk.Box(spacing=7)
        status.add_css_class("sidebar-status")
        status.append(Gtk.Label(label="●", css_classes=["status-dot"]))
        self._status = Gtk.Label(label="系統就緒", xalign=0, css_classes=["status-label"])
        status.append(self._status)
        sidebar.append(status)
        return sidebar

    def navigate(self, page: str) -> None:
        if page not in self._nav_buttons:
            return
        current = self._stack.get_visible_child_name()
        if page == current:
            return
        if current:
            self._history.append(current)
        self._stack.set_visible_child_name(page)

    def go_back(self) -> None:
        destination = self._history.pop() if self._history else self.HOME
        self._stack.set_visible_child_name(destination)

    def _on_screen_changed(self, stack: Gtk.Stack, _param: object) -> None:
        page = stack.get_visible_child_name() or self.HOME
        self.device.set_render_active(page == "device")
        self._set_active_navigation(page)
        self._status.set_label("3D 監測中" if page == "device" else "系統就緒")

    def _set_active_navigation(self, active_page: str) -> None:
        for page, button in self._nav_buttons.items():
            if page == active_page:
                button.add_css_class("active")
            else:
                button.remove_css_class("active")

    def update_telemetry(self, snapshot: TelemetrySnapshot) -> None:
        self.device.update_telemetry(snapshot)
        self.home.update_telemetry(snapshot)

    def update_weather(self, snapshot: WeatherSnapshot) -> None:
        self.weather.update_weather(snapshot)
        self.home.update_weather(snapshot)

    def update_feed(self, items: Sequence[FeedItem]) -> None:
        self.feed.update_feed(items)
        self.home.update_feed(items)

    def update_focus(self, state: FocusState) -> None:
        self.focus.update_focus(state)
        self.home.update_focus(state)
