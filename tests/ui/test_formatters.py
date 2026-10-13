from deskos.core.models import Freshness
from deskos.ui.formatters import duration, freshness_label, human_bytes, percent, temperature


def test_display_formatters_handle_missing_values() -> None:
    assert human_bytes(None) == "—"
    assert percent(None) == "—"
    assert temperature(None) == "—"
    assert duration(None) == "—"


def test_display_formatters_are_touch_readable() -> None:
    assert human_bytes(1536) == "1.5 KiB"
    assert percent(49.6) == "50%"
    assert temperature(42) == "42.0°C"
    assert duration(3723) == "1:02:03"
    assert freshness_label(Freshness.STALE) == "Cached"
