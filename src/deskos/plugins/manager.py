from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Protocol

from .api import PluginContext
from .registry import PluginRegistry


class SettingsStore(Protocol):
    def get_setting(self, key: str, default: Any = None) -> Any: ...

    def set_setting(self, key: str, value: Any) -> None: ...


class PluginManager:
    """Persist local plugin enablement; package installation is deliberately out of scope."""

    STORAGE_KEY = "plugins.installed_ids"

    def __init__(
        self,
        registry: PluginRegistry,
        store: SettingsStore,
        *,
        default_installed_ids: Iterable[str],
    ) -> None:
        self._registry = registry
        self._store = store
        stored = store.get_setting(self.STORAGE_KEY, None)
        if stored is None:
            self._installed = set(default_installed_ids)
            self._save()
        elif isinstance(stored, list) and all(isinstance(item, str) for item in stored):
            self._installed = set(stored)
        else:
            self._installed = set()
            self._save()
        self._listeners: list[Callable[[frozenset[str]], None]] = []

    @property
    def installed_ids(self) -> frozenset[str]:
        return frozenset(self._installed)

    def is_installed(self, plugin_id: str) -> bool:
        return plugin_id in self._installed

    def subscribe(self, callback: Callable[[frozenset[str]], None]) -> Callable[[], None]:
        self._listeners.append(callback)

        def unsubscribe() -> None:
            try:
                self._listeners.remove(callback)
            except ValueError:
                pass

        return unsubscribe

    def install(self, plugin_id: str, context: PluginContext) -> None:
        spec = self._registry.get(plugin_id)
        if plugin_id in self._installed:
            return
        if spec.on_install is not None:
            spec.on_install(context)
        self._installed.add(plugin_id)
        self._save_and_notify()

    def remove(self, plugin_id: str, context: PluginContext) -> None:
        spec = self._registry.get(plugin_id)
        if plugin_id not in self._installed:
            return
        if spec.on_remove is not None:
            spec.on_remove(context)
        self._installed.remove(plugin_id)
        self._save_and_notify()

    def _save_and_notify(self) -> None:
        self._save()
        snapshot = self.installed_ids
        for callback in tuple(self._listeners):
            callback(snapshot)

    def _save(self) -> None:
        self._store.set_setting(self.STORAGE_KEY, sorted(self._installed))
