"""DeskOS light visual language for a 1024×600 information display."""
# ruff: noqa: E501

from __future__ import annotations

CSS = b"""
window {
  background-color: #f4f1ea;
  color: #243239;
  font-family: "Inter", "Noto Sans TC", "Noto Sans", sans-serif;
}

/* Widget home: nothing consumes space while the user is reading. */
.home-screen,
.screen {
  padding: 24px 32px;
  background-color: #f4f1ea;
}
.home-header {
  min-height: 58px;
  padding: 0 2px 10px 2px;
}
.home-greeting { color: #243239; font-size: 27px; font-weight: 800; }
.screen-title { color: #243239; font-size: 28px; font-weight: 800; }
.screen-subtitle { color: #71807d; font-size: 13px; }
.home-edit-done,
button.home-edit-done {
  min-width: 100px;
  min-height: 42px;
  border: 0;
  border-radius: 21px;
  background-color: #315f55;
  background-image: none;
  color: #ffffff;
  font-weight: 800;
}
.home-edit-start,
button.home-edit-start {
  min-width: 100px;
  min-height: 42px;
  border: 1px solid #a8c1b4;
  border-radius: 21px;
  background-color: #fffdfa;
  background-image: none;
  color: #315f55;
  font-weight: 800;
}
button.home-edit-start:hover { background-color: #edf4ef; }
.home-widget-grid { margin: 2px 0 12px 0; }
.home-widget-shell { min-height: 164px; }
.home-widget-shell.widget-wide { min-height: 184px; }
button.home-widget {
  min-height: 164px;
  padding: 16px 18px;
  border: 1px solid #e4dfd4;
  border-radius: 22px;
  background-color: #fffdfa;
  background-image: none;
  color: #243239;
  box-shadow: 0 9px 24px rgba(44, 60, 54, 0.08);
}
button.home-widget:hover { border-color: #9bb7ab; background-color: #ffffff; }
button.home-widget:disabled { opacity: 1; }
.widget-edit-controls { margin: 10px; }
.widget-edit-control,
button.widget-edit-control {
  min-width: 34px;
  min-height: 34px;
  padding: 0;
  border: 0;
  border-radius: 17px;
  background-color: #315f55;
  background-image: none;
  color: #ffffff;
  font-weight: 800;
}
.hidden-widgets {
  padding: 14px;
  border: 1px dashed #b8c8be;
  border-radius: 16px;
  background-color: #edf4ef;
}
.hidden-widgets-title { color: #4f6e62; font-size: 13px; font-weight: 800; }
.restore-widget,
button.restore-widget {
  min-height: 36px;
  border: 0;
  border-radius: 18px;
  background-color: #d9e9e0;
  background-image: none;
  color: #315f55;
  font-weight: 800;
}

/* Each home App preview owns its small visual moment. */
.home-widget-preview { min-width: 0; }
.home-widget-title { color: #70827d; font-size: 12px; font-weight: 800; }
.home-widget-value { color: #26363a; font-size: 38px; font-weight: 800; font-feature-settings: "tnum"; }
.home-widget-detail { color: #76847f; font-size: 12px; }
.home-widget-trend-label { color: #88958f; font-size: 10px; font-weight: 800; }
.home-widget-clock .home-widget-value { font-size: 45px; }
.home-widget-weather .home-widget-value { color: #8e6723; }
.home-widget-focus .home-widget-value { color: #9b5145; }
.home-widget-device .home-widget-value { font-size: 22px; color: #376251; }
.home-widget-feed .home-widget-value { font-size: 17px; }
.fallback-widget .widget-title { color: #26363a; font-size: 19px; font-weight: 800; }
.fallback-widget .widget-detail { color: #76847f; font-size: 12px; }

/* Temporary edge App Rail: overlays instead of shrinking the active page. */
.app-rail-layer { background-color: transparent; }
.app-rail-scrim { background-color: rgba(29, 39, 40, 0.48); }
.app-rail-panel {
  min-width: 300px;
  padding: 22px 18px 16px 18px;
  background-color: #fffdfa;
  border-right: 1px solid #e1ddd2;
  box-shadow: 12px 0 30px rgba(32, 45, 41, 0.16);
}
.rail-title { color: #243239; font-size: 23px; font-weight: 800; }
.rail-close,
button.rail-close {
  min-width: 36px;
  min-height: 36px;
  padding: 0;
  border: 0;
  border-radius: 18px;
  background-color: #edf2ed;
  background-image: none;
  color: #456458;
  font-size: 20px;
  font-weight: 600;
}
.rail-divider { margin: 12px 8px 4px 8px; color: #8b9691; font-size: 11px; font-weight: 800; }
.rail-item,
button.rail-item {
  min-height: 64px;
  padding: 10px 12px;
  border: 0;
  border-radius: 14px;
  background-color: transparent;
  background-image: none;
  color: #26363a;
  box-shadow: none;
}
button.rail-item:hover { background-color: #edf4ef; }
button.rail-item.rail-app { background-color: #f7faf7; }
.rail-item-title { color: #31473f; font-size: 15px; font-weight: 800; }
.rail-item-detail { color: #7c8984; font-size: 11px; }
.rail-hint { margin-top: 6px; color: #83908a; font-size: 11px; }

/* Shared full-screen application structure. */
.screen-header {
  min-height: 60px;
  padding-bottom: 12px;
  border-bottom: 1px solid #dfddd4;
}
.header-meta { color: #687c75; font-size: 12px; font-weight: 800; }
.header-clock { color: #2d5f55; font-size: 25px; font-weight: 800; font-feature-settings: "tnum"; }
.section-label { color: #62746e; font-size: 12px; font-weight: 800; }
.panel { background-color: #fffdfa; border: 1px solid #e5e1d7; border-radius: 18px; padding: 16px; }
.meta-label { color: #7c8984; font-size: 12px; }
.data-label { color: #71807c; font-size: 13px; }
.data-value { color: #27373a; font-size: 16px; font-weight: 800; font-feature-settings: "tnum"; }
.data-row { min-height: 48px; padding: 2px 0; border-bottom: 1px solid #ece8df; }
.state-good { color: #4d8167; }
.state-warn { color: #b4773d; }
.state-alert { color: #bc5e5e; }
.warm-accent { color: #d8795d; }

/* Clock becomes a quiet typographic stage. */
.clock-stage { background-color: #e3eef0; border: 0; border-radius: 28px; padding: 28px; }
.clock-time { color: #26434a; font-size: 76px; font-weight: 800; font-feature-settings: "tnum"; }
.clock-seconds { color: #d8795d; font-size: 28px; font-weight: 800; font-feature-settings: "tnum"; }
.clock-date { color: #52717a; font-size: 18px; font-weight: 700; }
.clock-facts { background-color: rgba(255,255,255,0.56); border-left: 0; border-radius: 18px; padding: 16px; }
progressbar trough { min-height: 7px; border-radius: 4px; background-color: #d7e1de; }
progressbar progress { min-height: 7px; border-radius: 4px; background-color: #5d9580; }

/* Weather owns a cool sky palette. */
.weather-observation { background-color: #cde6ea; border: 0; border-radius: 28px; padding: 28px; }
.weather-icon { color: #f3bd4f; font-size: 60px; }
.weather-temperature { color: #28434c; font-size: 60px; font-weight: 800; font-feature-settings: "tnum"; }
.weather-condition { color: #385b64; font-size: 19px; font-weight: 800; }
.weather-advice { color: #597a72; font-size: 14px; font-weight: 800; }
.weather-facts { min-width: 254px; background-color: #f9fdfd; border: 0; border-radius: 22px; padding: 12px 18px; }

/* Editorial reading instead of a dark feed dashboard. */
.feed-list { background-color: #fffdfa; border: 1px solid #e4dfd4; border-radius: 20px; }
.feed-list row { background-color: transparent; }
.feed-row { min-height: 62px; padding: 8px 14px; border-bottom: 1px solid #eee9df; }
.feed-row:hover { background-color: #f4f8f4; }
.feed-index { color: #d8795d; font-size: 13px; font-weight: 800; font-feature-settings: "tnum"; }
.feed-title { color: #2c3d3d; font-size: 15px; font-weight: 800; }
.feed-source { color: #7c8984; font-size: 12px; }
.empty-state { color: #84918d; font-size: 15px; }

/* Focus uses a warm calm surface. */
.focus-stage { background-color: #fae8dc; border-left: 0; border-radius: 28px; padding: 30px; }
.focus-time { color: #774b42; font-size: 70px; font-weight: 800; font-feature-settings: "tnum"; }
.focus-mode { color: #a15d4e; font-size: 14px; font-weight: 800; }
.focus-summary { min-width: 230px; padding: 12px 0 12px 18px; border-left: 1px solid #e8cdbd; }
.focus-controls button { min-width: 108px; min-height: 50px; border-radius: 25px; font-size: 14px; font-weight: 800; }
button.primary-action { background-color: #c86e55; background-image: none; color: #ffffff; border: 0; }
button.secondary-action { background-color: #f4d8c8; background-image: none; color: #75483e; border: 0; }
button.danger-action { border: 1px solid #d9aaa0; background-color: transparent; background-image: none; color: #a95f58; }

/* Device is intentionally technical but still part of the light system. */
.model-shell { background-color: #e6f0e9; border: 0; border-radius: 24px; padding: 12px; }
.view-controls button { min-width: 72px; min-height: 44px; padding: 0 10px; border: 0; border-radius: 22px; background-color: #d0e4d7; background-image: none; color: #315f55; font-size: 12px; font-weight: 800; }
.telemetry-panel { min-width: 270px; background-color: #fffdfa; border: 1px solid #e0e8e0; border-radius: 22px; padding: 8px 16px; }
.telemetry-value { color: #28423b; font-size: 15px; font-weight: 800; font-feature-settings: "tnum"; }
.fallback { color: #788781; font-size: 13px; }

/* App management and settings remain deliberate system screens. */
.library-list { background-color: #fffdfa; border: 1px solid #e4dfd4; border-radius: 20px; }
.library-row { min-height: 74px; padding: 10px 14px; border-bottom: 1px solid #ece8df; }
.library-title { color: #2c3d3d; font-size: 15px; font-weight: 800; }
.library-status { color: #c86e55; font-size: 11px; font-weight: 800; }
.library-version { color: #8a9690; font-size: 11px; }
button.library-action { min-width: 104px; min-height: 48px; border-radius: 24px; font-size: 13px; font-weight: 800; }
.settings-form { padding: 4px 2px 16px 2px; }
.settings-form > box { min-height: 48px; }
.settings-label { color: #50645d; font-size: 13px; font-weight: 800; }
.settings-form entry, .settings-form spinbutton { min-height: 42px; border: 1px solid #dfe3da; border-radius: 12px; background-color: #fffdfa; color: #293a39; }
.settings-toggle { min-height: 48px; color: #3a514a; }
button.settings-save { min-width: 132px; min-height: 48px; margin-top: 4px; border-radius: 24px; font-weight: 800; }
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
