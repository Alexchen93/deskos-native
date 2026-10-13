"""DeskOS screen widgets; immutable application data enters through update methods."""
# ruff: noqa: E402

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from deskos.core.models import FeedItem, FocusState, TelemetrySnapshot, WeatherSnapshot

from .device import DeviceModelView
from .formatters import duration, freshness_label, human_bytes, percent, temperature

WEEKDAYS = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")


def _label(text: str = "", css: str | None = None, **kwargs: object) -> Gtk.Label:
    label = Gtk.Label(label=text, **kwargs)
    if css:
        label.add_css_class(css)
    return label


def _page_header(title: str, subtitle: str, *, right_text: str = "") -> tuple[Gtk.Box, Gtk.Label]:
    header = Gtk.Box(spacing=16)
    header.add_css_class("screen-header")
    copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
    copy.append(_label(title, "screen-title", xalign=0))
    copy.append(_label(subtitle, "screen-subtitle", xalign=0))
    header.append(copy)
    right = _label(right_text, "header-meta", valign=Gtk.Align.CENTER)
    header.append(right)
    return header, right


def _data_row(
    parent: Gtk.Box,
    title: str,
    *,
    initial: str = "—",
    value_class: str = "data-value",
) -> Gtk.Label:
    row = Gtk.Box(spacing=12)
    row.add_css_class("data-row")
    row.append(_label(title, "data-label", xalign=0, hexpand=True, valign=Gtk.Align.CENTER))
    value = _label(initial, value_class, xalign=1, valign=Gtk.Align.CENTER)
    row.append(value)
    parent.append(row)
    return value


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


def _weather_advice(snapshot: WeatherSnapshot) -> str:
    if snapshot.precipitation_probability is not None:
        if snapshot.precipitation_probability >= 60:
            return "外出記得帶傘"
        if snapshot.precipitation_probability >= 30:
            return "午後留意短暫雨"
    if snapshot.temperature_c is None:
        return "資料更新後提供建議"
    if snapshot.temperature_c >= 30:
        return "炎熱，記得補充水分"
    if snapshot.temperature_c <= 18:
        return "偏涼，出門多帶一件"
    return "適合安排戶外活動"


class HomeScreen(Gtk.Box):
    """Daily briefing with one primary observation and a compact action list."""

    def __init__(self, on_navigate: Callable[[str], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.add_css_class("screen")
        self._on_navigate = on_navigate

        header = Gtk.Box(spacing=16)
        header.add_css_class("home-header")
        greeting = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        self._greeting = _label("早安", "home-greeting", xalign=0)
        greeting.append(self._greeting)
        self._date = _label("", "screen-subtitle", xalign=0)
        greeting.append(self._date)
        header.append(greeting)
        self._home_clock = _label("--:--", "header-clock", valign=Gtk.Align.CENTER)
        header.append(self._home_clock)
        self.append(header)

        body = Gtk.Box(spacing=14, vexpand=True)
        weather_button = Gtk.Button(width_request=318, hexpand=False, vexpand=True)
        weather_button.add_css_class("briefing-weather")
        weather_button.connect("clicked", lambda _button: self._on_navigate("weather"))
        weather = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        weather.append(_label("現在天氣", "section-label", xalign=0))
        current = Gtk.Box(spacing=14, valign=Gtk.Align.CENTER, vexpand=True)
        self._weather_icon = _label("○", "home-weather-icon")
        current.append(self._weather_icon)
        current_copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._weather_temperature = _label("—", "home-temperature", xalign=0)
        self._weather_location = _label("等待更新", "data-label", xalign=0)
        current_copy.append(self._weather_temperature)
        current_copy.append(self._weather_location)
        current.append(current_copy)
        weather.append(current)
        self._weather_detail = _label("體感 —  ·  降雨 —", "meta-label", xalign=0)
        weather.append(self._weather_detail)
        weather_button.set_child(weather)
        body.append(weather_button)

        briefing = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
            hexpand=True,
            valign=Gtk.Align.START,
        )
        briefing.add_css_class("briefing-list")
        briefing.append(_label("今日摘要", "section-label", xalign=0, margin_top=12))
        self._focus_time, self._focus_detail = self._briefing_row(
            briefing,
            "focus",
            "專注計時",
            "25:00",
            "已暫停 · 今天完成 0 次",
        )
        self._system_value, self._system_detail = self._briefing_row(
            briefing,
            "device",
            "裝置狀態",
            "CPU —  ·  溫度 —",
            "記憶體 —",
        )
        self._feed_title, self._feed_source = self._briefing_row(
            briefing,
            "feed",
            "最新科技快訊",
            "等待新聞更新",
            "稍後自動更新",
            wrap=True,
        )
        body.append(briefing)
        self.append(body)

        self.update_time(datetime.now())
        GLib.timeout_add_seconds(30, self._tick)

    def _briefing_row(
        self,
        parent: Gtk.Box,
        page: str,
        title: str,
        value: str,
        detail: str,
        *,
        wrap: bool = False,
    ) -> tuple[Gtk.Label, Gtk.Label]:
        button = Gtk.Button(hexpand=True)
        button.add_css_class("briefing-row")
        button.connect("clicked", lambda _button: self._on_navigate(page))
        row = Gtk.Box(spacing=12)
        copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        copy.append(_label(title, "briefing-title", xalign=0))
        value_label = _label(value, "briefing-value", xalign=0, wrap=wrap, lines=2)
        copy.append(value_label)
        detail_label = _label(detail, "briefing-detail", xalign=0)
        copy.append(detail_label)
        row.append(copy)
        row.append(_label("›", "briefing-arrow", valign=Gtk.Align.CENTER))
        button.set_child(row)
        parent.append(button)
        return value_label, detail_label

    def _tick(self) -> bool:
        self.update_time(datetime.now())
        return True

    def update_time(self, moment: datetime) -> None:
        hour = moment.hour
        greeting = "早安" if hour < 12 else "午安" if hour < 18 else "晚安"
        self._greeting.set_label(greeting)
        self._date.set_label(f"{moment:%Y 年 %m 月 %d 日}  {WEEKDAYS[moment.weekday()]}")
        self._home_clock.set_label(moment.strftime("%H:%M"))

    def update_weather(self, snapshot: WeatherSnapshot) -> None:
        icon, condition = _weather_presentation(snapshot.weather_code)
        self._weather_icon.set_label(icon)
        self._weather_location.set_label(f"{snapshot.location} · {condition}")
        self._weather_temperature.set_label(temperature(snapshot.temperature_c))
        self._weather_detail.set_label(
            f"體感 {temperature(snapshot.apparent_temperature_c)}  ·  "
            f"降雨 {percent(snapshot.precipitation_probability)}"
        )

    def update_focus(self, state: FocusState) -> None:
        mode = "專注" if state.mode == "focus" else "休息"
        status = "進行中" if state.running else "已暫停"
        self._focus_time.set_label(duration(state.remaining_seconds))
        self._focus_detail.set_label(f"{mode} · {status} · 完成 {state.completed_sessions} 次")

    def update_telemetry(self, snapshot: TelemetrySnapshot) -> None:
        self._system_value.set_label(
            f"CPU {percent(snapshot.cpu_percent)}  ·  溫度 {temperature(snapshot.cpu_temp_c)}"
        )
        hostname = snapshot.hostname or "本機"
        self._system_detail.set_label(f"{hostname} · 記憶體 {percent(snapshot.memory_percent)}")

    def update_feed(self, items: Sequence[FeedItem]) -> None:
        if not items:
            self._feed_title.set_label("目前沒有科技快訊")
            self._feed_source.set_label("稍後再回來看看")
            return
        item = items[0]
        self._feed_title.set_label(item.title)
        published = item.published_at.strftime("%H:%M") if item.published_at else "最新"
        self._feed_source.set_label(f"{item.source} · {published}")


class ClockScreen(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.add_css_class("screen")
        header, self._status = _page_header("時鐘", "本機時間與日程進度", right_text="本機時間")
        self.append(header)

        stage = Gtk.Box(spacing=20, vexpand=True)
        stage.add_css_class("clock-stage")
        clock = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            hexpand=True,
            valign=Gtk.Align.CENTER,
        )
        time_row = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER)
        self._time = _label("--:--", "clock-time", xalign=0)
        self._seconds = _label(":--", "clock-seconds", valign=Gtk.Align.END)
        time_row.append(self._time)
        time_row.append(self._seconds)
        clock.append(time_row)
        self._date = _label("", "clock-date", xalign=0)
        clock.append(self._date)
        self._day_progress = Gtk.ProgressBar(show_text=False, hexpand=True)
        clock.append(self._day_progress)
        self._day_label = _label("", "meta-label", xalign=0)
        clock.append(self._day_label)
        stage.append(clock)

        facts = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
            width_request=220,
            valign=Gtk.Align.CENTER,
        )
        facts.add_css_class("clock-facts")
        facts.append(_label("日曆", "section-label", xalign=0, margin_bottom=8))
        self._weekday = _data_row(facts, "今天")
        self._week = _data_row(facts, "本年第幾週")
        self._year = _data_row(facts, "年度進度")
        stage.append(facts)
        self.append(stage)

        self.update_time(datetime.now())
        GLib.timeout_add_seconds(1, self._tick)

    def _tick(self) -> bool:
        self.update_time(datetime.now())
        return True

    def update_time(self, moment: datetime) -> None:
        self._time.set_label(moment.strftime("%H:%M"))
        self._seconds.set_label(moment.strftime(":%S"))
        self._date.set_label(moment.strftime("%Y 年 %m 月 %d 日"))
        seconds = moment.hour * 3600 + moment.minute * 60 + moment.second
        self._day_progress.set_fraction(seconds / 86_400)
        self._day_label.set_label(f"今天已經過 {seconds / 864:.0f}%")
        self._weekday.set_label(WEEKDAYS[moment.weekday()])
        self._week.set_label(f"第 {moment.isocalendar().week} 週")
        year_length = 366 if moment.replace(month=12, day=31).timetuple().tm_yday == 366 else 365
        self._year.set_label(f"{moment.timetuple().tm_yday / year_length:.0%}")


class WeatherScreen(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.add_css_class("screen")
        header, self._freshness = _page_header("天氣", "出門前掌握目前觀測", right_text="等待更新")
        self.append(header)

        content = Gtk.Box(spacing=14, vexpand=True)
        observation = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            hexpand=True,
            vexpand=True,
        )
        observation.add_css_class("weather-observation")
        self._location = _label("定位中", "section-label", xalign=0)
        observation.append(self._location)
        current = Gtk.Box(spacing=18, valign=Gtk.Align.CENTER, vexpand=True)
        self._icon = _label("○", "weather-icon")
        current.append(self._icon)
        weather_copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        self._temperature = _label("—", "weather-temperature", xalign=0)
        self._condition = _label("等待天氣資料", "weather-condition", xalign=0)
        weather_copy.append(self._temperature)
        weather_copy.append(self._condition)
        current.append(weather_copy)
        observation.append(current)
        self._advice = _label("資料更新後提供建議", "weather-advice", xalign=0)
        observation.append(self._advice)
        content.append(observation)

        facts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, vexpand=True)
        facts.add_css_class("weather-facts")
        facts.append(_label("觀測資料", "section-label", xalign=0, margin_top=8))
        self._apparent = _data_row(facts, "體感溫度")
        self._rain = _data_row(facts, "降雨機率")
        self._observed = _data_row(facts, "資料時間")
        content.append(facts)
        self.append(content)

    def update_weather(self, snapshot: WeatherSnapshot) -> None:
        icon, condition = _weather_presentation(snapshot.weather_code)
        self._freshness.set_label(freshness_label(snapshot.freshness))
        self._location.set_label(snapshot.location)
        self._icon.set_label(icon)
        self._temperature.set_label(temperature(snapshot.temperature_c))
        self._condition.set_label(condition)
        self._advice.set_label(_weather_advice(snapshot))
        self._apparent.set_label(temperature(snapshot.apparent_temperature_c))
        self._rain.set_label(percent(snapshot.precipitation_probability))
        self._observed.set_label(snapshot.observed_at.strftime("%H:%M"))


class TechFeedScreen(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add_css_class("screen")
        header, self._count = _page_header(
            "科技快訊", "按時間排列的精選科技動態", right_text="等待更新"
        )
        self.append(header)
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self._list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self._list.add_css_class("feed-list")
        scroll.set_child(self._list)
        self.append(scroll)
        self.update_feed(())

    def update_feed(self, items: Sequence[FeedItem]) -> None:
        while child := self._list.get_first_child():
            self._list.remove(child)
        self._count.set_label(f"{len(items)} 則更新" if items else "等待更新")
        if not items:
            empty = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=6,
                valign=Gtk.Align.CENTER,
                vexpand=True,
                margin_top=110,
            )
            empty.append(_label("尚無科技快訊", "empty-state"))
            empty.append(_label("連線更新後會依時間顯示", "meta-label"))
            self._list.append(empty)
            return
        for index, item in enumerate(items[:6], start=1):
            row = Gtk.Box(spacing=14)
            row.add_css_class("feed-row")
            row.append(_label(f"{index:02d}", "feed-index", valign=Gtk.Align.CENTER))
            copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, hexpand=True)
            copy.append(_label(item.title, "feed-title", xalign=0, wrap=True, lines=2))
            published = item.published_at.strftime("%m/%d  %H:%M") if item.published_at else "最新"
            copy.append(_label(f"{item.source}  ·  {published}", "feed-source", xalign=0))
            row.append(copy)
            self._list.append(row)


class FocusScreen(Gtk.Box):
    def __init__(
        self,
        on_start: Callable[[], None] | None = None,
        on_pause: Callable[[], None] | None = None,
        on_reset: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.add_css_class("screen")
        header, self._state_badge = _page_header(
            "專注計時", "一次只處理現在最重要的事", right_text="已暫停"
        )
        self.append(header)

        content = Gtk.Box(spacing=18, vexpand=True)
        timer = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            hexpand=True,
            vexpand=True,
            valign=Gtk.Align.FILL,
        )
        timer.add_css_class("focus-stage")
        self._mode = _label("專注模式", "focus-mode", xalign=0)
        self._remaining = _label("25:00", "focus-time", xalign=0, vexpand=True)
        self._progress = Gtk.ProgressBar(hexpand=True)
        self._progress.set_fraction(1.0)
        timer.append(self._mode)
        timer.append(self._remaining)
        timer.append(self._progress)
        timer.append(_label("完成這一段，再休息。", "meta-label", xalign=0))
        content.append(timer)

        summary = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
            valign=Gtk.Align.CENTER,
        )
        summary.add_css_class("focus-summary")
        summary.append(_label("本次節奏", "section-label", xalign=0, margin_bottom=8))
        self._sessions = _data_row(summary, "今日完成", initial="0 次")
        self._rhythm = _data_row(summary, "計時長度", initial="25 分鐘")
        content.append(summary)
        self.append(content)

        controls = Gtk.Box(spacing=10, halign=Gtk.Align.START)
        controls.add_css_class("focus-controls")
        for text, css_class, callback in (
            ("開始", "primary-action", on_start),
            ("暫停", "secondary-action", on_pause),
            ("重設", "danger-action", on_reset),
        ):
            button = Gtk.Button(label=text)
            button.add_css_class(css_class)
            if callback:
                button.connect("clicked", lambda _button, fn=callback: fn())
            controls.append(button)
        self.append(controls)

    def update_focus(self, state: FocusState) -> None:
        mode = "專注" if state.mode == "focus" else "休息"
        status = "進行中" if state.running else "已暫停"
        self._state_badge.set_label(status)
        self._mode.set_label(f"{mode}模式 · {status}")
        self._remaining.set_label(duration(state.remaining_seconds))
        self._sessions.set_label(f"{state.completed_sessions} 次")
        self._rhythm.set_label("25 分鐘" if state.mode == "focus" else "5 分鐘")
        total = 25 * 60 if state.mode == "focus" else 5 * 60
        self._progress.set_fraction(min(1.0, max(0.0, state.remaining_seconds / total)))


class DeviceMonitorScreen(Gtk.Box):
    def __init__(self, model_path: Path, preview_path: Path, low_power: bool = False) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add_css_class("screen")
        header, self._freshness = _page_header(
            "裝置監測", "Raspberry Pi 即時狀態", right_text="等待資料"
        )
        self.append(header)

        content = Gtk.Box(spacing=12, vexpand=True)
        model_column = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True, vexpand=True
        )
        model_column.add_css_class("model-shell")
        self._model_view = DeviceModelView(model_path, preview_path, low_power)
        model_column.append(self._model_view)
        views = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER)
        views.add_css_class("view-controls")
        for label, view in (
            ("上視圖", "top"),
            ("前視圖", "front"),
            ("右視圖", "right"),
            ("等角", "iso"),
        ):
            button = Gtk.Button(label=label)
            button.connect(
                "clicked", lambda _button, camera=view: self._model_view.set_camera_view(camera)
            )
            views.append(button)
        model_column.append(views)
        content.append(model_column)

        telemetry = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, vexpand=True)
        telemetry.add_css_class("telemetry-panel")
        telemetry.append(_label("系統讀數", "section-label", xalign=0, margin_top=8))
        self._values: dict[str, Gtk.Label] = {}
        for name in ("CPU", "溫度", "記憶體", "磁碟", "網路", "運行時間"):
            self._values[name] = _data_row(
                telemetry,
                name,
                value_class="telemetry-value",
            )
        content.append(telemetry)
        self.append(content)

    def update_telemetry(self, snapshot: TelemetrySnapshot) -> None:
        self._freshness.set_label(f"{snapshot.hostname} · {freshness_label(snapshot.freshness)}")
        self._values["CPU"].set_label(percent(snapshot.cpu_percent))
        self._values["溫度"].set_label(temperature(snapshot.cpu_temp_c))
        self._values["記憶體"].set_label(percent(snapshot.memory_percent))
        self._values["磁碟"].set_label(percent(snapshot.disk_percent))
        rx = human_bytes(snapshot.rx_bytes_per_second)
        tx = human_bytes(snapshot.tx_bytes_per_second)
        self._values["網路"].set_label(f"↓ {rx}  ↑ {tx}")
        self._values["運行時間"].set_label(duration(snapshot.uptime_seconds))

    def set_render_active(self, visible: bool) -> None:
        self._model_view.set_render_enabled(visible)

    def set_visible(self, visible: bool) -> None:
        """Retain the original render-toggle API used by the first window shell."""
        self.set_render_active(visible)
