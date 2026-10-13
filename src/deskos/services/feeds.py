from __future__ import annotations

import threading
import xml.etree.ElementTree as ET
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Protocol
from urllib.request import urlopen

from deskos.core.models import FeedItem


@dataclass(frozen=True, slots=True)
class FeedSource:
    name: str
    url: str


class CacheStore(Protocol):
    def get_cache(self, key: str) -> Any: ...

    def set_cache(
        self,
        key: str,
        value: Any,
        *,
        updated_at: datetime | None = None,
    ) -> None: ...


class RssAtomFeedService:
    """Fetch independent RSS/Atom sources while retaining each source's last-good data."""

    def __init__(
        self,
        sources: Sequence[FeedSource],
        store: CacheStore,
        *,
        timeout_seconds: float = 5.0,
        max_items_per_source: int = 20,
        max_response_bytes: int = 2_000_000,
        opener: Callable[..., Any] = urlopen,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if timeout_seconds <= 0 or max_items_per_source <= 0 or max_response_bytes <= 0:
            raise ValueError("timeouts and size limits must be positive")
        self._sources = tuple(sources)
        self._store = store
        self._timeout = timeout_seconds
        self._max_items = max_items_per_source
        self._max_bytes = max_response_bytes
        self._opener = opener
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.RLock()
        self._items_by_source = {source.url: self._load_cached(source) for source in self._sources}

    def latest(self) -> Sequence[FeedItem]:
        with self._lock:
            items = [item for values in self._items_by_source.values() for item in values]
        return tuple(sorted(items, key=_sort_key, reverse=True))

    def refresh(self) -> Sequence[FeedItem]:
        for source in self._sources:
            try:
                items = self._fetch_source(source)
            except Exception:
                continue
            with self._lock:
                self._items_by_source[source.url] = items
            self._store.set_cache(
                _cache_key(source),
                [_serialize_item(item) for item in items],
                updated_at=self._aware_now(),
            )
        return self.latest()

    def refresh_async(self, callback: Callable[[Sequence[FeedItem]], None]) -> None:
        def worker() -> None:
            items = self.refresh()
            try:
                callback(items)
            except Exception:
                pass

        threading.Thread(target=worker, name="deskos-feeds", daemon=True).start()

    def _fetch_source(self, source: FeedSource) -> list[FeedItem]:
        response = self._opener(source.url, timeout=self._timeout)
        with response:
            raw = response.read(self._max_bytes + 1)
        if len(raw) > self._max_bytes:
            raise ValueError("feed response exceeded configured size limit")
        return parse_feed(raw, source.name, limit=self._max_items)

    def _load_cached(self, source: FeedSource) -> list[FeedItem]:
        try:
            record = self._store.get_cache(_cache_key(source))
            if record is None or not isinstance(record.value, list):
                return []
            return [_deserialize_item(value) for value in record.value]
        except (AttributeError, KeyError, TypeError, ValueError):
            return []

    def _aware_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def parse_feed(payload: bytes, source: str, *, limit: int = 20) -> list[FeedItem]:
    """Parse bounded RSS/Atom XML without accepting DTD or entity declarations."""
    lowered = payload.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise ValueError("DTD and entity declarations are not allowed in feeds")
    root = ET.fromstring(payload)
    kind = _local_name(root.tag)
    if kind in {"rss", "rdf"}:
        elements = [element for element in root.iter() if _local_name(element.tag) == "item"]
        return [_rss_item(element, source) for element in elements[:limit]]
    if kind == "feed":
        elements = [element for element in root if _local_name(element.tag) == "entry"]
        return [_atom_item(element, source) for element in elements[:limit]]
    raise ValueError(f"unsupported feed root: {kind}")


def _rss_item(element: ET.Element, source: str) -> FeedItem:
    title = _child_text(element, "title") or "Untitled"
    url = _child_text(element, "link") or _child_text(element, "guid") or ""
    published = _parse_datetime(_child_text(element, "pubDate") or _child_text(element, "date"))
    return FeedItem(title=title, source=source, url=url, published_at=published)


def _atom_item(element: ET.Element, source: str) -> FeedItem:
    title = _child_text(element, "title") or "Untitled"
    url = ""
    for child in element:
        if _local_name(child.tag) != "link":
            continue
        relation = child.attrib.get("rel", "alternate")
        href = child.attrib.get("href", "")
        if href and relation == "alternate":
            url = href
            break
        if href and not url:
            url = href
    published = _parse_datetime(
        _child_text(element, "published") or _child_text(element, "updated")
    )
    return FeedItem(title=title, source=source, url=url, published_at=published)


def _child_text(element: ET.Element, name: str) -> str | None:
    target = name.lower()
    for child in element:
        if _local_name(child.tag) == target and child.text:
            return child.text.strip()
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _cache_key(source: FeedSource) -> str:
    return f"feed:{source.url}"


def _serialize_item(item: FeedItem) -> dict[str, Any]:
    return {
        "title": item.title,
        "source": item.source,
        "url": item.url,
        "published_at": item.published_at.isoformat() if item.published_at else None,
    }


def _deserialize_item(value: dict[str, Any]) -> FeedItem:
    return FeedItem(
        title=str(value["title"]),
        source=str(value["source"]),
        url=str(value["url"]),
        published_at=_parse_datetime(value.get("published_at")),
    )


def _sort_key(item: FeedItem) -> tuple[bool, datetime]:
    return (item.published_at is not None, item.published_at or datetime.min.replace(tzinfo=UTC))
