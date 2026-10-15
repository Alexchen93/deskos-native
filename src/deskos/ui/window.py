"""Top-level DeskOS shell for a widget home and edge-triggered App Rail."""
# ruff: noqa: E402

from __future__ import annotations

from collections.abc import Callable, Sequence

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from deskos.plugins import PluginContext, PluginEvent, PluginManager, PluginRegistry
from deskos.services.storage import SQLiteRepository
from deskos.settings import DeskOSSettings

from .home import HomeScreen, HomeWidget
from .screens import AppLibraryScreen, LibraryEntry, SettingsScreen
from .style import install_css


class DeskOSWindow(Gtk.ApplicationWindow):
    """Fullscreen application shell with no persistent navigation furniture."""

    HOME = "home"
    LIBRARY = "library"
    SETTINGS = "settings"
    DISPLAY_WIDTH = 1024
    DISPLAY_HEIGHT = 600
    HOME_LAYOUT_KEY = "home.widget_layout"
    EDGE_ACTIVATION_PX = 32
    EDGE_SWIPE_PX = 72
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
        self._plugin_screens: dict[str, Gtk.Widget] = {}
        self._plugin_widgets: dict[str, Gtk.Widget] = {}
        self._latest_events: dict[str, PluginEvent] = {}
        self._runtime_errors: dict[str, str] = {}
        self._active_plugin_id: str | None = None
        self._rail_origin = "left"

        root = Gtk.Overlay()
        self._stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.CROSSFADE,
            transition_duration=180,
            hexpand=True,
            vexpand=True,
        )
        self.home = HomeScreen(self.navigate, self._save_home_layout)
        self.library = AppLibraryScreen(self._library_entries, self._set_plugin_installed)
        self.settings_screen = SettingsScreen(settings, on_settings_save)
        for name, widget in (
            (self.HOME, self.home),
            (self.LIBRARY, self.library),
            (self.SETTINGS, self.settings_screen),
        ):
            self._stack.add_named(widget, name)
        self._rail_layer = self._make_app_rail()
        for spec in self._registry.all():
            if self._plugins.is_installed(spec.metadata.id):
                self._mount_plugin(spec.metadata.id)
        self._stack.connect("notify::visible-child-name", self._on_screen_changed)
        root.set_child(self._stack)
        root.add_overlay(self._rail_layer)
        self._install_edge_gesture(root)
        self.set_child(root)
        self._sync_home_widgets()

    def _make_app_rail(self) -> Gtk.Box:
        """Build a temporary overlay: it dims content instead of consuming its width."""
        layer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True, vexpand=True)
        layer.add_css_class("app-rail-layer")
        layer.set_visible(False)
        self._rail_layer = layer

        self._rail_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._rail_panel.add_css_class("app-rail-panel")
        header = Gtk.Box(spacing=8)
        header.append(
            Gtk.Label(label="應用程式", hexpand=True, xalign=0, css_classes=["rail-title"])
        )
        close = Gtk.Button(label="×", tooltip_text="關閉 App 軌道")
        close.add_css_class("rail-close")
        close.connect("clicked", lambda _button: self._hide_rail())
        header.append(close)
        self._rail_panel.append(header)
        self._rail_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroll.set_child(self._rail_list)
        self._rail_panel.append(scroll)
        self._rail_hint = Gtk.Label(
            label="向外滑動或點畫面空白處關閉", xalign=0, css_classes=["rail-hint"]
        )
        self._rail_panel.append(self._rail_hint)

        self._rail_scrim = Gtk.Box(hexpand=True, vexpand=True)
        self._rail_scrim.add_css_class("app-rail-scrim")
        dismiss = Gtk.GestureClick.new()
        dismiss.connect("released", lambda *_args: self._hide_rail())
        self._rail_scrim.add_controller(dismiss)
        self._place_rail_children()
        return layer

    def _place_rail_children(self) -> None:
        while child := self._rail_layer.get_first_child():
            self._rail_layer.remove(child)
        if self._rail_origin == "right":
            self._rail_layer.append(self._rail_scrim)
            self._rail_layer.append(self._rail_panel)
        else:
            self._rail_layer.append(self._rail_panel)
            self._rail_layer.append(self._rail_scrim)

    def _install_edge_gesture(self, root: Gtk.Widget) -> None:
        gesture = Gtk.GestureDrag.new()
        gesture.connect("drag-end", self._on_edge_drag_end)
        root.add_controller(gesture)

    def _on_edge_drag_end(
        self, gesture: Gtk.GestureDrag, offset_x: float, _offset_y: float
    ) -> None:
        if self._rail_layer.get_visible():
            if abs(offset_x) >= self.EDGE_SWIPE_PX:
                self._hide_rail()
            return
        start = gesture.get_start_point()
        if start is None:
            return
        _recognized, start_x, _start_y = start
        width = self.get_width() or self.DISPLAY_WIDTH
        left_open = start_x <= self.EDGE_ACTIVATION_PX and offset_x >= self.EDGE_SWIPE_PX
        right_open = (
            start_x >= width - self.EDGE_ACTIVATION_PX and offset_x <= -self.EDGE_SWIPE_PX
        )
        if left_open:
            self._show_rail("left")
        elif right_open:
            self._show_rail("right")

    def _show_rail(self, origin: str = "left") -> None:
        self._rail_origin = origin
        self._place_rail_children()
        self._refresh_rail()
        self._rail_layer.set_visible(True)

    def _hide_rail(self) -> None:
        self._rail_layer.set_visible(False)

    def _refresh_rail(self) -> None:
        while child := self._rail_list.get_first_child():
            self._rail_list.remove(child)
        self._append_rail_item(self.HOME, "首頁", "Widget 桌面")
        self._append_rail_item("edit-home", "編輯首頁", "排列、調整或隱藏 Widget")
        self._append_rail_divider("已加入的 App")
        for spec in self._registry.all():
            plugin_id = spec.metadata.id
            if self._plugins.is_installed(plugin_id):
                self._append_rail_item(
                    plugin_id, spec.metadata.name, spec.metadata.description, plugin=True
                )
        self._append_rail_divider("系統")
        self._append_rail_item(self.LIBRARY, "管理 App", "加入或移除本機 App")
        self._append_rail_item(self.SETTINGS, "設定", "偏好與資料來源")

    def _append_rail_item(
        self, page: str, title: str, detail: str, *, plugin: bool = False
    ) -> None:
        button = Gtk.Button(hexpand=True)
        button.add_css_class("rail-item")
        if plugin:
            button.add_css_class("rail-app")
        copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        copy.append(Gtk.Label(label=title, xalign=0, css_classes=["rail-item-title"]))
        copy.append(Gtk.Label(label=detail, xalign=0, css_classes=["rail-item-detail"]))
        button.set_child(copy)
        button.connect(
            "clicked", lambda _button, destination=page: self._select_rail_item(destination)
        )
        self._rail_list.append(button)

    def _append_rail_divider(self, label: str) -> None:
        self._rail_list.append(Gtk.Label(label=label, xalign=0, css_classes=["rail-divider"]))

    def _select_rail_item(self, page: str) -> None:
        self._hide_rail()
        if page == "edit-home":
            self.navigate(self.HOME)
            self.home.enter_edit_mode()
            return
        self.navigate(page)

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
        context = self._context_for(plugin_id)
        try:
            screen = spec.create_screen(context)
            if not isinstance(screen, Gtk.Widget):
                raise TypeError("screen factory must return a Gtk.Widget")
        except Exception as error:
            self._runtime_errors[plugin_id] = str(error)
            return False
        self._runtime_errors.pop(plugin_id, None)
        self._plugin_screens[plugin_id] = screen
        self._plugin_widgets[plugin_id] = self._create_home_widget(plugin_id, context)
        self._stack.add_named(screen, plugin_id)
        for event in self._latest_events.values():
            self._deliver(plugin_id, screen, event)
            self._deliver(plugin_id, self._plugin_widgets[plugin_id], event)
        self._sync_home_widgets()
        return True

    def _create_home_widget(self, plugin_id: str, context: PluginContext) -> Gtk.Widget:
        spec = self._registry.get(plugin_id)
        factory = getattr(spec, "create_widget", None)
        if callable(factory):
            try:
                widget = factory(context)
                if isinstance(widget, Gtk.Widget):
                    return widget
                raise TypeError("widget factory must return a Gtk.Widget")
            except Exception as error:
                self._runtime_errors[plugin_id] = str(error)
        fallback = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, valign=Gtk.Align.CENTER)
        fallback.add_css_class("fallback-widget")
        fallback.append(
            Gtk.Label(label=spec.metadata.name, xalign=0, css_classes=["widget-title"])
        )
        fallback.append(
            Gtk.Label(
                label=spec.metadata.description,
                xalign=0,
                wrap=True,
                css_classes=["widget-detail"],
            )
        )
        return fallback

    def _unmount_plugin(self, plugin_id: str) -> None:
        screen = self._plugin_screens.pop(plugin_id, None)
        self._plugin_widgets.pop(plugin_id, None)
        if screen is None:
            self._runtime_errors.pop(plugin_id, None)
            self._sync_home_widgets()
            return
        was_visible = self._stack.get_visible_child_name() == plugin_id
        self._invoke(screen, "on_deactivate")
        if was_visible:
            self._active_plugin_id = None
            self._stack.set_visible_child_name(self.HOME)
        self._stack.remove(screen)
        self._history = [page for page in self._history if page != plugin_id]
        self._runtime_errors.pop(plugin_id, None)
        self._sync_home_widgets()

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
                self._sync_home_widgets()
        else:
            try:
                self._plugins.remove(plugin_id, context)
            except Exception as error:
                self._runtime_errors[plugin_id] = str(error)
            else:
                self._unmount_plugin(plugin_id)
        self.library.refresh()

    def _library_entries(self) -> Sequence[LibraryEntry]:
        entries = [
            LibraryEntry(page, label, "DeskOS 核心頁面", "0.5.0", "核心", False, True)
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
        if page not in {self.HOME, self.LIBRARY, self.SETTINGS, *self._plugin_screens}:
            return
        current = self._stack.get_visible_child_name()
        if page == current:
            return
        if current:
            self._history.append(current)
        self.home.set_editing(False)
        self._stack.set_visible_child_name(page)

    def go_back(self) -> None:
        while self._history:
            destination = self._history.pop()
            if destination in {self.HOME, self.LIBRARY, self.SETTINGS, *self._plugin_screens}:
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

    def _sync_home_widgets(self) -> None:
        entries = tuple(
            HomeWidget(spec.metadata.id, spec.metadata.name, self._plugin_widgets[spec.metadata.id])
            for spec in self._registry.all()
            if spec.metadata.id in self._plugin_widgets
            and self._plugins.is_installed(spec.metadata.id)
        )
        layout = self._repository.get_setting(self.HOME_LAYOUT_KEY, [])
        self.home.set_widgets(entries, layout)

    def _save_home_layout(self, layout: list[dict[str, object]]) -> None:
        self._repository.set_setting(self.HOME_LAYOUT_KEY, layout)

    def dispatch_event(self, event: PluginEvent) -> None:
        self._latest_events[event.topic] = event
        for plugin_id, screen in tuple(self._plugin_screens.items()):
            if self._plugins.is_installed(plugin_id):
                self._deliver(plugin_id, screen, event)
                widget = self._plugin_widgets.get(plugin_id)
                if widget is not None:
                    self._deliver(plugin_id, widget, event)

    def update_settings(self, settings: DeskOSSettings) -> None:
        self._settings = settings
        self.dispatch_event(PluginEvent("settings", settings))

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
