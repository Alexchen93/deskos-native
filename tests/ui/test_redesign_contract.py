import ast
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
WINDOW_PATH = ROOT / "src/deskos/ui/window.py"
SCREENS_PATH = ROOT / "src/deskos/ui/screens.py"
STYLE_PATH = ROOT / "src/deskos/ui/style.py"

NAV_DESTINATIONS = ("home", "clock", "weather", "feed", "focus", "device")
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


def test_compact_rail_exposes_all_six_stack_destinations_without_decorative_icons() -> None:
    window = _class(_tree(WINDOW_PATH), "DeskOSWindow")
    nav_items = _class_literal(window, "_NAV_ITEMS")

    assert tuple(item[0] for item in nav_items) == NAV_DESTINATIONS
    assert all(len(item) == 2 for item in nav_items)
    assert tuple(item[1] for item in nav_items) == ("首頁", "時鐘", "天氣", "快訊", "專注", "裝置")

    init = _method(window, "__init__")
    root_children = {
        _qualified_name(argument.func)
        if isinstance(argument, ast.Call)
        else _qualified_name(argument)
        for call in ast.walk(init)
        if isinstance(call, ast.Call) and _qualified_name(call.func) == "root.append"
        for argument in call.args
    }
    assert {"self._make_sidebar", "self._stack"} <= root_children

    stack_destinations = set()
    for loop in (node for node in ast.walk(init) if isinstance(node, ast.For)):
        if not any(
            isinstance(node, ast.Call) and _qualified_name(node.func) == "self._stack.add_named"
            for node in ast.walk(loop)
        ):
            continue
        assert isinstance(loop.iter, ast.Tuple)
        for pair in loop.iter.elts:
            assert isinstance(pair, ast.Tuple)
            destination = pair.elts[0]
            if isinstance(destination, ast.Constant):
                stack_destinations.add(destination.value)
            else:
                assert _qualified_name(destination) == "self.HOME"
                stack_destinations.add("home")
    assert stack_destinations == set(NAV_DESTINATIONS)


def test_window_updates_forward_to_detail_screen_and_home() -> None:
    window = _class(_tree(WINDOW_PATH), "DeskOSWindow")
    forwarding = {
        "update_telemetry": "device",
        "update_weather": "weather",
        "update_feed": "feed",
        "update_focus": "focus",
    }

    for method_name, detail_screen in forwarding.items():
        calls = _calls(_method(window, method_name))
        argument = "items" if method_name == "update_feed" else "snapshot"
        if method_name == "update_focus":
            argument = "state"
        assert (f"self.{detail_screen}.{method_name}", (argument,)) in calls
        assert (f"self.home.{method_name}", (argument,)) in calls


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
