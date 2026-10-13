# Changelog

## 0.2.0 — 2026-10-13

- Rebuilt the shell for the Raspberry Pi's actual 1024×600 output and fixed Labwc fullscreen sizing.
- Replaced the monochrome launcher with a persistent six-destination touch sidebar.
- Added a colorful semantic palette for weather, focus, telemetry, news and time.
- Reworked Home into a live dashboard with weather, focus, CPU, temperature, memory and headline summaries.
- Redesigned Clock, Weather, Tech Feed, Focus and Device Monitor with dedicated responsive layouts.
- Added Chinese weekday presentation and polished loading/empty states.
- Added a start-page diagnostic override for Raspberry Pi visual acceptance testing.
- Verified 28 tests and live screenshots of Home, Weather, Focus, Feed and Device Monitor on the Pi.

## 0.1.0 — 2026-10-12

Initial native DeskOS implementation.

- Added an 800×480 GTK 4 touch interface with status bar, 2×3 launcher, stack navigation and persistent Home/Back dock.
- Added Clock & Daily, Weather, Tech Feed, Focus and Device Monitor screens.
- Added a timestamp-based Focus timer persisted in SQLite.
- Added Open-Meteo and RSS/Atom background adapters with bounded responses and last-good caches.
- Added psutil CPU, memory, disk, network, uptime and Linux temperature monitoring with 30 minutes of in-memory history.
- Added a native `Gtk.GLArea` Raspberry Pi 4 renderer that reads all 113 GLB triangle batches, applies scene transforms and material colors, and supports rotation, zoom and Top/Front/Right/Iso views.
- Added a static Pi preview fallback for unsupported OpenGL contexts.
- Added Raspberry Pi graphical-session deployment guidance.
- Explicitly excluded HTTP servers, WebViews, browser shells and VPN endpoints from the application runtime.
