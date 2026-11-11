"""Caption generation for HeyMariner posts.

Captions only reuse the item's own title / summary -- no quotes or
statistics are invented. Emojis are stripped.
"""

from __future__ import annotations

import re

# Broad emoji / pictograph ranges.
_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U00002B00-\U00002BFF"
    "\U0000FE00-\U0000FE0F"
    "\U0001F1E6-\U0001F1FF"
    "]+",
    flags=re.UNICODE,
)

DEFAULT_CTA = "Follow HeyMariner for trusted maritime updates."
DEFAULT_HASHTAGS = "#Maritime #Shipping #Seafarers"


def _strip_emojis(text: str) -> str:
    return _EMOJI_RE.sub("", text or "")


def _first_sentence(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    # Split on the first sentence-ending punctuation followed by space/end.
    match = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)
    return match[0].strip() if match else text


def generate_caption(item, score, brand: dict | None = None) -> str:
    """Build a post caption for *item* (<= 2000 chars, no emojis).

    Format: title, summary (truncated to 400 chars), a key-takeaway
    line drawn from the summary's first sentence, a ``Source:`` line
    when ``brand.get('attribution', True)``, the brand CTA (or the
    default), and ``#Maritime #Shipping #Seafarers``.
    ``score`` is accepted for API compatibility and is not used to
    invent content.
    """
    brand = brand or {}
    title = _strip_emojis(str(getattr(item, "title", "") or "").strip())
    summary = _strip_emojis(str(getattr(item, "summary", "") or "").strip())
    if len(summary) > 400:
        summary = summary[:397].rstrip() + "..."
    source = str(getattr(item, "source", "") or "").strip()

    takeaway_text = _first_sentence(summary) or title
    takeaway = f"Key takeaway: {takeaway_text}" if takeaway_text else ""

    cta = (
        brand.get("cta")
        or brand.get("call_to_action")
        or DEFAULT_CTA
    )
    cta = _strip_emojis(str(cta).strip())

    parts = [title]
    if summary:
        parts.append(summary)
    if takeaway:
        parts.append(takeaway)
    if brand.get("attribution", True) and source:
        parts.append(f"Source: {source}")
    parts.append(cta)
    parts.append(DEFAULT_HASHTAGS)

    caption = "\n\n".join(p for p in parts if p)
    caption = _strip_emojis(caption)
    # Collapse runs of blank lines left by emoji removal.
    caption = re.sub(r"\n{3,}", "\n\n", caption).strip()
    if len(caption) > 2000:
        caption = caption[:1997].rstrip() + "..."
    return caption


def headline_for_card(item) -> str:
    """Short title for an image card, at most 80 characters."""
    title = _strip_emojis(str(getattr(item, "title", "") or "").strip())
    if len(title) <= 80:
        return title
    truncated = title[:77].rstrip()
    # Prefer a word boundary.
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return (truncated + "...")[:80]
