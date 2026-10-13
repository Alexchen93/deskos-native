from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from deskos.ui.screens import (
    ClockScreen,
    DeviceMonitorScreen,
    FocusScreen,
    TechFeedScreen,
    WeatherScreen,
)

from .api import PluginMetadata, PluginSpec


def builtin_plugin_specs(
    *,
    model_path: Path,
    preview_path: Path,
    low_power: bool,
    use_24_hour_time: bool,
    focus_minutes: int,
    rest_minutes: int,
    on_focus_start: Callable[[], None] | None = None,
    on_focus_pause: Callable[[], None] | None = None,
    on_focus_reset: Callable[[], None] | None = None,
) -> Sequence[PluginSpec]:
    """Return the built-ins through exactly the same registry API as third-party apps."""

    return (
        PluginSpec(
            PluginMetadata("clock", "時鐘", "本機時間與日程進度", "0.4.0", 10),
            lambda _context: ClockScreen(use_24_hour=use_24_hour_time),
        ),
        PluginSpec(
            PluginMetadata("weather", "天氣", "目前天氣觀測", "0.4.0", 20),
            lambda _context: WeatherScreen(),
        ),
        PluginSpec(
            PluginMetadata("feed", "科技快訊", "RSS 與 Atom 科技動態", "0.4.0", 30),
            lambda _context: TechFeedScreen(),
        ),
        PluginSpec(
            PluginMetadata("focus", "專注", "本機專注與休息計時", "0.4.0", 40),
            lambda _context: FocusScreen(
                on_focus_start,
                on_focus_pause,
                on_focus_reset,
                focus_minutes=focus_minutes,
                rest_minutes=rest_minutes,
            ),
        ),
        PluginSpec(
            PluginMetadata("device", "裝置監測", "Raspberry Pi 即時狀態", "0.4.0", 50),
            lambda _context: DeviceMonitorScreen(model_path, preview_path, low_power),
        ),
    )
