"""Research providers: RSS feeds and a deterministic local sample."""

from __future__ import annotations

import calendar
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

try:
    import feedparser
except ImportError:  # pragma: no cover - feedparser is a declared dep
    feedparser = None

logger = logging.getLogger("heymariner.research")


@dataclass
class ResearchItem:
    """One researched story / fact candidate."""

    id: str = ""
    title: str = ""
    summary: str = ""
    url: str = ""
    source: str = ""
    source_type: str = "rss"
    published_at: datetime | None = None
    category: str = "general"
    raw: object = None

    def __post_init__(self):
        if not self.id:
            digest = hashlib.sha256(
                f"{self.url or ''}{self.title or ''}".encode("utf-8")
            ).hexdigest()
            self.id = digest


class ResearchProvider(ABC):
    """Abstract source of :class:`ResearchItem` objects."""

    @abstractmethod
    def fetch(self) -> list[ResearchItem]:
        """Fetch items from this provider (never raises for one bad feed)."""
        raise NotImplementedError


def _parsed_to_datetime(parsed) -> datetime | None:
    """Convert a feedparser ``published_parsed`` struct_time to UTC datetime."""
    if not parsed:
        return None
    try:
        ts = calendar.timegm(parsed)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        return None


class RSSFeedProvider(ResearchProvider):
    """Fetch items from a list of RSS feeds.

    ``feeds`` is a list of dicts with ``url`` and ``name`` keys.
    A feed that fails to parse (missing feedparser, network error,
    malformed feed) is logged and skipped; other feeds still run.
    """

    def __init__(self, feeds: list[dict]):
        self.feeds = list(feeds or [])

    def fetch(self) -> list[ResearchItem]:
        items: list[ResearchItem] = []
        if feedparser is None:
            logger.warning("feedparser is not installed; RSS fetch skipped")
            return items
        for feed in self.feeds:
            url = feed.get("url") if isinstance(feed, dict) else None
            name = feed.get("name") if isinstance(feed, dict) else None
            if not url:
                logger.warning("RSS feed entry without url skipped: %r", feed)
                continue
            try:
                parsed = feedparser.parse(url)
            except Exception as exc:  # noqa: BLE001 - one bad feed must not stop others
                logger.warning("RSS feed failed %s: %s", url, exc)
                continue
            try:
                entries = parsed.entries or []
            except Exception:
                entries = []
            for entry in entries:
                try:
                    title = entry.get("title", "") or ""
                    summary = (
                        entry.get("summary")
                        or entry.get("description")
                        or ""
                    )
                    link = entry.get("link", "") or ""
                    published = _parsed_to_datetime(
                        entry.get("published_parsed")
                        or entry.get("updated_parsed")
                    )
                    items.append(
                        ResearchItem(
                            title=str(title).strip(),
                            summary=str(summary).strip(),
                            url=str(link).strip(),
                            source=str(name or feed.get("source") or ""),
                            source_type="rss",
                            published_at=published,
                            raw=dict(entry) if hasattr(entry, "keys") else entry,
                        )
                    )
                except Exception as exc:  # noqa: BLE001 - one bad entry must not stop the feed
                    logger.warning("RSS entry skipped from %s: %s", url, exc)
                    continue
        return items


class LocalSampleProvider(ResearchProvider):
    """Deterministic sample provider for offline use / tests.

    Returns three maritime items with real-looking sources and URLs
    and recent dates relative to now.
    """

    def fetch(self) -> list[ResearchItem]:
        now = datetime.now(timezone.utc)
        samples = [
            (
                "IMO advances decarbonization measures for international shipping",
                "The International Maritime Organization announced further "
                "measures to reduce greenhouse gas emissions from ships, "
                "as member states work towards the organisation's "
                "decarbonization targets for international shipping.",
                "https://www.imo.org/en/MediaCentre/PressBriefings/Pages/Decarbonization-measures.aspx",
                "IMO",
                now - timedelta(days=1),
            ),
            (
                "SOLAS safety rules put focus on crew training and lifeboat drills",
                "Updated SOLAS safety requirements underline the importance "
                "of regular lifeboat drills and crew training, with "
                "shipping companies reminded to keep safety procedures "
                "current and crews familiar with emergency equipment.",
                "https://www.lloydslist.com/LL1140000/SOLAS-safety-rules-crew-training-lifeboat-drills",
                "Lloyd's List",
                now - timedelta(days=2),
            ),
            (
                "Port congestion eases at major container hubs as schedules stabilise",
                "Congestion at major container ports has eased as vessel "
                "schedules stabilise, according to industry reports, "
                "helping to shorten waiting times for ships at anchor.",
                "https://splash247.com/port-congestion-eases-at-major-container-hubs/",
                "Splash247",
                now - timedelta(days=3),
            ),
        ]
        return [
            ResearchItem(
                title=title,
                summary=summary,
                url=url,
                source=source,
                source_type="sample",
                published_at=published,
                category="general",
            )
            for title, summary, url, source, published in samples
        ]
