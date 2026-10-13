from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata

from .api import PluginSpec

ENTRY_POINT_GROUP = "deskos.plugins"


@dataclass(frozen=True, slots=True)
class DiscoveryError:
    source: str
    message: str


class PluginRegistry:
    """Validated plugin specifications plus isolated discovery failures."""

    def __init__(self) -> None:
        self._specs: dict[str, PluginSpec] = {}
        self._errors: list[DiscoveryError] = []

    @property
    def errors(self) -> tuple[DiscoveryError, ...]:
        return tuple(self._errors)

    def register(self, spec: PluginSpec) -> None:
        if not isinstance(spec, PluginSpec):
            raise TypeError("plugin entry point must provide a PluginSpec")
        plugin_id = spec.metadata.id
        if plugin_id in self._specs:
            raise ValueError(f"duplicate plugin id: {plugin_id}")
        self._specs[plugin_id] = spec

    def get(self, plugin_id: str) -> PluginSpec:
        return self._specs[plugin_id]

    def all(self) -> tuple[PluginSpec, ...]:
        return tuple(
            sorted(self._specs.values(), key=lambda item: (item.metadata.order, item.metadata.id))
        )

    def discover(self) -> None:
        try:
            entry_points = metadata.entry_points(group=ENTRY_POINT_GROUP)
        except Exception as error:
            self._errors.append(DiscoveryError(ENTRY_POINT_GROUP, str(error)))
            return
        for entry_point in entry_points:
            source = getattr(entry_point, "name", repr(entry_point))
            try:
                loaded = entry_point.load()
                spec = (
                    loaded() if callable(loaded) and not isinstance(loaded, PluginSpec) else loaded
                )
                self.register(spec)
            except Exception as error:
                self._errors.append(DiscoveryError(str(source), str(error)))
