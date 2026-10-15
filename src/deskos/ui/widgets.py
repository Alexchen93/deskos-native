"""Compact, event-driven previews for the configurable DeskOS home screen."""
# ruff: noqa: E402

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from deskos.core.models import FeedItem, FocusState, TelemetrySnapshot, WeatherSnapshot
from deskos.plugins.api import PluginEvent
from deskos.services.history import HistorySample
from deskos.settings import DeskOSSettings

from .charts import Sparkline
from .formatters import duration, percent, temperature


def _label(text: str, css_class: str, **kwargs: object) -> Gtk.Label:
    label = Gtk.Label(label=text, **kwargs)
    label.add_css_class(css_class)
    return label


def _weather_presentation(code: int | None) -> tuple[str, str]:
    if code is None:
        return "○", "等待天氣資料"
    if code == 0:
        return "☀", "晴朗"
    if code in {1, 2}:
        return "◐", "晴時多雲"
    if code == 3:
        return "☁", "多雲"
    if code in {45, 48}:
        return "≋", "有霧"
    if code in {51, 53, 55, 56, 57}:
        return "☂", "毛毛雨"
    if code in {61, 63, 65, 66, 67, 80, 81, 82}:
        return "☔", "有雨"
    if code in {71, 73, 75, 77, 85, 86}:
        return "❄", "降雪"
    if code in {95, 96, 99}:
        return "ϟ", "雷雨"
    return "○", "天氣變化中"


class _HomeWidget(Gtk.Box):
    """Shared compact layout and CSS vocabulary for plugin-provided previews."""

    def __init__(self, widget_class: str, title: str) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add_css_class("home-widget-preview")
        self.add_css_class(widget_class)
        self.append(_label(title, "home-widget-title", xalign=0))

    def _value(self, text: str = "—") -> Gtk.Label:
        value = _label(text, "home-widget-value", xalign=0)
        self.append(value)
        return value

    def _detail(self, text: str) -> Gtk.Label:
        detail = _label(text, "home-widget-detail", xalign=0, wrap=True, lines=2)
        self.append(detail)
        return detail


class ClockHomeWidget(_HomeWidget):
    def __init__(self, *, use_24_hour: bool = True) -> None:
        super().__init__("home-widget-clock", "時鐘")
        self._use_24_hour = use_24_hour
        self._time = self._value("--:--")
        self._date = self._detail("本機時間")
        self.update_time(datetime.now())
        GLib.timeout_add_seconds(30, self._tick)

    def _tick(self) -> bool:
        self.update_time(datetime.now())
        return True

    def update_time(self, moment: datetime) -> None:
        format_string = "%H:%M" if self._use_24_hour else "%I:%M %p"
        self._time.set_label(moment.strftime(format_string))
        self._date.set_label(moment.strftime("%Y 年 %m 月 %d 日"))

    def on_plugin_event(self, event: PluginEvent) -> None:
        if event.topic == "settings" and isinstance(event.payload, DeskOSSettings):
            self._use_24_hour = event.payload.use_24_hour_time
            self.update_time(datetime.now())


class WeatherHomeWidget(_HomeWidget):
    def __init__(self) -> None:
        super().__init__("home-widget-weather", "天氣")
        self._summary = self._value("—")
        self._detail_label = self._detail("等待天氣資料")
        self.append(_label("溫度趨勢", "home-widget-trend-label", xalign=0))
        self._trend = Sparkline(height=22)
        self.append(self._trend)

    def update_weather(self, snapshot: WeatherSnapshot) -> None:
        icon, condition = _weather_presentation(snapshot.weather_code)
        self._summary.set_label(f"{icon}  {temperature(snapshot.temperature_c)}")
        self._detail_label.set_label(f"{snapshot.location or '目前位置'} · {condition}")

    def on_plugin_event(self, event: PluginEvent) -> None:
        if event.topic == "weather" and isinstance(event.payload, WeatherSnapshot):
            self.update_weather(event.payload)
        elif event.topic == "weather_history" and isinstance(event.payload, Sequence):
            self._trend.set_samples(_history_samples(event.payload))


class TechFeedHomeWidget(_HomeWidget):
    def __init__(self) -> None:
        super().__init__("home-widget-feed", "科技快訊")
        self._headline = self._value("等待新聞更新")
        self._source = self._detail("稍後自動更新")

    def update_feed(self, items: Sequence[FeedItem]) -> None:
        item = next((item for item in items if isinstance(item, FeedItem)), None)
        if item is None:
            self._headline.set_label("目前沒有科技快訊")
            self._source.set_label("稍後再回來看看")
            return
        self._headline.set_label(item.title or "未命名快訊")
        published = item.published_at.strftime("%H:%M") if item.published_at else "最新"
        self._source.set_label(f"{item.source or '科技快訊'} · {published}")

    def on_plugin_event(self, event: PluginEvent) -> None:
        if (
            event.topic == "feed"
            and isinstance(event.payload, Sequence)
            and not isinstance(event.payload, (str, bytes))
        ):
            self.update_feed(event.payload)


class FocusHomeWidget(_HomeWidget):
    def __init__(self, *, focus_minutes: int = 25, rest_minutes: int = 5) -> None:
        super().__init__("home-widget-focus", "專注")
        self._focus_minutes = focus_minutes
        self._rest_minutes = rest_minutes
        self._remaining = self._value(f"{focus_minutes:02d}:00")
        self._state = self._detail("已暫停 · 完成 0 次")

    def update_focus(self, state: FocusState) -> None:
        mode = "專注" if state.mode == "focus" else "休息"
        status = "進行中" if state.running else "已暫停"
        self._remaining.set_label(duration(state.remaining_seconds))
        self._state.set_label(f"{mode} · {status} · 完成 {state.completed_sessions} 次")

    def on_plugin_event(self, event: PluginEvent) -> None:
        if event.topic == "focus" and isinstance(event.payload, FocusState):
            self.update_focus(event.payload)
        elif event.topic == "settings" and isinstance(event.payload, DeskOSSettings):
            self._focus_minutes = event.payload.focus_minutes
            self._rest_minutes = event.payload.rest_minutes


class DeviceHomeWidget(_HomeWidget):
    def __init__(self) -> None:
        super().__init__("home-widget-device", "裝置監測")
        self._summary = self._value("CPU — · 溫度 —")
        self._detail_label = self._detail("記憶體 —")
        self.append(_label("CPU 溫度", "home-widget-trend-label", xalign=0))
        self._temperature_trend = Sparkline(height=18)
        self.append(_label("CPU 使用率", "home-widget-trend-label", xalign=0))
        self._usage_trend = Sparkline(height=18)
        self.append(self._temperature_trend)
        self.append(self._usage_trend)

    def update_telemetry(self, snapshot: TelemetrySnapshot) -> None:
        self._summary.set_label(
            f"CPU {percent(snapshot.cpu_percent)} · 溫度 {temperature(snapshot.cpu_temp_c)}"
        )
        hostname = snapshot.hostname or "本機"
        self._detail_label.set_label(f"{hostname} · 記憶體 {percent(snapshot.memory_percent)}")

    def on_plugin_event(self, event: PluginEvent) -> None:
        if event.topic == "telemetry" and isinstance(event.payload, TelemetrySnapshot):
            self.update_telemetry(event.payload)
        elif event.topic == "cpu_temperature_history" and isinstance(event.payload, Sequence):
            self._temperature_trend.set_samples(_history_samples(event.payload))
        elif event.topic == "cpu_usage_history" and isinstance(event.payload, Sequence):
            self._usage_trend.set_samples(_history_samples(event.payload))


def _history_samples(values: Sequence[object]) -> tuple[HistorySample, ...]:
    return tuple(value for value in values if isinstance(value, HistorySample))
