"""Deterministic scoring of research items (0-100 per dimension)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.research.validation import classify_source

WEIGHTS: dict[str, float] = {
    "recency": 0.15,
    "relevance": 0.15,
    "importance": 0.15,
    "maritime_value": 0.12,
    "seafarer_value": 0.12,
    "shareability": 0.10,
    "visual_potential": 0.08,
    "video_potential": 0.05,
    "source_reliability": 0.08,
}
# Sanity: weights sum to 1.0.
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

RELEVANCE_KEYWORDS = (
    "shipping", "maritime", "port", "vessel", "ship", "cargo", "freight",
    "logistics", "trade", "ocean", "sea", "container", "fleet",
)
IMPORTANCE_KEYWORDS = (
    "imo", "solas", "marpol", "safety", "regulation", "decarbonization",
    "decarbonisation", "emission", "accident", "incident", "crew",
    "seafarer", "strike", "congestion", "sanction", "fuel", "ban",
    "deadline", "treaty", "convention",
)
MARITIME_KEYWORDS = (
    "shipping", "maritime", "vessel", "ship", "port", "cargo", "seafarer",
    "sailor", "nautical", "offshore", "container", "tanker", "bulk carrier",
)
SEAFARER_KEYWORDS = (
    "crew", "seafarer", "sailor", "welfare", "fatigue", "training",
    "certification", "wages", "abandonment", "repatriation", "lifeboat",
    "drill", "mental health",
)
SHAREABILITY_KEYWORDS = (
    "breaking", "record", "first", "new", "historic", "major", "urgent",
    "landmark", "milestone",
)
VISUAL_KEYWORDS = (
    "photo", "image", "ship", "port", "bridge", "vessel", "harbour",
    "harbor", "container", "crane", "sea", "ocean", "sunset", "aerial",
    "drone", "picture",
)
VIDEO_KEYWORDS = (
    "video", "watch", "footage", "drone", "tour", "onboard", "on board",
    "bridge", "engine room", "timelapse", "clip", "film",
)


@dataclass
class ScoreResult:
    total: float
    band: str
    dimensions: dict = field(default_factory=dict)


def band(total: float) -> str:
    """Map a 0-100 total to a band label."""
    if total < 40:
        return "reject"
    if total < 60:
        return "low priority"
    if total < 75:
        return "possible"
    if total < 90:
        return "strong candidate"
    return "priority content"


# Alias with a more explicit name.
band_for_total = band


def _keyword_score(text: str, keywords) -> float:
    """Score 0-100 from distinct keyword matches in *text*.

    No match -> 20, one match -> 45, two -> 65, three -> 85, four+ -> 100.
    Deterministic and capped at 100.
    """
    lowered = (text or "").lower()
    matches = {kw for kw in keywords if kw in lowered}
    if not matches:
        return 20.0
    return float(min(100, 25 + 20 * len(matches)))


def _recency_score(published_at) -> float:
    if published_at is None:
        return 50.0
    now = datetime.now(timezone.utc)
    pub = published_at
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=timezone.utc)
    age_days = (now - pub).total_seconds() / 86400.0
    if age_days < 0:
        return 100.0
    if age_days < 1:
        return 100.0
    if age_days < 3:
        return 80.0
    if age_days < 7:
        return 60.0
    if age_days < 30:
        return 40.0
    return 20.0


def _shareability_score(item) -> float:
    text = f"{item.title or ''} {item.summary or ''}".lower()
    title_len = len((item.title or "").strip())
    score = 50.0
    if 40 <= title_len <= 120:
        score += 20.0
    elif title_len >= 20:
        score += 10.0
    matches = {kw for kw in SHAREABILITY_KEYWORDS if kw in text}
    score += 10.0 * len(matches)
    return float(min(100, max(20, score)))


def score_item(item, config: dict | None = None) -> ScoreResult:
    """Score *item* deterministically; *config* is accepted for API
    compatibility (weights may be overridden via ``config["weights"]``)."""
    weights = dict(WEIGHTS)
    if config and isinstance(config, dict) and isinstance(config.get("weights"), dict):
        weights.update(config["weights"])
        total_w = sum(weights.values())
        if total_w > 0:
            weights = {k: v / total_w for k, v in weights.items()}

    text = f"{item.title or ''} {item.summary or ''}"
    dimensions = {
        "recency": _recency_score(getattr(item, "published_at", None)),
        "relevance": _keyword_score(text, RELEVANCE_KEYWORDS),
        "importance": _keyword_score(text, IMPORTANCE_KEYWORDS),
        "maritime_value": _keyword_score(text, MARITIME_KEYWORDS),
        "seafarer_value": _keyword_score(text, SEAFARER_KEYWORDS),
        "shareability": _shareability_score(item),
        "visual_potential": _keyword_score(text, VISUAL_KEYWORDS),
        "video_potential": _keyword_score(text, VIDEO_KEYWORDS),
        "source_reliability": float(
            classify_source(getattr(item, "source", "") or "", getattr(item, "url", "") or "")
        ),
    }
    total = round(
        sum(dimensions[k] * weights.get(k, 0.0) for k in WEIGHTS), 1
    )
    total = float(min(100.0, max(0.0, total)))
    return ScoreResult(total=total, band=band(total), dimensions=dimensions)
