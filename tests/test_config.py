from deskos.app import _source_name
from deskos.config import AppConfig


def test_config_reads_the_native_window_mode_flag(monkeypatch) -> None:
    monkeypatch.setenv("DESKOS_WINDOWED", "1")

    assert AppConfig.from_environment().windowed is True


def test_config_defaults_to_fullscreen_native_mode(monkeypatch) -> None:
    monkeypatch.delenv("DESKOS_WINDOWED", raising=False)

    assert AppConfig.from_environment().windowed is False


def test_feed_source_name_uses_hostname() -> None:
    assert _source_name("https://www.raspberrypi.com/news/feed/") == "raspberrypi.com"
