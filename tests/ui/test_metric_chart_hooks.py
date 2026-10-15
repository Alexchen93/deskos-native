from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[2]
APP_PATH = ROOT / "src/deskos/app.py"
CHARTS_PATH = ROOT / "src/deskos/ui/charts.py"
SCREENS_PATH = ROOT / "src/deskos/ui/screens.py"
WIDGETS_PATH = ROOT / "src/deskos/ui/widgets.py"


def _literals(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def test_native_sparkline_is_a_gtk_drawing_area_with_an_empty_state() -> None:
    text = CHARTS_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(CHARTS_PATH))
    sparkline = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Sparkline"
    )

    assert any(
        base.attr == "DrawingArea" for base in sparkline.bases if isinstance(base, ast.Attribute)
    )
    assert {"set_draw_func", "set_tooltip_text", "queue_draw"} <= {
        node.attr for node in ast.walk(sparkline) if isinstance(node, ast.Attribute)
    }
    assert "暫無趨勢資料" in text


def test_app_and_native_metric_views_use_history_event_hooks() -> None:
    expected_topics = {"weather_history", "cpu_temperature_history", "cpu_usage_history"}

    assert expected_topics <= _literals(APP_PATH)
    assert expected_topics <= _literals(WIDGETS_PATH)
    assert expected_topics <= _literals(SCREENS_PATH)
    assert "Sparkline" in WIDGETS_PATH.read_text(encoding="utf-8")
    assert "Sparkline" in SCREENS_PATH.read_text(encoding="utf-8")
