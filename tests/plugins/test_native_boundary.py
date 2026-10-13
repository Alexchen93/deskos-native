from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[2]
PLUGIN_ROOT = ROOT / "src/deskos/plugins"

FORBIDDEN_IMPORTS = {
    "http.server",
    "socketserver",
    "subprocess",
    "webbrowser",
    "webkit",
    "webview",
    "urllib.request",
}
FORBIDDEN_CALLS = {
    "os.system",
    "os.popen",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "subprocess.Popen",
    "subprocess.run",
    "urllib.request.urlretrieve",
    "urllib.request.urlopen",
    "webbrowser.open",
}


def _qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _qualified_name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    return None


def test_plugin_code_keeps_a_native_local_capability_boundary() -> None:
    violations: list[str] = []

    for path in PLUGIN_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in FORBIDDEN_IMPORTS or alias.name.startswith("webkit"):
                        violations.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module in FORBIDDEN_IMPORTS or module.startswith("webkit"):
                    violations.append(f"{path.name}: from {module} import")
            elif isinstance(node, ast.Call):
                name = _qualified_name(node.func)
                if name in FORBIDDEN_CALLS:
                    violations.append(f"{path.name}: {name}()")
                if name == "subprocess.run" and any(
                    keyword.arg == "shell"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value
                    for keyword in node.keywords
                ):
                    violations.append(f"{path.name}: subprocess.run(shell=True)")

    assert violations == []


def test_plugin_context_exposes_only_navigation_events_and_settings() -> None:
    api = ast.parse((PLUGIN_ROOT / "api.py").read_text(encoding="utf-8"))
    context = next(
        node for node in api.body if isinstance(node, ast.ClassDef) and node.name == "PluginContext"
    )

    assert [field.target.id for field in context.body if isinstance(field, ast.AnnAssign)] == [
        "navigate",
        "dispatch",
        "get_setting",
        "set_setting",
    ]
