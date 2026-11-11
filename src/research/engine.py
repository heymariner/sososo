"""Research engine: fan out to providers, dedupe, sort newest first."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.logging_config import log_event
from src.research.providers import ResearchItem

logger = logging.getLogger("heymariner.research")


class ResearchEngine:
    """Run all providers and return a clean, deduplicated item list."""

    def __init__(self, providers, config: dict | None = None):
        self.providers = list(providers or [])
        self.config = config or {}

    def run(self) -> list[ResearchItem]:
        items: list[ResearchItem] = []
        fetched = 0
        for provider in self.providers:
            try:
                provider_items = provider.fetch() or []
            except Exception as exc:  # noqa: BLE001 - one bad provider must not stop the run
                logger.warning("Research provider failed %r: %s", provider, exc)
                continue
            fetched += len(provider_items)
            items.extend(provider_items)

        seen_urls: set[str] = set()
        seen_ids: set[str] = set()
        deduped: list[ResearchItem] = []
        for item in items:
            url_key = (item.url or "").strip().lower()
            if url_key and url_key in seen_urls:
                continue
            if item.id and item.id in seen_ids:
                continue
            if url_key:
                seen_urls.add(url_key)
            if item.id:
                seen_ids.add(item.id)
            deduped.append(item)

        def _sort_key(item: ResearchItem):
            return item.published_at or datetime.min.replace(tzinfo=timezone.utc)

        deduped.sort(key=_sort_key, reverse=True)
        log_event(
            logger,
            "research_run",
            providers=len(self.providers),
            fetched=fetched,
            returned=len(deduped),
        )
        return deduped
