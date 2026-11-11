"""HeyMariner pipeline: research -> score -> generate -> gate -> publish/queue.

Uses Part A (``src.config.Settings``, ``src.research`` providers/engine,
``src.content.scoring`` / ``caption`` / ``decision`` / ``selection``)
with their real signatures:

- ``RSSFeedProvider(feeds: list[dict])`` and ``LocalSampleProvider()``,
  run via ``ResearchEngine(providers).run()`` -> ``list[ResearchItem]``.
- ``ResearchItem`` fields: ``title``, ``summary``, ``url``, ``source``,
  ``published_at``, ``id``.
- ``score_item(item) -> ScoreResult(total, band, dimensions)``.
- ``generate_caption(item, score, brand) -> str``.
- ``decide_format(item, score, config) -> IMAGE_POST | VIDEO | TEXT_LED | NO_POST``.
- ``item_fingerprint(item)`` / ``select_top(scored, threshold, limit)``.

Falls back to local sample items / heuristic scoring when Part A is
not yet importable, so the pipeline stays runnable in dry-run mode
either way. No real Facebook call is made while ``dry_run=True``.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from src.facebook.client import FacebookClient
from src.facebook.publisher import FacebookPublisher
from src.image.card import DEFAULT_BRAND, generate_brand_card
from src.publishing.gate import check_publishing_gate
from src.publishing.queue import save_pending
from src.publishing.state import StateStore


# --------------------------------------------------------------------------
# Config / normalisation helpers
# --------------------------------------------------------------------------

def _unwrap(configs: dict, key: str) -> dict:
    """Unwrap one level: config files are ``{"<key>": {...}}``."""
    value = configs.get(key) or {}
    if isinstance(value, dict) and set(value.keys()) == {key}:
        inner = value.get(key)
        return inner if isinstance(inner, dict) else {}
    return value if isinstance(value, dict) else {}


def _load_configs(root: Path) -> dict:
    try:
        from src.config import load_all_configs

        raw = load_all_configs(root)
        return {key: _unwrap(raw, key) for key in raw}
    except Exception:
        configs: dict[str, Any] = {}
        for name in ("brand", "content_policy", "publishing", "research", "generation"):
            path = root / "config" / f"{name}.json"
            if name == "content_policy":
                path = root / "config" / "content-policy.json"
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            configs[name] = _unwrap({name: data}, name) if data else {}
        return configs


def _settings(root: Path):
    try:
        from src.config import Settings

        return Settings()
    except Exception:
        return None


def _as_item(raw: Any) -> Any:
    """Coerce a dict to a ResearchItem-like object (title/summary/url/...)."""
    if isinstance(raw, dict):
        try:
            from src.research.providers import ResearchItem

            return ResearchItem(
                title=str(raw.get("title") or ""),
                summary=str(raw.get("summary") or raw.get("description") or ""),
                url=str(raw.get("url") or raw.get("source_url") or raw.get("link") or ""),
                source=str(raw.get("source") or raw.get("feed") or ""),
                published_at=raw.get("published_at"),
            )
        except Exception:
            return SimpleNamespace(
                id=str(raw.get("fingerprint") or raw.get("id") or ""),
                title=str(raw.get("title") or ""),
                summary=str(raw.get("summary") or raw.get("description") or ""),
                url=str(raw.get("url") or raw.get("source_url") or raw.get("link") or ""),
                source=str(raw.get("source") or raw.get("feed") or ""),
                published_at=raw.get("published_at"),
            )
    return raw


def _item_title(item: Any) -> str:
    return str(getattr(item, "title", "") or "") if not isinstance(item, dict) else str(item.get("title") or "")


def _item_url(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("url") or item.get("source_url") or item.get("link") or "")
    return str(getattr(item, "url", "") or getattr(item, "source_url", "") or "")


def _item_summary(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("summary") or item.get("description") or "")
    return str(getattr(item, "summary", "") or getattr(item, "description", "") or "")


def _item_source(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("source") or item.get("feed") or "")
    return str(getattr(item, "source", "") or getattr(item, "feed", "") or "")


def _fingerprint(item: Any) -> str:
    """Fingerprint via Part A selection.item_fingerprint when available."""
    try:
        from src.content.selection import item_fingerprint

        return item_fingerprint(item)
    except Exception:
        pass
    item_id = getattr(item, "id", "") if not isinstance(item, dict) else item.get("id", "")
    if item_id:
        return str(item_id)
    seed = f"{_item_title(item)}|{_item_url(item)}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _normalise_item(raw: Any) -> dict:
    """JSON-safe view of an item (for CLI output / post records)."""
    item = _as_item(raw)
    published_at = getattr(item, "published_at", None)
    return {
        "title": _item_title(item),
        "summary": _item_summary(item),
        "source_url": _item_url(item),
        "url": _item_url(item),
        "source": _item_source(item),
        "fingerprint": _fingerprint(item),
        "published_at": published_at.isoformat() if hasattr(published_at, "isoformat") else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


_SAMPLE_ITEMS: list[dict] = [
    {
        "title": "IMO advances next steps on shipping decarbonization",
        "summary": "IMO member states have agreed the next steps in shipping's "
        "decarbonization pathway, with new measures aimed at cutting "
        "greenhouse gas emissions from international shipping.",
        "url": "https://www.imo.org/en/MediaCentre/PressBriefings/Pages/Default.aspx",
        "source": "IMO",
    },
    {
        "title": "Seafarer welfare remains central to safe shipping",
        "summary": "Crew welfare, rest and fair treatment at sea continue to "
        "shape maritime safety discussions, with a focus on supporting "
        "seafarers on long voyages.",
        "url": "https://www.imo.org/en/MediaCentre/PressBriefings/Pages/Default.aspx",
        "source": "IMO",
    },
    {
        "title": "Ports invest in greener, safer vessel operations",
        "summary": "Ports are adopting cleaner shore power and safer berthing "
        "practices as shipping works to reduce emissions and improve "
        "safety for crews and coastal communities.",
        "url": "https://splash247.com/feed/",
        "source": "Splash 247",
    },
]


def _sample_items(max_items: int) -> list[Any]:
    return [_as_item(item) for item in _SAMPLE_ITEMS[:max_items]]


def _collect_via_part_a(
    sample: bool, feeds: list[dict], max_items: int
) -> tuple[list[Any] | None, str | None]:
    """Try Part A research; return (items, error). items=None = unavailable."""
    try:
        from src.research.engine import ResearchEngine
        from src.research.providers import LocalSampleProvider, RSSFeedProvider
    except Exception as exc:
        return None, f"research providers unavailable: {exc}"
    try:
        if sample or not feeds:
            providers = [LocalSampleProvider()]
        else:
            providers = [RSSFeedProvider(feeds)]
        engine = ResearchEngine(providers)
        items = engine.run()
        if not items:
            return None, "research engine returned no items"
        return list(items[:max_items]), None
    except Exception as exc:
        return None, f"research failed: {exc}"


def collect_items(
    root: Path, sample: bool = False, max_items: int = 3
) -> tuple[list[Any], list[str]]:
    """Collect research items (ResearchItem objects); returns (items, errors)."""
    configs = _load_configs(root)
    research_cfg = configs.get("research") or {}
    feeds = research_cfg.get("feeds") or []
    if sample or not feeds:
        # LocalSampleProvider is the sample source (Part A); the local
        # _sample_items list is only a fallback if Part A is unavailable.
        items, error = _collect_via_part_a(True, feeds, max_items)
        if items:
            return items, []
        return _sample_items(max_items), [error] if error else []
    items, error = _collect_via_part_a(sample, feeds, max_items)
    if items:
        return items, []
    return [], [error] if error else ["research returned no items"]


# --------------------------------------------------------------------------
# Scoring / caption / format (Part A with fallbacks)
# --------------------------------------------------------------------------

def _fallback_score(item: Any) -> SimpleNamespace:
    score = 60.0
    if _item_title(item):
        score += 10.0
    if _item_summary(item):
        score += 5.0
    if _item_url(item):
        score += 5.0
    total = min(score, 85.0)
    band = "strong candidate" if total >= 75 else "possible"
    return SimpleNamespace(total=total, band=band, dimensions={})


def _score_item(item: Any) -> Any:
    """Return a ScoreResult (Part A) or a fallback namespace with .total/.band."""
    item = _as_item(item)
    try:
        from src.content.scoring import score_item

        result = score_item(item)
        if hasattr(result, "total"):
            return result
    except Exception:
        pass
    return _fallback_score(item)


def _make_caption(item: Any, score: Any, brand: dict) -> str:
    item = _as_item(item)
    try:
        from src.content.caption import generate_caption

        return str(generate_caption(item, score, brand))
    except Exception:
        pass
    hashtags = " ".join(
        str(h) for h in (brand.get("hashtags") or ["#Maritime", "#Shipping", "#Seafarers"])
    )
    source = _item_source(item)
    caption = f"{_item_title(item)}\n\n{_item_summary(item)}\n"
    if _item_url(item):
        caption += f"\nSource: {source + ' ' if source else ''}{_item_url(item)}\n"
    caption += "\nFollow HeyMariner for trusted maritime updates.\n\n" + hashtags
    return caption[:2000]


def _decide_format(item: Any, score: Any, generation: dict) -> str:
    item = _as_item(item)
    try:
        from src.content.decision import decide_format

        return str(decide_format(item, score, generation))
    except Exception:
        pass
    total = float(getattr(score, "total", 0) or 0)
    return "IMAGE_POST" if total >= 60 else "NO_POST"


# --------------------------------------------------------------------------
# Main pipeline
# --------------------------------------------------------------------------

def run_pipeline(
    root: Path | str = ".",
    sample: bool = False,
    dry_run: bool = True,
    auto_publish: bool = False,
    max_items: int = 3,
) -> dict:
    """Run research -> score -> generate -> gate -> publish/queue.

    Returns a summary dict with keys ``researched``, ``scored``,
    ``selected``, ``pending``, ``published``, ``dry_run`` and ``errors``.
    Per-item exceptions are recorded and processing continues.
    """
    root = Path(root)
    configs = _load_configs(root)
    settings = _settings(root)
    brand_cfg = configs.get("brand") or {}
    brand = {
        "name": brand_cfg.get("name", "HeyMariner"),
        "colors": brand_cfg.get("colors", DEFAULT_BRAND["colors"]),
        "hashtags": brand_cfg.get("hashtags", ["#Maritime", "#Shipping", "#Seafarers"]),
        "tagline": brand_cfg.get("tagline", DEFAULT_BRAND["tagline"]),
        "cta": brand_cfg.get("cta"),
        "attribution": brand_cfg.get("attribution", True),
    }
    generation_cfg = configs.get("generation") or {}
    publishing_cfg = configs.get("publishing") or {}
    if settings is not None:
        threshold = float(getattr(settings, "content_threshold", 60.0) or 60.0)
        page_id = getattr(settings, "page_id", None)
        page_token = getattr(settings, "page_token", None)
        api_version = getattr(settings, "api_version", "v21.0") or "v21.0"
    else:
        threshold = float(publishing_cfg.get("content_threshold", 60) or 60)
        page_id = os.environ.get("META_PAGE_ID")
        page_token = os.environ.get("META_PAGE_ACCESS_TOKEN")
        api_version = os.environ.get("META_API_VERSION", "v21.0")

    summary: dict[str, Any] = {
        "researched": 0,
        "scored": 0,
        "selected": 0,
        "pending": 0,
        "published": 0,
        "dry_run": dry_run,
        "errors": [],
    }

    items, collect_errors = collect_items(root, sample=sample, max_items=max_items)
    summary["errors"].extend(collect_errors)
    summary["researched"] = len(items)

    state = StateStore(root / "data" / "state")
    client = FacebookClient(
        page_id=page_id,
        page_token=page_token,
        api_version=api_version,
        dry_run=dry_run,
        timeout=30,
    )
    publisher = FacebookPublisher(client)

    with tempfile.TemporaryDirectory(prefix="heymariner-") as tmpdir:
        for raw_item in items:
            item = _as_item(raw_item)
            fingerprint = _fingerprint(item)
            try:
                score = _score_item(item)
                summary["scored"] += 1
                total = float(getattr(score, "total", 0) or 0)
                validated = bool(_item_title(item) and _item_url(item))
                if total < threshold or not validated:
                    content_type = "NO_POST"
                else:
                    content_type = _decide_format(item, score, generation_cfg)
                if content_type == "NO_POST":
                    state.mark_processed(
                        fingerprint, {"score": total, "reason": "NO_POST"}
                    )
                    continue
                summary["selected"] += 1

                caption = _make_caption(item, score, brand)
                post: dict[str, Any] = {
                    "fingerprint": fingerprint,
                    "title": _item_title(item),
                    "caption": caption,
                    "format": content_type,
                    "score": total,
                    "source_url": _item_url(item),
                    "source": _item_source(item),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }

                is_duplicate = state.is_processed(fingerprint) or state.is_published(fingerprint)
                # Pre-publish content validation (Master Command §18):
                # title/caption/format/source must all check out, or the
                # gate must not allow publishing.
                from src.validation.checks import validate_post

                post_errors = validate_post(post)
                if post_errors:
                    summary["errors"].append(
                        f"{fingerprint}: validation failed: {'; '.join(post_errors)}"
                    )
                validated = validated and not post_errors
                gate = check_publishing_gate(
                    dry_run=dry_run,
                    auto_publish=auto_publish,
                    page_id=page_id,
                    page_token=page_token,
                    validated=validated,
                    is_duplicate=is_duplicate,
                    content_type=content_type,
                )
                # Generate the brand card in the temp dir (not committed);
                # it is used for publishing and re-generated on publish
                # from a pending post, so pending records do not
                # reference the temp path.
                image_path = Path(tmpdir) / f"{fingerprint}.jpg"
                try:
                    generate_brand_card(
                        item,
                        brand=brand,
                        output_path=image_path,
                        size=(1080, 1080),
                    )
                except Exception as exc:
                    summary["errors"].append(
                        f"{fingerprint}: brand card failed: {exc}"
                    )
                    image_path = None  # type: ignore[assignment]

                if gate.allowed:
                    if content_type == "VIDEO" and image_path is not None:
                        # No real video footage exists: build a slideshow
                        # from the brand card. If ffmpeg is unavailable,
                        # fall back to an image post rather than failing.
                        from src.video.assembler import assemble_slideshow

                        video_path = assemble_slideshow(
                            [image_path], Path(tmpdir) / f"{fingerprint}.mp4"
                        )
                        if video_path is not None:
                            post["video_path"] = str(video_path)
                        else:
                            post["format"] = "IMAGE_POST"
                            post["image_path"] = str(image_path)
                    elif image_path is not None:
                        post["image_path"] = str(image_path)
                    result = publisher.publish(post)
                    post_id = result.get("post_id") or result.get("id")
                    state.mark_published(fingerprint, post_id, {"score": total})
                    state.mark_processed(fingerprint, {"score": total, "post_id": post_id})
                    summary["published"] += 1
                else:
                    save_pending(root, post)
                    state.mark_processed(fingerprint, {"score": total})
                    summary["pending"] += 1
            except Exception as exc:
                summary["errors"].append(f"{fingerprint}: {exc}")
                continue

    return summary
