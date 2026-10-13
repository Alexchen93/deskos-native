from __future__ import annotations

from typing import Any

from deskos.plugins import PluginContext, PluginManager, PluginMetadata, PluginRegistry, PluginSpec


class _Store:
    def __init__(self, values: dict[str, Any] | None = None) -> None:
        self.values = dict(values or {})
        self.writes: list[tuple[str, Any]] = []

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        self.values[key] = value
        self.writes.append((key, value))


def _context() -> PluginContext:
    return PluginContext(
        navigate=lambda _page: None,
        dispatch=lambda _event: None,
        get_setting=lambda _key, default=None: default,
        set_setting=lambda _key, _value: None,
    )


def _registry(events: list[str]) -> PluginRegistry:
    registry = PluginRegistry()
    registry.register(
        PluginSpec(
            PluginMetadata("clock", "Clock", "Local clock", "0.4.0", 10),
            lambda _context: object(),
        )
    )
    registry.register(
        PluginSpec(
            PluginMetadata("sample", "Sample", "Sample plugin", "0.4.0", 20),
            lambda _context: object(),
            on_install=lambda _context: events.append("install"),
            on_remove=lambda _context: events.append("remove"),
        )
    )
    return registry


def test_first_run_seeds_and_persists_default_installed_plugins() -> None:
    store = _Store()
    manager = PluginManager(_registry([]), store, default_installed_ids=("clock", "sample"))

    assert manager.installed_ids == frozenset({"clock", "sample"})
    assert store.values[PluginManager.STORAGE_KEY] == ["clock", "sample"]
    assert store.writes == [(PluginManager.STORAGE_KEY, ["clock", "sample"])]


def test_existing_valid_installation_survives_restart_without_reseeding() -> None:
    store = _Store({PluginManager.STORAGE_KEY: ["sample", "sample"]})

    manager = PluginManager(_registry([]), store, default_installed_ids=("clock",))

    assert manager.installed_ids == frozenset({"sample"})
    assert store.writes == []


def test_invalid_persisted_installation_is_repaired_to_empty_list() -> None:
    store = _Store({PluginManager.STORAGE_KEY: "sample"})

    manager = PluginManager(_registry([]), store, default_installed_ids=("clock",))

    assert manager.installed_ids == frozenset()
    assert store.writes == [(PluginManager.STORAGE_KEY, [])]


def test_install_remove_are_durable_idempotent_and_notify_subscribers() -> None:
    events: list[str] = []
    store = _Store()
    manager = PluginManager(_registry(events), store, default_installed_ids=("clock",))
    notifications: list[frozenset[str]] = []
    unsubscribe = manager.subscribe(notifications.append)

    manager.install("sample", _context())
    manager.install("sample", _context())
    manager.remove("sample", _context())
    manager.remove("sample", _context())
    unsubscribe()
    manager.install("sample", _context())

    assert events == ["install", "remove", "install"]
    assert notifications == [frozenset({"clock", "sample"}), frozenset({"clock"})]
    assert store.values[PluginManager.STORAGE_KEY] == ["clock", "sample"]
    assert [value for key, value in store.writes if key == PluginManager.STORAGE_KEY] == [
        ["clock"],
        ["clock", "sample"],
        ["clock"],
        ["clock", "sample"],
    ]
