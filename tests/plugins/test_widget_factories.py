from __future__ import annotations

from pathlib import Path

from deskos.plugins import PluginContext, PluginMetadata, PluginSpec, builtin


def _context() -> PluginContext:
    return PluginContext(
        navigate=lambda _page: None,
        dispatch=lambda _event: None,
        get_setting=lambda _key, default=None: default,
        set_setting=lambda _key, _value: None,
    )


def test_plugin_spec_keeps_lifecycle_position_and_makes_widget_optional() -> None:
    def install(_context: PluginContext) -> None:
        return None

    spec = PluginSpec(
        PluginMetadata("sample", "Sample", "A plugin", "0.4.0", 10),
        lambda _context: object(),
        install,
    )

    assert spec.on_install is install
    assert spec.create_widget is None


def test_builtin_plugins_provide_dedicated_widget_factories(monkeypatch, tmp_path: Path) -> None:
    def factory(name: str):
        def create(
            *args: object, **kwargs: object
        ) -> tuple[str, tuple[object, ...], dict[str, object]]:
            return name, args, kwargs

        return create

    monkeypatch.setattr(builtin, "ClockHomeWidget", factory("clock"))
    monkeypatch.setattr(builtin, "WeatherHomeWidget", factory("weather"))
    monkeypatch.setattr(builtin, "TechFeedHomeWidget", factory("feed"))
    monkeypatch.setattr(builtin, "FocusHomeWidget", factory("focus"))
    monkeypatch.setattr(builtin, "DeviceHomeWidget", factory("device"))

    specs = builtin.builtin_plugin_specs(
        model_path=tmp_path / "model.glb",
        preview_path=tmp_path / "preview.png",
        low_power=False,
        use_24_hour_time=False,
        focus_minutes=50,
        rest_minutes=10,
    )
    widgets = {spec.metadata.id: spec.create_widget(_context()) for spec in specs}

    assert widgets == {
        "clock": ("clock", (), {"use_24_hour": False}),
        "weather": ("weather", (), {}),
        "feed": ("feed", (), {}),
        "focus": ("focus", (), {"focus_minutes": 50, "rest_minutes": 10}),
        "device": ("device", (), {}),
    }
