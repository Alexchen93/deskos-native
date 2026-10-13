"""DeskOS product UI theme for the 1024×600 Raspberry Pi display."""
# ruff: noqa: E501

from __future__ import annotations

CSS = b"""
window {
  background-color: #0d1218;
  color: #eef1f4;
  font-family: "Inter", "Noto Sans TC", "Noto Sans", sans-serif;
}

/* Compact, persistent product rail */
.sidebar {
  min-width: 132px;
  background-color: #111820;
  border-right: 1px solid #29313a;
  padding: 18px 10px 14px 10px;
}
.brand-title {
  color: #f4f1ec;
  font-size: 19px;
  font-weight: 800;
}
.brand-subtitle {
  color: #bd7a4a;
  font-size: 11px;
  font-weight: 700;
}
.nav-list { margin-top: 22px; }
.nav-button,
button.nav-button {
  min-height: 48px;
  padding: 0 12px;
  border: 0;
  border-left: 3px solid transparent;
  border-radius: 3px;
  background-color: transparent;
  background-image: none;
  color: #9da8b3;
  box-shadow: none;
}
button.nav-button:hover {
  background-color: #18212a;
  color: #f4f1ec;
}
button.nav-button.active {
  border-left-color: #c27a45;
  background-color: #1a222b;
  color: #ffffff;
}
.nav-label { font-size: 14px; font-weight: 700; }
.sidebar-status {
  min-height: 32px;
  padding: 6px 8px;
  border-top: 1px solid #29313a;
}
.status-dot { color: #65ad86; font-size: 12px; }
.status-label { color: #8995a0; font-size: 11px; font-weight: 600; }

/* Shared page structure */
.screen { padding: 18px 22px 18px 22px; }
.screen-header {
  min-height: 58px;
  padding-bottom: 12px;
  border-bottom: 1px solid #2b333c;
}
.screen-title { font-size: 24px; font-weight: 800; }
.screen-subtitle { color: #909ca7; font-size: 13px; }
.header-meta {
  color: #c58a60;
  font-size: 12px;
  font-weight: 700;
}
.header-clock {
  color: #f1eee9;
  font-size: 25px;
  font-weight: 700;
  font-feature-settings: "tnum";
}
.section-label {
  color: #b5bec7;
  font-size: 12px;
  font-weight: 700;
}
.panel {
  background-color: #141c24;
  border: 1px solid #2b3540;
  border-radius: 6px;
  padding: 16px;
}
.meta-label { color: #84919c; font-size: 12px; }
.data-label { color: #aab4bd; font-size: 13px; }
.data-value {
  color: #f1f3f5;
  font-size: 16px;
  font-weight: 700;
  font-feature-settings: "tnum";
}
.data-row {
  min-height: 48px;
  padding: 2px 0;
  border-bottom: 1px solid #29323b;
}
.state-good { color: #70b38f; }
.state-warn { color: #d39a65; }
.state-alert { color: #d87979; }
.warm-accent { color: #d18a55; }

/* Daily briefing */
.home-header { min-height: 66px; }
.home-greeting { font-size: 26px; font-weight: 800; }
button.briefing-weather {
  min-width: 310px;
  background-color: #171f27;
  background-image: none;
  border-left: 4px solid #c27a45;
  border-radius: 4px;
  padding: 18px;
  color: #eef1f4;
  box-shadow: none;
}
button.briefing-weather:hover { background-color: #1b252e; }
.home-weather-icon { color: #d6a56e; font-size: 38px; }
.home-temperature {
  color: #f5f2ed;
  font-size: 48px;
  font-weight: 700;
  font-feature-settings: "tnum";
}
.briefing-list {
  background-color: #131a21;
  border: 1px solid #29323b;
  border-radius: 4px;
  padding: 0 16px;
}
button.briefing-row {
  min-height: 76px;
  padding: 8px 0;
  border: 0;
  border-bottom: 1px solid #29323b;
  border-radius: 0;
  background-color: transparent;
  background-image: none;
  color: #eef1f4;
  box-shadow: none;
}
button.briefing-row:hover { background-color: #19222b; }
.briefing-title { color: #b3bdc6; font-size: 12px; font-weight: 700; }
.briefing-value {
  color: #f1f3f5;
  font-size: 18px;
  font-weight: 700;
}
.briefing-detail { color: #84919c; font-size: 12px; }
.briefing-arrow { color: #a46d47; font-size: 18px; }

/* Clock: one clear instrument, supporting calendar facts */
.clock-stage {
  background-color: #121920;
  border: 1px solid #303943;
  border-radius: 5px;
  padding: 22px 26px;
}
.clock-time {
  font-size: 76px;
  font-weight: 700;
  font-feature-settings: "tnum";
}
.clock-seconds {
  color: #c17e4e;
  font-size: 28px;
  font-weight: 700;
  font-feature-settings: "tnum";
}
.clock-date { color: #c7ced5; font-size: 18px; font-weight: 600; }
.clock-facts {
  background-color: #161e26;
  border-left: 1px solid #303943;
  padding: 10px 0 10px 18px;
}
progressbar trough {
  min-height: 6px;
  border-radius: 2px;
  background-color: #2a333c;
}
progressbar progress {
  min-height: 6px;
  border-radius: 2px;
  background-color: #bf7846;
}

/* Weather: observation plus aligned facts */
.weather-observation {
  background-color: #15202a;
  border-top: 3px solid #b97849;
  border-radius: 5px;
  padding: 20px;
}
.weather-icon { color: #d3a36f; font-size: 56px; }
.weather-temperature {
  font-size: 58px;
  font-weight: 700;
  font-feature-settings: "tnum";
}
.weather-condition { color: #d4d9de; font-size: 18px; font-weight: 700; }
.weather-advice {
  color: #d9b08c;
  font-size: 14px;
  font-weight: 700;
}
.weather-facts {
  min-width: 254px;
  background-color: #131a21;
  border: 1px solid #2b3540;
  border-radius: 5px;
  padding: 8px 16px;
}

/* Feed: editorial list, not cards */
.feed-list { background-color: transparent; }
.feed-list row { background-color: transparent; }
.feed-row {
  min-height: 62px;
  padding: 8px 12px;
  border-bottom: 1px solid #2b333c;
}
.feed-row:hover { background-color: #161f27; }
.feed-index {
  color: #b97849;
  font-size: 13px;
  font-weight: 800;
  font-feature-settings: "tnum";
}
.feed-title { color: #eef1f4; font-size: 15px; font-weight: 700; }
.feed-source { color: #85919c; font-size: 12px; }
.empty-state { color: #919da8; font-size: 15px; }

/* Focus: large timer with restrained controls */
.focus-stage {
  background-color: #151c23;
  border-left: 4px solid #bd7746;
  border-radius: 4px;
  padding: 24px;
}
.focus-time {
  font-size: 68px;
  font-weight: 700;
  font-feature-settings: "tnum";
}
.focus-mode { color: #d5b091; font-size: 14px; font-weight: 700; }
.focus-summary {
  min-width: 230px;
  padding: 10px 0 10px 18px;
  border-left: 1px solid #303943;
}
.focus-controls button {
  min-width: 108px;
  min-height: 50px;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 800;
}
button.primary-action {
  background-color: #b86f3f;
  background-image: none;
  color: #ffffff;
}
button.secondary-action {
  background-color: #27313b;
  background-image: none;
  color: #eef1f4;
}
button.danger-action {
  border: 1px solid #654747;
  background-color: transparent;
  background-image: none;
  color: #d99a9a;
}

/* Device: model workspace plus instrument table */
.model-shell {
  background-color: #10171e;
  border: 1px solid #2d3741;
  border-radius: 5px;
  padding: 10px;
}
.view-controls button {
  min-width: 72px;
  min-height: 44px;
  padding: 0 10px;
  border-radius: 3px;
  border: 1px solid #35414c;
  background-color: #1b242d;
  background-image: none;
  color: #d5dbe0;
  font-size: 12px;
  font-weight: 700;
}
.telemetry-panel {
  min-width: 270px;
  background-color: #131a21;
  border: 1px solid #2d3741;
  border-radius: 5px;
  padding: 6px 16px;
}
.telemetry-value {
  color: #f1f3f5;
  font-size: 15px;
  font-weight: 700;
  font-feature-settings: "tnum";
}
.fallback { color: #8d99a4; font-size: 13px; }
"""


def install_css() -> None:
    """Install CSS after GTK has been initialised."""
    from gi.repository import Gdk, Gtk

    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    display = Gdk.Display.get_default()
    if display is not None:
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
