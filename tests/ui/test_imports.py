import importlib


def test_ui_package_imports_without_initialising_gtk() -> None:
    ui = importlib.import_module("deskos.ui")
    assert ui.duration(61) == "01:01"


def test_glb_parser_rejects_missing_file() -> None:
    from pathlib import Path

    from deskos.ui.device import load_glb_positions

    try:
        load_glb_positions(Path("does-not-exist.glb"))
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("expected missing GLB to fail for fallback path")
