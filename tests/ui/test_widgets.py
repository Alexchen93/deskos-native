from __future__ import annotations

import ast
from pathlib import Path

WIDGETS_PATH = Path(__file__).parents[2] / "src/deskos/ui/widgets.py"
WIDGET_CLASSES = {
    "ClockHomeWidget",
    "WeatherHomeWidget",
    "TechFeedHomeWidget",
    "FocusHomeWidget",
    "DeviceHomeWidget",
}


def _tree() -> ast.Module:
    return ast.parse(WIDGETS_PATH.read_text(encoding="utf-8"), filename=str(WIDGETS_PATH))


def test_plugin_home_widgets_are_event_driven_native_gtk_previews() -> None:
    tree = _tree()
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}

    assert WIDGET_CLASSES <= classes.keys()
    for name in WIDGET_CLASSES:
        methods = {
            method.name
            for method in classes[name].body
            if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert "on_plugin_event" in methods

    gtk_button_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "Gtk"
        and node.func.attr == "Button"
    ]
    assert gtk_button_calls == []


def test_plugin_home_widgets_use_the_shared_home_css_vocabulary() -> None:
    literals = {
        node.value
        for node in ast.walk(_tree())
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }

    assert {
        "home-widget-preview",
        "home-widget-title",
        "home-widget-value",
        "home-widget-detail",
        "home-widget-clock",
        "home-widget-weather",
        "home-widget-feed",
        "home-widget-focus",
        "home-widget-device",
    } <= literals
