# Changelog

## 0.5.0 — 2026-10-14

- Replaced the persistent navigation rail with a full-width, warm-light Widget Home designed for a 1024×600 touch display.
- Added an edge-triggered, overlay App Rail from either side of the screen; it scrolls vertically and never consumes Home content width.
- Added an explicit **Edit Home** button plus durable Widget ordering, standard/wide sizing, hiding, and restoring. Focus is hidden on a fresh Home layout but remains available to add back.
- Added a plugin Widget factory capability. Clock, Weather, Tech Feed, Focus, and Device Monitor now provide compact native Home previews that receive the same live events as their full-screen apps.
- Added local, downsampled SQLite histories and native Cairo sparklines: weather temperature samples every 20 minutes; CPU temperature and usage samples every minute. The charts appear on Home and their related full-screen pages.
- Reworked the visual language into task-specific light scenes for clock, weather, news, focus, and device monitoring.
- Expanded the test suite to 59 tests; Ruff, compileall, and live 1024×600 Raspberry Pi validation passed.

## 0.4.0 — 2026-10-13

- Rebuilt DeskOS around a native mini-app plugin platform.
- Added a frozen plugin API, validated registry, isolated Python entry-point discovery, and persistent enablement in SQLite.
- Converted Clock, Weather, Tech Feed, Focus, and Device Monitor into built-in plugins using the same API as third-party apps.
- Added a live App Library for adding and removing discovered apps without restarting DeskOS.
- Added a native Settings screen for weather, RSS, focus rhythm, clock format, and low-power 3D preferences.
- Added scrollable dynamic navigation and Home summaries that adapt when source apps are removed.
- Added plugin lifecycle, settings namespacing, retained event delivery, discovery-error reporting, and security documentation.
- Expanded the test suite to 52 tests and verified the add/remove/reinstall flow with GTK 4 on Raspberry Pi hardware.

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
