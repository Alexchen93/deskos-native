"""Small native GTK/Cairo chart widgets used by DeskOS metric views."""

# ruff: noqa: E402
from __future__ import annotations

from collections.abc import Sequence

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from deskos.services.history import HistorySample


class Sparkline(Gtk.DrawingArea):
    """A touch-safe, allocation-free sparkline with a visible empty state."""

    def __init__(self, *, height: int = 32) -> None:
        super().__init__(height_request=height, hexpand=True)
        self._samples: tuple[HistorySample, ...] = ()
        self.set_draw_func(self._draw)
        self.set_tooltip_text("暫無趨勢資料")

    @property
    def samples(self) -> tuple[HistorySample, ...]:
        return self._samples

    def set_samples(self, samples: Sequence[HistorySample]) -> None:
        self._samples = tuple(samples)
        self.set_tooltip_text(None if self._samples else "暫無趨勢資料")
        self.queue_draw()

    def _draw(self, _area: Gtk.DrawingArea, context: object, width: int, height: int) -> None:
        if width <= 1 or height <= 1:
            return
        padding = 3.0
        draw = context
        draw.set_line_width(1.5)
        if not self._samples:
            draw.set_source_rgba(0.26, 0.36, 0.34, 0.32)
            draw.move_to(padding, height / 2)
            draw.line_to(width - padding, height / 2)
            draw.stroke()
            return

        values = [sample.value for sample in self._samples]
        minimum, maximum = min(values), max(values)
        span = maximum - minimum or 1.0
        usable_width = max(1.0, width - 2 * padding)
        usable_height = max(1.0, height - 2 * padding)
        draw.set_source_rgba(0.15, 0.36, 0.31, 0.9)
        for index, value in enumerate(values):
            x = padding + usable_width * index / max(1, len(values) - 1)
            y = height - padding - (value - minimum) / span * usable_height
            if index:
                draw.line_to(x, y)
            else:
                draw.move_to(x, y)
        if len(values) == 1:
            y = height / 2
            draw.move_to(padding, y)
            draw.line_to(width - padding, y)
            draw.stroke()
            draw.arc(width / 2, y, 2.5, 0, 6.283185307)
            draw.fill()
        else:
            draw.stroke()
