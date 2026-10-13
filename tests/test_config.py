from deskos.app import _source_name
from deskos.config import AppConfig


def test_config_reads_native_runtime_flags(monkeypatch) -> None:
    monkeypatch.setenv("DESKOS_WINDOWED", "1")
    monkeypatch.setenv("DESKOS_LOW_POWER", "1")
    monkeypatch.setenv("DESKOS_FEED_URLS", "https://example.com/feed, https://other.test/rss")
    config = AppConfig.from_environment()
    assert config.windowed is True
    assert config.low_power is True
    assert config.feed_urls == ("https://example.com/feed", "https://other.test/rss")


def test_feed_source_name_uses_hostname() -> None:
    assert _source_name("https://www.raspberrypi.com/news/feed/") == "raspberrypi.com"
