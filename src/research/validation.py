"""Source reliability, claim classification and item validation.

Claim-classification rules (deterministic, in this order):
1. UNVERIFIED -- text contains a hedge / unattributed-rumour marker:
   ``reportedly``, ``allegedly``, ``rumour`` / ``rumor``, ``unconfirmed``.
2. COMMENTARY -- text contains an opinion / speculation marker:
   ``opinion``, ``analysis``, ``expects``, ``could``, ``may suggest``.
3. FACT -- text contains a factual-action marker (``announced``,
   ``confirmed``, ``published``, ``issued``, ``adopted``) or is a
   plain statement with none of the markers above. Plain statements
   are treated as FACT; they still need a reliable source, which is
   what :func:`classify_source` / :func:`validate_item` are for.
   No quotes or statistics are invented here.
"""

from __future__ import annotations

import re

TRUSTED_SOURCES: dict[str, int] = {
    "imo.org": 95,
    "lloydslist.com": 90,
    "tradewindsnews.com": 88,
    "splash247.com": 85,
    "gcaptain.com": 85,
    "maritime-executive.com": 85,
    # Class societies.
    "dnv.com": 90,
    "lr.org": 90,
    "bureauveritas.com": 90,
    "abs-group.com": 90,
    "classnk.or.jp": 90,
    "rina.org": 90,
}

UNKNOWN_RELIABILITY = 50

_FACT_MARKERS = ("announced", "confirmed", "published", "issued", "adopted")
_COMMENTARY_MARKERS = ("opinion", "analysis", "expects", "could", "may suggest")
_UNVERIFIED_MARKERS = ("reportedly", "allegedly", "rumour", "rumor", "unconfirmed")


def _contains(text: str, markers) -> bool:
    lowered = (text or "").lower()
    return any(m in lowered for m in markers)


def classify_source(source_name: str, url: str) -> int:
    """Return a 0-100 reliability score for a source.

    Matches domain substrings from :data:`TRUSTED_SOURCES` against
    the URL and the source name (case-insensitive); the highest
    matching reliability wins. Unknown sources score 50.
    """
    haystack = f"{source_name or ''} {url or ''}".lower()
    best: int | None = None
    for domain, reliability in TRUSTED_SOURCES.items():
        if domain in haystack:
            if best is None or reliability > best:
                best = reliability
    return best if best is not None else UNKNOWN_RELIABILITY


def classify_claim(text: str) -> str:
    """Classify *text* as ``"FACT"``, ``"COMMENTARY"`` or ``"UNVERIFIED"``.

    See the module docstring for the deterministic rule order.
    """
    if _contains(text, _UNVERIFIED_MARKERS):
        return "UNVERIFIED"
    if _contains(text, _COMMENTARY_MARKERS):
        return "COMMENTARY"
    # FACT markers, or a plain statement with no hedge/opinion marker.
    return "FACT"


def validate_item(item) -> list[str]:
    """Return a list of errors for a research item (empty = valid).

    Checks that ``title``, ``url`` and ``source`` are present and
    non-blank. Works with :class:`ResearchItem` objects and with
    dicts / objects exposing those attributes.
    """
    errors: list[str] = []
    if isinstance(item, dict):
        title = item.get("title")
        url = item.get("url")
        source = item.get("source")
    else:
        title = getattr(item, "title", None)
        url = getattr(item, "url", None)
        source = getattr(item, "source", None)
    if not title or not str(title).strip():
        errors.append("title is required")
    if not url or not str(url).strip():
        errors.append("url is required")
    if not source or not str(source).strip():
        errors.append("source is required")
    return errors
