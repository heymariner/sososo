"""Title normalisation, fingerprinting / dedupe, and top-N selection."""

from __future__ import annotations

import hashlib
import re

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation and collapse whitespace."""
    if not title:
        return ""
    lowered = title.lower()
    no_punct = _PUNCT_RE.sub("", lowered)
    return _WS_RE.sub(" ", no_punct).strip()


def item_fingerprint(item) -> str:
    """SHA-256 of ``normalized title + "|" + lowercased url``."""
    if isinstance(item, dict):
        title = item.get("title", "") or ""
        url = item.get("url", "") or ""
    else:
        title = getattr(item, "title", "") or ""
        url = getattr(item, "url", "") or ""
    payload = f"{normalize_title(str(title))}|{str(url).strip().lower()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def is_duplicate(item, seen_fingerprints: set) -> bool:
    """Return True if *item*'s fingerprint is already in *seen_fingerprints*."""
    return item_fingerprint(item) in seen_fingerprints


def select_top(scored, threshold: float = 60, limit: int = 5):
    """Return ``(item, ScoreResult)`` pairs with ``total >= threshold``,
    sorted by total descending, capped at *limit* entries."""
    kept = [
        pair for pair in (scored or [])
        if pair and len(pair) == 2 and getattr(pair[1], "total", 0) >= threshold
    ]
    kept.sort(key=lambda pair: getattr(pair[1], "total", 0), reverse=True)
    return kept[:limit]
