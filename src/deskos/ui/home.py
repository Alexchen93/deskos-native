"""Customisable widget home screen for DeskOS."""
# ruff: noqa: E402

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


@dataclass(frozen=True, slots=True)
class HomeWidget:
    """A home preview owned by one installed application."""

    id: str
    name: str
    widget: Gtk.Widget


@dataclass(slots=True)
class _WidgetShell:
    entry: HomeWidget
    shell: Gtk.Overlay
    button: Gtk.Button
    controls: Gtk.Box


class HomeScreen(Gtk.Box):
    """A user-arrangeable, touch-first surface of installed app widgets."""

    LAYOUT_SIZE_STANDARD = "standard"
    LAYOUT_SIZE_WIDE = "wide"
    _VALID_SIZES = frozenset((LAYOUT_SIZE_STANDARD, LAYOUT_SIZE_WIDE))

    def __init__(
        self,
        on_navigate: Callable[[str], None],
        on_layout_changed: Callable[[list[dict[str, object]]], None],
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add_css_class("home-screen")
        self._on_navigate = on_navigate
        self._on_layout_changed = on_layout_changed
        self._entries: dict[str, HomeWidget] = {}
        self._shells: dict[str, _WidgetShell] = {}
        self._layout: list[dict[str, object]] = []
        self._editing = False

        header = Gtk.Box(spacing=12)
        header.add_css_class("home-header")
        copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        self._title = Gtk.Label(label="我的桌面", xalign=0, css_classes=["home-greeting"])
        self._subtitle = Gtk.Label(
            label="每個 App 都在這裡即時更新", xalign=0, css_classes=["screen-subtitle"]
        )
        copy.append(self._title)
        copy.append(self._subtitle)
        header.append(copy)
        self._start_edit = Gtk.Button(label="編輯桌面")
        self._start_edit.add_css_class("home-edit-start")
        self._start_edit.connect("clicked", lambda _button: self.set_editing(True))
        header.append(self._start_edit)
        self._finish_edit = Gtk.Button(label="完成編輯")
        self._finish_edit.add_css_class("home-edit-done")
        self._finish_edit.connect("clicked", lambda _button: self.set_editing(False))
        self._finish_edit.set_visible(False)
        header.append(self._finish_edit)
        self.append(header)

        self._scroll = Gtk.ScrolledWindow(
            vexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        )
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self._grid = Gtk.Grid(column_spacing=14, row_spacing=14)
        self._grid.add_css_class("home-widget-grid")
        content.append(self._grid)
        self._hidden = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._hidden.add_css_class("hidden-widgets")
        self._hidden.set_visible(False)
        content.append(self._hidden)
        self._scroll.set_child(content)
        self.append(self._scroll)

    def set_widgets(self, entries: Sequence[HomeWidget], layout: object) -> None:
        """Adopt installed app widgets and normalise their persisted arrangement."""
        incoming = {entry.id: entry for entry in entries}
        for widget_id, shell in tuple(self._shells.items()):
            if widget_id not in incoming:
                self._grid.remove(shell.shell)
                self._shells.pop(widget_id)
        self._entries = incoming
        for widget_id, entry in incoming.items():
            existing = self._shells.get(widget_id)
            if existing is None:
                self._shells[widget_id] = self._make_shell(entry)
            elif existing.entry.widget is not entry.widget:
                existing.button.set_child(entry.widget)
                existing.entry = entry
        self._layout = self._normalise_layout(layout)
        self._render()

    def enter_edit_mode(self) -> None:
        self.set_editing(True)

    def set_editing(self, editing: bool) -> None:
        self._editing = editing
        self._title.set_label("排列我的桌面" if editing else "我的桌面")
        self._subtitle.set_label(
            "調整順序、寬度與顯示內容" if editing else "每個 App 都在這裡即時更新"
        )
        self._start_edit.set_visible(not editing)
        self._finish_edit.set_visible(editing)
        self._render()

    def _make_shell(self, entry: HomeWidget) -> _WidgetShell:
        shell = Gtk.Overlay(hexpand=True, vexpand=True)
        shell.add_css_class("home-widget-shell")
        button = Gtk.Button(hexpand=True, vexpand=True)
        button.add_css_class("home-widget")
        button.set_child(entry.widget)
        button.connect("clicked", lambda _button, page=entry.id: self._on_navigate(page))
        shell.set_child(button)

        controls = Gtk.Box(spacing=4, halign=Gtk.Align.END, valign=Gtk.Align.START)
        controls.add_css_class("widget-edit-controls")
        for label, callback, hint in (
            ("↑", lambda widget_id=entry.id: self._move(widget_id, -1), "往前"),
            ("↓", lambda widget_id=entry.id: self._move(widget_id, 1), "往後"),
            ("寬", lambda widget_id=entry.id: self._toggle_width(widget_id), "切換寬度"),
            ("×", lambda widget_id=entry.id: self._set_visible(widget_id, False), "隱藏"),
        ):
            control = Gtk.Button(label=label, tooltip_text=hint)
            control.add_css_class("widget-edit-control")
            control.connect("clicked", lambda _button, action=callback: action())
            controls.append(control)
        shell.add_overlay(controls)
        return _WidgetShell(entry, shell, button, controls)

    def _normalise_layout(self, raw_layout: object) -> list[dict[str, object]]:
        raw_items = raw_layout if isinstance(raw_layout, list) else []
        values: dict[str, dict[str, object]] = {}
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            widget_id = item.get("id")
            if (
                isinstance(widget_id, str)
                and widget_id in self._entries
                and widget_id not in values
            ):
                size = item.get("size")
                values[widget_id] = {
                    "id": widget_id,
                    "size": size if size in self._VALID_SIZES else self.LAYOUT_SIZE_STANDARD,
                    "visible": item.get("visible") is not False,
                }
        ordered = [values[widget_id] for widget_id in values]
        for widget_id in self._entries:
            if widget_id not in values:
                ordered.append(
                    {
                        "id": widget_id,
                        "size": self.LAYOUT_SIZE_STANDARD,
                        "visible": widget_id != "focus",
                    }
                )
        return ordered

    def _render(self) -> None:
        for shell in self._shells.values():
            if shell.shell.get_parent() is self._grid:
                self._grid.remove(shell.shell)
        column = 0
        row = 0
        for item in self._layout:
            if not item["visible"]:
                continue
            widget_id = item["id"]
            shell = self._shells.get(widget_id)
            if shell is None:
                continue
            wide = item["size"] == self.LAYOUT_SIZE_WIDE
            span = 2 if wide else 1
            if column + span > 3:
                row += 1
                column = 0
            shell.shell.remove_css_class("widget-wide")
            shell.shell.remove_css_class("widget-standard")
            shell.shell.add_css_class("widget-wide" if wide else "widget-standard")
            shell.controls.set_visible(self._editing)
            shell.button.set_sensitive(not self._editing)
            self._grid.attach(shell.shell, column, row, span, 1)
            column += span
            if column == 3:
                row += 1
                column = 0
        self._render_hidden_widgets()

    def _render_hidden_widgets(self) -> None:
        while child := self._hidden.get_first_child():
            self._hidden.remove(child)
        hidden = [item for item in self._layout if not item["visible"]]
        self._hidden.set_visible(self._editing and bool(hidden))
        if not hidden:
            return
        self._hidden.append(
            Gtk.Label(label="已隱藏的 Widget", xalign=0, css_classes=["hidden-widgets-title"])
        )
        row = Gtk.FlowBox(
            column_spacing=8,
            row_spacing=8,
            selection_mode=Gtk.SelectionMode.NONE,
        )
        for item in hidden:
            widget_id = str(item["id"])
            name = self._entries[widget_id].name
            restore = Gtk.Button(label=f"＋ {name}")
            restore.add_css_class("restore-widget")
            restore.connect(
                "clicked", lambda _button, selected=widget_id: self._set_visible(selected, True)
            )
            row.append(restore)
        self._hidden.append(row)

    def _move(self, widget_id: str, direction: int) -> None:
        index = next((i for i, item in enumerate(self._layout) if item["id"] == widget_id), None)
        if index is None:
            return
        destination = index + direction
        if not 0 <= destination < len(self._layout):
            return
        self._layout[index], self._layout[destination] = (
            self._layout[destination],
            self._layout[index],
        )
        self._commit_layout()

    def _toggle_width(self, widget_id: str) -> None:
        item = self._find_item(widget_id)
        if item is None:
            return
        item["size"] = (
            self.LAYOUT_SIZE_STANDARD
            if item["size"] == self.LAYOUT_SIZE_WIDE
            else self.LAYOUT_SIZE_WIDE
        )
        self._commit_layout()

    def _set_visible(self, widget_id: str, visible: bool) -> None:
        item = self._find_item(widget_id)
        if item is None:
            return
        item["visible"] = visible
        self._commit_layout()

    def _find_item(self, widget_id: str) -> dict[str, object] | None:
        return next((item for item in self._layout if item["id"] == widget_id), None)

    def _commit_layout(self) -> None:
        snapshot = [dict(item) for item in self._layout]
        self._on_layout_changed(snapshot)
        self._render()
