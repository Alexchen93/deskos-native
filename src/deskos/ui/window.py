"""Top-level DeskOS shell tuned for the 1024×600 Raspberry Pi display."""
# ruff: noqa: E402

from __future__ import annotations

from collections.abc import Callable, Sequence

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from deskos.plugins import PluginContext, PluginEvent, PluginManager, PluginRegistry
from deskos.services.storage import SQLiteRepository
from deskos.settings import DeskOSSettings

from .screens import AppLibraryScreen, HomeScreen, LibraryEntry, SettingsScreen
from .style import install_css


class DeskOSWindow(Gtk.ApplicationWindow):
    """Core shell plus dynamically mounted plugin screens."""

    HOME = "home"
    LIBRARY = "library"
    SETTINGS = "settings"
    DISPLAY_WIDTH = 1024
    DISPLAY_HEIGHT = 600
    _CORE_NAV_ITEMS = (
        (HOME, "首頁"),
        (LIBRARY, "應用程式"),
        (SETTINGS, "設定"),
    )

    def __init__(
        self,
        application: Gtk.Application,
        *,
        registry: PluginRegistry,
        plugins: PluginManager,
        repository: SQLiteRepository,
        settings: DeskOSSettings,
        on_settings_save: Callable[[DeskOSSettings], None],
    ) -> None:
        super().__init__(
            application=application,
            title="DeskOS",
            default_width=self.DISPLAY_WIDTH,
            default_height=self.DISPLAY_HEIGHT,
        )
        self.set_resizable(False)
        install_css()
        self._registry = registry
        self._plugins = plugins
        self._repository = repository
        self._settings = settings
        self._on_settings_save = on_settings_save
        self._history: list[str] = []
        self._nav_buttons: dict[str, Gtk.Button] = {}
        self._plugin_screens: dict[str, Gtk.Widget] = {}
        self._latest_events: dict[str, PluginEvent] = {}
        self._runtime_errors: dict[str, str] = {}
        self._active_plugin_id: str | None = None

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        root.append(self._make_sidebar())
        self._stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.CROSSFADE,
            transition_duration=140,
            hexpand=True,
            vexpand=True,
        )
        self.home = HomeScreen(self.navigate)
        self.library = AppLibraryScreen(self._library_entries, self._set_plugin_installed)
        self.settings_screen = SettingsScreen(settings, on_settings_save)
        for name, widget in (
            (self.HOME, self.home),
            (self.LIBRARY, self.library),
            (self.SETTINGS, self.settings_screen),
        ):
            self._stack.add_named(widget, name)
        for spec in self._registry.all():
            if self._plugins.is_installed(spec.metadata.id):
                self._mount_plugin(spec.metadata.id)
        self._stack.connect("notify::visible-child-name", self._on_screen_changed)
        root.append(self._stack)
        self.set_child(root)
        self._sync_home_availability()
        self._set_active_navigation(self.HOME)

    def _make_sidebar(self) -> Gtk.Box:
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar.add_css_class("sidebar")
        brand = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        brand.append(Gtk.Label(label="DeskOS", xalign=0, css_classes=["brand-title"]))
        brand.append(Gtk.Label(label="本機控制", xalign=0, css_classes=["brand-subtitle"]))
        sidebar.append(brand)

        scroll = Gtk.ScrolledWindow(
            vexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        )
        self._nav = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._nav.add_css_class("nav-list")
        scroll.set_child(self._nav)
        sidebar.append(scroll)
        for page, label in self._CORE_NAV_ITEMS:
            self._add_navigation(page, label)

        status = Gtk.Box(spacing=7)
        status.add_css_class("sidebar-status")
        status.append(Gtk.Label(label="●", css_classes=["status-dot"]))
        self._status = Gtk.Label(label="系統就緒", xalign=0, css_classes=["status-label"])
        status.append(self._status)
        sidebar.append(status)
        return sidebar

    def _add_navigation(self, page: str, label: str) -> None:
        if page in self._nav_buttons:
            return
        button = Gtk.Button()
        button.add_css_class("nav-button")
        button.set_child(Gtk.Label(label=label, xalign=0, hexpand=True, css_classes=["nav-label"]))
        button.connect("clicked", lambda _button, destination=page: self.navigate(destination))
        self._nav_buttons[page] = button
        self._nav.append(button)

    def _remove_navigation(self, page: str) -> None:
        button = self._nav_buttons.pop(page, None)
        if button is not None:
            self._nav.remove(button)

    def _context_for(self, plugin_id: str) -> PluginContext:
        prefix = f"plugin.{plugin_id}."
        return PluginContext(
            navigate=self.navigate,
            dispatch=self.dispatch_event,
            get_setting=lambda key, default=None: self._repository.get_setting(
                prefix + key, default
            ),
            set_setting=lambda key, value: self._repository.set_setting(prefix + key, value),
        )

    def _mount_plugin(self, plugin_id: str) -> bool:
        if plugin_id in self._plugin_screens:
            return True
        spec = self._registry.get(plugin_id)
        try:
            screen = spec.create_screen(self._context_for(plugin_id))
            if not isinstance(screen, Gtk.Widget):
                raise TypeError("screen factory must return a Gtk.Widget")
        except Exception as error:
            self._runtime_errors[plugin_id] = str(error)
            return False
        self._runtime_errors.pop(plugin_id, None)
        self._plugin_screens[plugin_id] = screen
        self._stack.add_named(screen, plugin_id)
        self._add_navigation(plugin_id, spec.metadata.name)
        for event in self._latest_events.values():
            self._deliver(plugin_id, screen, event)
        return True

    def _unmount_plugin(self, plugin_id: str) -> None:
        screen = self._plugin_screens.pop(plugin_id, None)
        if screen is None:
            self._remove_navigation(plugin_id)
            self._runtime_errors.pop(plugin_id, None)
            return
        was_visible = self._stack.get_visible_child_name() == plugin_id
        if was_visible:
            self._invoke(screen, "on_deactivate")
            self._active_plugin_id = None
            self._stack.set_visible_child_name(self.HOME)
        else:
            self._invoke(screen, "on_deactivate")
        self._stack.remove(screen)
        self._remove_navigation(plugin_id)
        self._history = [page for page in self._history if page != plugin_id]
        self._runtime_errors.pop(plugin_id, None)

    def _set_plugin_installed(self, plugin_id: str, install: bool) -> None:
        context = self._context_for(plugin_id)
        if install:
            if not self._mount_plugin(plugin_id):
                self.library.refresh()
                return
            try:
                self._plugins.install(plugin_id, context)
            except Exception as error:
                self._unmount_plugin(plugin_id)
                self._runtime_errors[plugin_id] = str(error)
        else:
            try:
                self._plugins.remove(plugin_id, context)
            except Exception as error:
                self._runtime_errors[plugin_id] = str(error)
            else:
                self._unmount_plugin(plugin_id)
        self._sync_home_availability()
        self.library.refresh()

    def _library_entries(self) -> Sequence[LibraryEntry]:
        entries = [
            LibraryEntry(page, label, "DeskOS 核心頁面", "0.4.0", "核心", False, True)
            for page, label in self._CORE_NAV_ITEMS
        ]
        for spec in self._registry.all():
            plugin_id = spec.metadata.id
            error = self._runtime_errors.get(plugin_id)
            installed = self._plugins.is_installed(plugin_id)
            status = (
                "已加入 · 錯誤"
                if error and installed
                else "錯誤"
                if error
                else "已加入"
                if installed
                else "可加入"
            )
            description = (
                f"{spec.metadata.description} · {error}" if error else spec.metadata.description
            )
            entries.append(
                LibraryEntry(
                    plugin_id,
                    spec.metadata.name,
                    description,
                    spec.metadata.version,
                    status,
                    True,
                    installed,
                )
            )
        entries.extend(
            LibraryEntry(
                f"discovery-error-{index}",
                error.source,
                error.message,
                "—",
                "探索錯誤",
                False,
            )
            for index, error in enumerate(self._registry.errors)
        )
        return tuple(entries)

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
        while self._history:
            destination = self._history.pop()
            if destination in self._nav_buttons:
                self._stack.set_visible_child_name(destination)
                return
        self._stack.set_visible_child_name(self.HOME)

    def _on_screen_changed(self, stack: Gtk.Stack, _param: object) -> None:
        page = stack.get_visible_child_name() or self.HOME
        if self._active_plugin_id and self._active_plugin_id != page:
            previous = self._plugin_screens.get(self._active_plugin_id)
            if previous is not None:
                self._invoke(previous, "on_deactivate")
        self._active_plugin_id = page if page in self._plugin_screens else None
        if self._active_plugin_id:
            self._invoke(self._plugin_screens[self._active_plugin_id], "on_activate")
        if page == self.LIBRARY:
            self.library.refresh()
        self._set_active_navigation(page)
        self._status.set_label("應用程式執行中" if self._active_plugin_id else "系統就緒")

    def _set_active_navigation(self, active_page: str) -> None:
        for page, button in self._nav_buttons.items():
            if page == active_page:
                button.add_css_class("active")
            else:
                button.remove_css_class("active")

    def dispatch_event(self, event: PluginEvent) -> None:
        self._latest_events[event.topic] = event
        self._deliver_home(event)
        for plugin_id, screen in tuple(self._plugin_screens.items()):
            if self._plugins.is_installed(plugin_id):
                self._deliver(plugin_id, screen, event)

    def update_settings(self, settings: DeskOSSettings) -> None:
        self._settings = settings
        self.dispatch_event(PluginEvent("settings", settings))

    def _deliver_home(self, event: PluginEvent) -> None:
        handlers = {
            "settings": self.home.update_settings,
            "weather": self.home.update_weather,
            "feed": self.home.update_feed,
            "focus": self.home.update_focus,
            "telemetry": self.home.update_telemetry,
        }
        handler = handlers.get(event.topic)
        if handler is not None:
            handler(event.payload)

    def _deliver(self, plugin_id: str, screen: Gtk.Widget, event: PluginEvent) -> None:
        handler = getattr(screen, "on_plugin_event", None)
        if callable(handler):
            try:
                handler(event)
            except Exception as error:
                self._runtime_errors[plugin_id] = str(error)

    @staticmethod
    def _invoke(screen: Gtk.Widget, method_name: str) -> None:
        handler = getattr(screen, method_name, None)
        if callable(handler):
            handler()

    def _sync_home_availability(self) -> None:
        for plugin_id in ("weather", "feed", "focus", "device"):
            self.home.set_plugin_available(plugin_id, self._plugins.is_installed(plugin_id))
