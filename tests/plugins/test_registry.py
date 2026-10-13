from __future__ import annotations

from deskos.plugins import PluginMetadata, PluginRegistry, PluginSpec
from deskos.plugins.registry import ENTRY_POINT_GROUP


def _spec(plugin_id: str, order: int = 10) -> PluginSpec:
    return PluginSpec(
        PluginMetadata(plugin_id, plugin_id.title(), f"{plugin_id} plugin", "0.4.0", order),
        lambda _context: object(),
    )


def test_metadata_validates_identifiers_and_required_text() -> None:
    metadata = PluginMetadata("weather.card", "Weather", "Current weather", "0.4.0", 20)

    assert metadata.id == "weather.card"

    for plugin_id in ("Weather", "weather_1", "1weather", "weather."):
        try:
            PluginMetadata(plugin_id, "Name", "Description", "0.4.0", 1)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected {plugin_id!r} to be rejected")

    for field in ("name", "description", "version"):
        values = dict(
            id="weather", name="Weather", description="Current weather", version="0.4.0", order=1
        )
        values[field] = "  "
        try:
            PluginMetadata(**values)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected empty {field} to be rejected")


def test_registry_sorts_by_order_then_id_and_rejects_duplicates() -> None:
    registry = PluginRegistry()
    registry.register(_spec("zeta", 20))
    registry.register(_spec("beta", 10))
    registry.register(_spec("alpha", 10))

    assert tuple(spec.metadata.id for spec in registry.all()) == ("alpha", "beta", "zeta")

    try:
        registry.register(_spec("alpha", 99))
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate plugin ids must be rejected")

    try:
        registry.register(object())  # type: ignore[arg-type]
    except TypeError:
        pass
    else:
        raise AssertionError("registry must only accept PluginSpec instances")


class _EntryPoint:
    def __init__(self, name: str, value: object | Exception) -> None:
        self.name = name
        self._value = value

    def load(self) -> object:
        if isinstance(self._value, Exception):
            raise self._value
        return self._value


def test_discovery_isolates_entry_point_load_factory_and_registration_failures(monkeypatch) -> None:
    good = _spec("good", 10)
    duplicate = _spec("good", 20)
    entry_points = (
        _EntryPoint("good", lambda: good),
        _EntryPoint("load-fails", RuntimeError("unavailable")),
        _EntryPoint("factory-fails", lambda: (_ for _ in ()).throw(RuntimeError("broken factory"))),
        _EntryPoint("wrong-type", lambda: object()),
        _EntryPoint("duplicate", duplicate),
    )
    calls: list[str] = []

    def fake_entry_points(*, group: str):
        calls.append(group)
        return entry_points

    monkeypatch.setattr("deskos.plugins.registry.metadata.entry_points", fake_entry_points)

    registry = PluginRegistry()
    registry.discover()

    assert calls == [ENTRY_POINT_GROUP]
    assert tuple(spec.metadata.id for spec in registry.all()) == ("good",)
    assert [(error.source, error.message) for error in registry.errors] == [
        ("load-fails", "unavailable"),
        ("factory-fails", "broken factory"),
        ("wrong-type", "plugin entry point must provide a PluginSpec"),
        ("duplicate", "duplicate plugin id: good"),
    ]


def test_discovery_records_global_entry_point_enumeration_failure(monkeypatch) -> None:
    def fake_entry_points(*, group: str):
        assert group == ENTRY_POINT_GROUP
        raise RuntimeError("metadata is unavailable")

    monkeypatch.setattr("deskos.plugins.registry.metadata.entry_points", fake_entry_points)

    registry = PluginRegistry()
    registry.discover()

    assert registry.all() == ()
    assert [(error.source, error.message) for error in registry.errors] == [
        (ENTRY_POINT_GROUP, "metadata is unavailable")
    ]
