from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

_PLUGIN_ID = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")


class SettingReader(Protocol):
    def __call__(self, key: str, default: Any = None) -> Any: ...


class SettingWriter(Protocol):
    def __call__(self, key: str, value: Any) -> None: ...


@dataclass(frozen=True, slots=True)
class PluginMetadata:
    id: str
    name: str
    description: str
    version: str
    order: int

    def __post_init__(self) -> None:
        if not _PLUGIN_ID.fullmatch(self.id):
            raise ValueError(f"invalid plugin id: {self.id!r}")
        if not self.name.strip() or not self.description.strip() or not self.version.strip():
            raise ValueError("plugin name, description, and version must not be empty")


@dataclass(frozen=True, slots=True)
class PluginEvent:
    topic: str
    payload: object

    def __post_init__(self) -> None:
        if not self.topic.strip():
            raise ValueError("plugin event topic must not be empty")


@dataclass(frozen=True, slots=True)
class PluginContext:
    """Small stable capability surface passed to plugin screens and hooks."""

    navigate: Callable[[str], None]
    dispatch: Callable[[PluginEvent], None]
    get_setting: SettingReader
    set_setting: SettingWriter


ScreenFactory = Callable[[PluginContext], object]
WidgetFactory = Callable[[PluginContext], object]
LifecycleHook = Callable[[PluginContext], None]


@dataclass(frozen=True, slots=True)
class PluginSpec:
    metadata: PluginMetadata
    create_screen: ScreenFactory
    on_install: LifecycleHook | None = None
    on_remove: LifecycleHook | None = None
    create_widget: WidgetFactory | None = None
