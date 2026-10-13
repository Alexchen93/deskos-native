# DeskOS Native Architecture

## Product boundary

DeskOS is a local native GTK 4 application shown directly on a Raspberry Pi-connected display. It is not a website, does not embed a browser, does not run an HTTP server, and does not expose a VPN endpoint.

## Runtime

- Python 3.11+
- GTK 4 through PyGObject (`python3-gi` and `gir1.2-gtk-4.0` from the OS)
- One application process, one GTK main loop
- `Gtk.Stack`-based navigation for a 1024×600 touch display
- `Gtk.GLArea` for the Raspberry Pi model, with a static PNG fallback if OpenGL or model loading fails
- Background I/O through worker threads; UI updates return through GLib idle callbacks
- SQLite for settings/cache; high-frequency telemetry stays in memory

## Ownership boundaries

- `src/deskos/ui/**`: widgets, screens, CSS, navigation, OpenGL model viewer
- `src/deskos/services/**`: telemetry, weather/RSS adapters, focus timer, SQLite storage
- `src/deskos/core/**`: shared dataclasses and stable contracts; integration owner only
- `src/deskos/app.py`, `src/deskos/main.py`: integration owner only
- `tests/**`: tests may be added by the owning layer; integration owner resolves shared fixtures

## Contracts

UI consumes immutable dataclasses from `deskos.core.models` and service protocols from `deskos.core.contracts`. Services never import GTK. UI must not perform blocking file or network I/O on the GTK main loop.

## Performance rules

- Telemetry sample every 2 seconds; keep at most 30 minutes in memory.
- SQLite receives settings, cached external content, events, and optional one-minute aggregates only.
- Render 3D only while the Device screen is visible. Target 30 FPS and drop to 15 FPS on low-power mode.
- If the OpenGL context is unavailable, show the provided static Pi preview beside live telemetry; never invent values.
