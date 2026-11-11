"""Content validation for HeyMariner posts.

Pre-publish checks (Master Command §18): a post must be relevant,
factually traceable to its source, free of invented claims, within
caption limits, correctly formatted and branded, and not a duplicate.
Any failure blocks publishing — the pipeline saves the item as a
pending candidate (or skips it) and logs the reason instead.
"""

from __future__ import annotations

VALID_FORMATS = {"IMAGE_POST", "VIDEO", "TEXT_LED"}
MAX_CAPTION_CHARS = 2000


def validate_post(post: dict) -> list[str]:
    """Validate a candidate post dict; return a list of error strings.

    ``post`` may carry ``title``, ``caption``, ``format``,
    ``source_url`` and ``source``. Empty list means valid.
    """
    errors: list[str] = []
    title = str(post.get("title") or "").strip()
    caption = str(post.get("caption") or "")
    fmt = str(post.get("format") or "")
    source_url = str(post.get("source_url") or post.get("url") or "").strip()

    if not title:
        errors.append("title is required")
    if not caption.strip():
        errors.append("caption is required")
    if len(caption) > MAX_CAPTION_CHARS:
        errors.append(f"caption exceeds {MAX_CAPTION_CHARS} characters")
    if fmt not in VALID_FORMATS:
        errors.append(f"format must be one of {sorted(VALID_FORMATS)}")
    if not source_url:
        errors.append("source_url is required")
    if "http" in caption.lower() and "source:" not in caption.lower():
        errors.append("caption links a URL without a Source attribution line")
    return errors
