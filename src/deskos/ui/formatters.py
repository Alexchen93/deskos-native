"""Dependency-free presentation helpers for DeskOS widgets."""

from __future__ import annotations

from datetime import datetime

from deskos.core.models import Freshness


def human_bytes(value: int | None) -> str:
    if value is None:
        return "—"
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    amount = float(value)
    for unit in units:
        if abs(amount) < 1024 or unit == units[-1]:
            return f"{amount:.0f} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024
    return "—"


def percent(value: float | None) -> str:
    return "—" if value is None else f"{value:.0f}%"


def temperature(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}°C"


def duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "—"
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


def freshness_label(value: Freshness) -> str:
    return {
        Freshness.FRESH: "Live",
        Freshness.STALE: "Cached",
        Freshness.UNAVAILABLE: "Unavailable",
        Freshness.ERROR: "Error",
    }[value]


def clock_text(moment: datetime) -> tuple[str, str]:
    return moment.strftime("%H:%M"), moment.strftime("%A, %d %B")
