# DeskOS Plugin System

DeskOS v0.4 treats its optional applications as plugins. The bundled Clock, Weather,
Tech Feed, Focus, and Device Monitor applications use the same registry as
third-party plugins. The DeskOS shell itself owns the **Home**, **App Library**,
and **Settings** pages; those core pages are not plugins.

## Package and discovery

A plugin is a normal, already-installed Python distribution that advertises one
entry point in the `deskos.plugins` group. The entry point may resolve directly
to a `PluginSpec`, or to a zero-argument callable that returns a `PluginSpec`.

Minimal package layout:

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"

[project]
name = "deskos-example"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["deskos-native"]

[project.entry-points."deskos.plugins"]
example = "deskos_example.plugin:plugin_spec"
```

```python
# src/deskos_example/plugin.py
from gi.repository import Gtk

from deskos.plugins import PluginContext, PluginMetadata, PluginSpec


class ExampleScreen(Gtk.Box):
    def __init__(self, context: PluginContext) -> None:
        super().__init__()
        self.append(Gtk.Label(label="Hello from a plugin"))


def plugin_spec() -> PluginSpec:
    return PluginSpec(
        metadata=PluginMetadata(
            id="example",
            name="Example",
            description="A minimal DeskOS plugin",
            version="0.1.0",
            order=100,
        ),
        create_screen=ExampleScreen,
    )
```

Plugin IDs must start with a lowercase letter and may contain lowercase letters,
digits, dots, and hyphens. IDs are unique across built-in and discovered plugins.
`order` controls App Library and navigation order, then the ID breaks ties.

## API contract

`PluginMetadata`, `PluginEvent`, `PluginContext`, and `PluginSpec` are frozen,
slotted dataclasses. Treat them as immutable values.

- `PluginMetadata(id, name, description, version, order)` describes the app.
  `name`, `description`, and `version` must not be empty.
- `PluginSpec(metadata, create_screen, on_install=None, on_remove=None)` is the
  complete registration. `create_screen(context)` must return a `Gtk.Widget`.
- `PluginContext` is the intentionally small capability surface:
  - `navigate(page_id)` moves to a mounted DeskOS page or plugin.
  - `dispatch(PluginEvent(topic, payload))` broadcasts an event through the
    DeskOS window.
  - `get_setting(key, default=None)` and `set_setting(key, value)` read and
    write persistent plugin settings. Keys are namespaced automatically as
    `plugin.<plugin-id>.<key>`.
- `PluginEvent(topic, payload)` carries a non-empty topic and any payload.

A plugin screen can implement `on_plugin_event(event)`. DeskOS delivers each
dispatched event to every installed plugin screen and retains the latest event
per topic; newly mounted screens receive those retained events immediately.
Choose namespaced, stable topics such as `example.status` to avoid collisions.

## Screen lifecycle

Screen factories are called when DeskOS mounts a plugin. A screen may implement
these optional, no-argument hooks:

- `on_activate()` — called after the plugin becomes the visible screen.
- `on_deactivate()` — called when it stops being visible or is removed.
- `on_plugin_event(event)` — receives the event stream described above.

Hooks are duck-typed; no base class is required. Screens start inactive and
must defer expensive rendering or polling until `on_activate()`. Keep GTK work
on the GTK main loop, and ensure deactivation stops resources the screen owns.

## Enablement is not package installation

DeskOS discovers Python packages that are already present in the environment.
The App Library's **Install** and **Remove** controls only enable or disable a
discovered plugin locally; they do not install or uninstall a Python package.
The enabled plugin ID list is persisted in SQLite under `plugins.installed_ids`.

When a plugin is enabled, DeskOS mounts its screen and calls `on_install(context)`
if supplied. When disabled, DeskOS unmounts the screen and calls
`on_remove(context)` if supplied. Re-enabling creates a fresh screen instance.

Disabling preserves data by default. In particular, DeskOS never deletes the
plugin's namespaced SQLite settings. A plugin should therefore make
`on_install` and `on_remove` safe to repeat and should not delete user data from
`on_remove` unless it has an explicit, separately confirmed user-facing action.

## Discovery and runtime errors

Discovery is isolated per entry point. If the entry-point query, import, factory
call, validation, or duplicate-ID check fails, DeskOS records a `DiscoveryError`
with the entry-point source and message, then continues discovering other
plugins. App Library shows those errors instead of preventing DeskOS from
starting.

A screen-factory failure is similarly isolated: App Library shows the plugin
with its error, but its screen is not mounted or enabled. Fix the package and
restart DeskOS to retry discovery.

## Security boundary

DeskOS does **not** download code, install Python packages, invoke `pip`, or
execute shell commands on behalf of plugins. App Library is an enablement UI,
not a package manager.

Python imports execute code. Consequently, every installed package advertising a
`deskos.plugins` entry point is trusted code with the permissions of the DeskOS
process. Only install plugin distributions from sources you trust, and review
updates through the operating system or the Python environment's normal package
management process before launching DeskOS.
