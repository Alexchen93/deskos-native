from __future__ import annotations

import threading

import pytest

from deskos.services.feeds import FeedSource, RssAtomFeedService, parse_feed
from deskos.services.storage import SQLiteRepository

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Example</title>
  <item><title>RSS story</title><link>https://example.test/rss</link>
  <pubDate>Mon, 12 Oct 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><title>Atom story</title><link href="https://example.test/atom" />
  <updated>2026-10-12T11:00:00Z</updated></entry>
</feed>"""


class Response:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size: int) -> bytes:
        return self._payload[:size]


def test_parser_supports_rss_and_namespaced_atom() -> None:
    rss = parse_feed(RSS, "RSS")
    atom = parse_feed(ATOM, "Atom")

    assert rss[0].title == "RSS story"
    assert rss[0].published_at.isoformat() == "2026-10-12T10:00:00+00:00"
    assert atom[0].url == "https://example.test/atom"
    assert atom[0].published_at.isoformat() == "2026-10-12T11:00:00+00:00"


def test_parser_rejects_dtd_and_entity_declarations() -> None:
    malicious = b'<!DOCTYPE rss [<!ENTITY x "expanded">]><rss><item>&x;</item></rss>'

    with pytest.raises(ValueError, match="not allowed"):
        parse_feed(malicious, "unsafe")


def test_source_failures_are_isolated_and_last_good_is_cached(tmp_path) -> None:
    repository = SQLiteRepository(tmp_path / "deskos.sqlite3")
    sources = [
        FeedSource("RSS", "https://feeds.test/rss"),
        FeedSource("Atom", "https://feeds.test/atom"),
    ]
    payloads = {
        "https://feeds.test/rss": RSS,
        "https://feeds.test/atom": ATOM,
    }
    calls = []

    def opener(url, *, timeout):
        calls.append((url, timeout))
        value = payloads[url]
        if isinstance(value, Exception):
            raise value
        return Response(value)

    service = RssAtomFeedService(sources, repository, timeout_seconds=4, opener=opener)
    assert [item.title for item in service.refresh()] == ["Atom story", "RSS story"]
    assert all(timeout == 4 for _, timeout in calls)

    payloads["https://feeds.test/rss"] = TimeoutError("rss unavailable")
    payloads["https://feeds.test/atom"] = b"<not-xml"
    assert [item.title for item in service.refresh()] == ["Atom story", "RSS story"]

    restored = RssAtomFeedService(sources, repository, opener=opener)
    assert [item.title for item in restored.latest()] == ["Atom story", "RSS story"]


def test_refresh_async_calls_back_with_aggregate(tmp_path) -> None:
    repository = SQLiteRepository(tmp_path / "deskos.sqlite3")
    service = RssAtomFeedService(
        [FeedSource("RSS", "https://feeds.test/rss")],
        repository,
        opener=lambda *args, **kwargs: Response(RSS),
    )
    finished = threading.Event()
    received = []

    service.refresh_async(lambda items: (received.extend(items), finished.set()))

    assert finished.wait(1)
    assert [item.title for item in received] == ["RSS story"]
