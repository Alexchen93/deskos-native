import ast
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
HOME_PATH = ROOT / "src/deskos/ui/home.py"
WINDOW_PATH = ROOT / "src/deskos/ui/window.py"
SCREENS_PATH = ROOT / "src/deskos/ui/screens.py"
STYLE_PATH = ROOT / "src/deskos/ui/style.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _class(tree: ast.Module, name: str) -> ast.ClassDef:
    return next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)


def _method(class_node: ast.ClassDef, name: str) -> ast.FunctionDef:
    return next(
        node
        for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _qualified_name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    return None


def _calls(node: ast.AST) -> set[str]:
    return {
        name
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and (name := _qualified_name(call.func)) is not None
    }


def _css_text() -> str:
    tree = _tree(STYLE_PATH)
    css_assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "CSS" for target in node.targets)
    )
    return ast.literal_eval(css_assignment.value).decode("utf-8")


def _css_rules() -> dict[str, dict[str, str]]:
    css = re.sub(r"/\*.*?\*/", "", _css_text(), flags=re.DOTALL)
    rules: dict[str, dict[str, str]] = {}
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        declarations = {
            name.strip(): value.strip()
            for declaration in match.group(2).split(";")
            if ":" in declaration
            for name, value in [declaration.split(":", 1)]
        }
        for selector in match.group(1).split(","):
            rules[selector.strip()] = declarations
    return rules


def test_window_targets_the_pi_display_and_uses_an_overlay_shell() -> None:
    window = _class(_tree(WINDOW_PATH), "DeskOSWindow")
    literals = {
        assignment.targets[0].id: ast.literal_eval(assignment.value)
        for assignment in window.body
        if isinstance(assignment, ast.Assign)
        and isinstance(assignment.targets[0], ast.Name)
        and assignment.targets[0].id in {"DISPLAY_WIDTH", "DISPLAY_HEIGHT", "EDGE_ACTIVATION_PX"}
    }
    assert literals == {"DISPLAY_WIDTH": 1024, "DISPLAY_HEIGHT": 600, "EDGE_ACTIVATION_PX": 32}
    assert "Gtk.Overlay" in _calls(_method(window, "__init__"))
    assert "self._install_edge_gesture" in _calls(_method(window, "__init__"))


def test_edge_rail_is_temporary_and_supports_either_edge() -> None:
    window = _class(_tree(WINDOW_PATH), "DeskOSWindow")
    assert {"_make_app_rail", "_show_rail", "_hide_rail", "_on_edge_drag_end"} <= {
        method.name for method in window.body if isinstance(method, ast.FunctionDef)
    }
    gesture_calls = _calls(_method(window, "_on_edge_drag_end"))
    assert "self._show_rail" in gesture_calls
    rail_calls = _calls(_method(window, "_make_app_rail"))
    assert "Gtk.ScrolledWindow" in rail_calls


def test_every_installed_plugin_is_synced_into_the_widget_home() -> None:
    window = _class(_tree(WINDOW_PATH), "DeskOSWindow")
    mount_calls = _calls(_method(window, "_mount_plugin"))
    assert "self._create_home_widget" in mount_calls
    assert "self._sync_home_widgets" in mount_calls
    sync_calls = _calls(_method(window, "_sync_home_widgets"))
    assert "self.home.set_widgets" in sync_calls
    assert "self._plugins.is_installed" in sync_calls


def test_home_layout_is_persistent_and_editable() -> None:
    home = _class(_tree(HOME_PATH), "HomeScreen")
    assert {"enter_edit_mode", "set_editing", "_move", "_toggle_width", "_set_visible"} <= {
        method.name for method in home.body if isinstance(method, ast.FunctionDef)
    }
    assert "self._on_layout_changed" in _calls(_method(home, "_commit_layout"))
    window = _class(_tree(WINDOW_PATH), "DeskOSWindow")
    assert "self._repository.set_setting" in _calls(_method(window, "_save_home_layout"))


def test_fullscreen_apps_keep_distinct_task_compositions() -> None:
    tree = _tree(SCREENS_PATH)
    expected = {
        "ClockScreen": {"clock-stage", "clock-facts"},
        "WeatherScreen": {"weather-observation", "weather-facts"},
        "TechFeedScreen": {"feed-list", "feed-row"},
        "FocusScreen": {"focus-stage", "focus-summary", "focus-controls"},
        "DeviceMonitorScreen": {"model-shell", "telemetry-panel", "view-controls"},
    }
    for class_name, classes in expected.items():
        literals = {
            node.value
            for node in ast.walk(_class(tree, class_name))
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        assert classes <= literals


def test_light_theme_has_no_persistent_sidebar_and_keeps_touch_targets() -> None:
    rules = _css_rules()
    css = _css_text()
    assert rules["window"]["background-color"] == "#f4f1ea"
    assert ".sidebar" not in css
    assert rules[".app-rail-panel"]["min-width"] == "300px"
    assert rules["button.home-widget"]["min-height"] == "164px"
    assert rules[".focus-controls button"]["min-height"] == "50px"
    assert rules[".view-controls button"]["min-height"] == "44px"
