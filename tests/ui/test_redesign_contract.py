import ast
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
WINDOW_PATH = ROOT / "src/deskos/ui/window.py"
SCREENS_PATH = ROOT / "src/deskos/ui/screens.py"
STYLE_PATH = ROOT / "src/deskos/ui/style.py"

CORE_NAV_DESTINATIONS = ("home", "library", "settings")
SCREEN_COMPOSITIONS = {
    "HomeScreen": {"briefing-weather", "briefing-list", "briefing-row"},
    "ClockScreen": {"clock-stage", "clock-facts"},
    "WeatherScreen": {"weather-observation", "weather-facts"},
    "TechFeedScreen": {"feed-list", "feed-row"},
    "FocusScreen": {"focus-stage", "focus-summary", "focus-controls"},
    "DeviceMonitorScreen": {"model-shell", "telemetry-panel", "view-controls"},
}
FORBIDDEN_DASHBOARD_CLASSES = {
    "card",
    "card-soft",
    "card-icon",
    "card-value",
    "badge",
    "accent-purple",
    "accent-blue",
    "accent-cyan",
    "accent-orange",
    "accent-green",
    "accent-pink",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _class(tree: ast.Module, name: str) -> ast.ClassDef:
    return next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)


def _method(class_node: ast.ClassDef, name: str) -> ast.FunctionDef:
    return next(
        node for node in class_node.body if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _qualified_name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    return None


def _class_literal(class_node: ast.ClassDef, name: str) -> object:
    assignment = next(
        node
        for node in class_node.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and any(
            isinstance(target, ast.Name) and target.id == name
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        )
    )
    return ast.literal_eval(assignment.value)


def _calls(node: ast.AST) -> set[tuple[str, tuple[str | None, ...]]]:
    return {
        (
            name,
            tuple(_qualified_name(argument) for argument in call.args),
        )
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and (name := _qualified_name(call.func)) is not None
    }


def _string_literals(node: ast.AST) -> set[str]:
    return {
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
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


def _pixels(rule: dict[str, str], property_name: str) -> int:
    match = re.fullmatch(r"(\d+)px", rule[property_name])
    assert match, f"{property_name} must remain a fixed pixel value"
    return int(match.group(1))


def test_window_defaults_target_the_pi_display() -> None:
    window = _class(_tree(WINDOW_PATH), "DeskOSWindow")

    assert _class_literal(window, "DISPLAY_WIDTH") == 1024
    assert _class_literal(window, "DISPLAY_HEIGHT") == 600

    init = _method(window, "__init__")
    super_init = next(
        node
        for node in ast.walk(init)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "__init__"
        and isinstance(node.func.value, ast.Call)
        and _qualified_name(node.func.value.func) == "super"
    )
    keywords = {keyword.arg: _qualified_name(keyword.value) for keyword in super_init.keywords}
    assert keywords["default_width"] == "self.DISPLAY_WIDTH"
    assert keywords["default_height"] == "self.DISPLAY_HEIGHT"


def test_dynamic_shell_keeps_core_pages_and_scrollable_touch_navigation() -> None:
    window = _class(_tree(WINDOW_PATH), "DeskOSWindow")
    assignment = next(
        node
        for node in window.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "_CORE_NAV_ITEMS"
            for target in node.targets
        )
    )
    assert isinstance(assignment.value, ast.Tuple)
    core_items = assignment.value.elts
    init = _method(window, "__init__")
    sidebar = _method(window, "_make_sidebar")

    assert tuple(_qualified_name(item.elts[0]) for item in core_items) == (
        "HOME",
        "LIBRARY",
        "SETTINGS",
    )
    assert tuple(ast.literal_eval(item.elts[1]) for item in core_items) == (
        "首頁",
        "應用程式",
        "設定",
    )
    assert any(name == "Gtk.ScrolledWindow" for name, _arguments in _calls(sidebar))
    assert ("self._add_navigation", ("page", "label")) in _calls(sidebar)
    assert {"self.HOME", "self.LIBRARY", "self.SETTINGS"} <= {
        _qualified_name(node) for node in ast.walk(init) if isinstance(node, ast.Attribute)
    }


def test_dynamic_plugin_mount_remove_and_event_delivery_are_guarded_by_installation() -> None:
    window = _class(_tree(WINDOW_PATH), "DeskOSWindow")

    mount_calls = _calls(_method(window, "_mount_plugin"))
    assert ("self._stack.add_named", ("screen", "plugin_id")) in mount_calls
    assert ("self._add_navigation", ("plugin_id", "spec.metadata.name")) in mount_calls

    unmount_calls = _calls(_method(window, "_unmount_plugin"))
    assert ("self._stack.remove", ("screen",)) in unmount_calls
    assert ("self._remove_navigation", ("plugin_id",)) in unmount_calls

    dispatch = _method(window, "dispatch_event")
    assert "self._plugins.is_installed" in {
        _qualified_name(call.func) for call in ast.walk(dispatch) if isinstance(call, ast.Call)
    }
    assert ("self._deliver_home", ("event",)) in _calls(dispatch)


def test_home_availability_tracks_optional_plugin_installation() -> None:
    window = _class(_tree(WINDOW_PATH), "DeskOSWindow")
    sync = _method(window, "_sync_home_availability")

    assert {"weather", "feed", "focus", "device"} <= _string_literals(sync)
    assert (
        "self.home.set_plugin_available",
        ("plugin_id", "self._plugins.is_installed"),
    ) not in _calls(sync)
    assert "self.home.set_plugin_available" in {
        _qualified_name(call.func) for call in ast.walk(sync) if isinstance(call, ast.Call)
    }
    assert "self._plugins.is_installed" in {
        _qualified_name(call.func) for call in ast.walk(sync) if isinstance(call, ast.Call)
    }


def test_touch_controls_and_compact_rail_fit_the_embedded_target() -> None:
    rules = _css_rules()

    assert _pixels(rules[".sidebar"], "min-width") <= 140
    assert _pixels(rules[".nav-button"], "min-height") >= 48
    assert _pixels(rules[".focus-controls button"], "min-width") >= 96
    assert _pixels(rules[".focus-controls button"], "min-height") >= 48
    assert _pixels(rules[".view-controls button"], "min-width") >= 72
    assert _pixels(rules[".view-controls button"], "min-height") >= 42


def test_screens_use_distinct_task_specific_compositions() -> None:
    tree = _tree(SCREENS_PATH)
    used_by_screen: dict[str, set[str]] = {}

    for class_name, expected_classes in SCREEN_COMPOSITIONS.items():
        literals = _string_literals(_class(tree, class_name))
        used_by_screen[class_name] = literals
        assert expected_classes <= literals

    signatures = [
        frozenset(classes & set.union(*map(set, SCREEN_COMPOSITIONS.values())))
        for classes in used_by_screen.values()
    ]
    assert len(signatures) == len(set(signatures))


def test_generic_colorful_dashboard_vocabulary_is_removed() -> None:
    css = _css_text()
    screen_literals = _string_literals(_tree(SCREENS_PATH))

    for class_name in FORBIDDEN_DASHBOARD_CLASSES:
        assert f".{class_name}" not in css
        assert class_name not in screen_literals

    assert "page-kicker" not in screen_literals
    assert "TODAY AT A GLANCE" not in screen_literals
    assert "homogeneous=True" not in SCREENS_PATH.read_text(encoding="utf-8")


def test_visual_language_uses_restrained_geometry_and_one_warm_accent() -> None:
    rules = _css_rules()
    accent_colors = {"#c27a45", "#c58a60", "#d18a55", "#b97849", "#bd7746", "#b86f3f"}

    assert rules["window"]["background-color"] == "#0d1218"
    assert rules[".sidebar"]["background-color"] == "#111820"
    assert _pixels(rules[".panel"], "border-radius") <= 8
    assert _pixels(rules[".briefing-list"], "border-radius") <= 8
    assert _pixels(rules[".weather-observation"], "border-radius") <= 8

    css_colors = set(re.findall(r"#[0-9a-fA-F]{6}", _css_text()))
    assert accent_colors <= css_colors
    assert not {"#7759f6", "#2586ca", "#2aa6b7", "#39c78b", "#d86acb"} & css_colors
