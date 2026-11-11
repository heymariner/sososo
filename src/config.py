"""Configuration loading and validation for HeyMariner.

Secrets (page id / page token) are read from the environment only --
never from files and never written to files. See ``src/utils/secrets.py``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


def load_json(path) -> dict:
    """Load a JSON file, returning ``{}`` if it does not exist.

    Raises the underlying error for malformed JSON / unreadable files
    other than a missing file.
    """
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


def get_env(name: str, default=None):
    """Return env var *name*, or *default* when missing/empty."""
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def get_env_bool(name: str, default: bool = False) -> bool:
    """Return env var *name* parsed as a bool, or *default* if unset.

    Truthy values: ``1``, ``true``, ``yes``, ``on`` (case-insensitive).
    Falsy values: ``0``, ``false``, ``no``, ``off``, ``""``.
    """
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _get_env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass
class Settings:
    """Runtime settings, resolved from the environment.

    Explicit constructor arguments win over the environment; when an
    argument is left at its default, the corresponding env var (if
    set) is used, otherwise the documented default applies.
    """

    dry_run: bool = True
    auto_publish: bool = False
    max_daily_posts: int = 2
    max_daily_videos: int = 1
    quiet_hours: str = "22:00-06:00"
    content_threshold: float = 60.0
    duplicate_threshold: float = 0.85
    api_version: str = "v21.0"
    page_id: str | None = None
    page_token: str | None = None

    def __post_init__(self):
        if "DRY_RUN" in os.environ:
            self.dry_run = get_env_bool("DRY_RUN", self.dry_run)
        if "AUTO_PUBLISH" in os.environ:
            self.auto_publish = get_env_bool("AUTO_PUBLISH", self.auto_publish)
        if "MAX_DAILY_POSTS" in os.environ:
            self.max_daily_posts = _get_env_int("MAX_DAILY_POSTS", self.max_daily_posts)
        if "MAX_DAILY_VIDEOS" in os.environ:
            self.max_daily_videos = _get_env_int("MAX_DAILY_VIDEOS", self.max_daily_videos)
        if "QUIET_HOURS" in os.environ:
            self.quiet_hours = get_env("QUIET_HOURS", self.quiet_hours)
        if "CONTENT_THRESHOLD" in os.environ:
            self.content_threshold = _get_env_float("CONTENT_THRESHOLD", self.content_threshold)
        if "DUPLICATE_THRESHOLD" in os.environ:
            self.duplicate_threshold = _get_env_float("DUPLICATE_THRESHOLD", self.duplicate_threshold)
        if "META_API_VERSION" in os.environ:
            self.api_version = get_env("META_API_VERSION", self.api_version) or self.api_version
        if "META_PAGE_ID" in os.environ:
            self.page_id = get_env("META_PAGE_ID", self.page_id)
        if "META_PAGE_ACCESS_TOKEN" in os.environ:
            self.page_token = get_env("META_PAGE_ACCESS_TOKEN", self.page_token)


_CONFIG_FILES = {
    "brand": "brand.json",
    "content_policy": "content-policy.json",
    "publishing": "publishing.json",
    "research": "research.json",
    "generation": "generation.json",
}


def _unwrap_section(data: dict, key: str) -> dict:
    """Unwrap a config file's single-key wrapper, if present.

    Config files are written as ``{"<key>": {...}}``; callers should
    always see the inner dict. Already-unwrapped data passes through
    unchanged, so this is idempotent.
    """
    if isinstance(data, dict) and set(data.keys()) == {key}:
        inner = data.get(key)
        return inner if isinstance(inner, dict) else {}
    return data if isinstance(data, dict) else {}


def load_all_configs(root: Path) -> dict:
    """Load ``config/*.json`` under *root*.

    Returns a dict with keys ``brand``, ``content_policy``,
    ``publishing``, ``research`` and ``generation``; a missing file
    yields ``{}`` for that key. Each value is the unwrapped inner
    config dict (see :func:`_unwrap_section`).
    """
    root = Path(root)
    config_dir = root / "config"
    return {
        key: _unwrap_section(load_json(config_dir / filename), key)
        for key, filename in _CONFIG_FILES.items()
    }


def validate_config(configs: dict) -> list[str]:
    """Validate *configs* (as returned by :func:`load_all_configs`).

    Returns a list of human-readable error strings; empty means valid.
    Checks: ``brand.name``, ``brand.colors.navy`` / ``.teal``,
    ``publishing.max_daily_posts > 0``, ``research.feeds`` being a
    non-empty list whose entries each have ``url`` and ``name``, and
    ``generation.image`` having positive ``width`` / ``height``.
    """
    errors: list[str] = []

    brand = configs.get("brand") or {}
    if not isinstance(brand, dict) or not brand:
        errors.append("brand is missing")
    else:
        if not brand.get("name"):
            errors.append("brand.name is required")
        colors = brand.get("colors") or {}
        if not isinstance(colors, dict):
            errors.append("brand.colors must be an object")
        else:
            if not colors.get("navy"):
                errors.append("brand.colors.navy is required")
            if not colors.get("teal"):
                errors.append("brand.colors.teal is required")

    publishing = configs.get("publishing") or {}
    if not isinstance(publishing, dict) or not publishing:
        errors.append("publishing is missing")
    else:
        max_posts = publishing.get("max_daily_posts")
        if not isinstance(max_posts, (int, float)) or isinstance(max_posts, bool) or max_posts <= 0:
            errors.append("publishing.max_daily_posts must be > 0")

    research = configs.get("research") or {}
    if not isinstance(research, dict) or not research:
        errors.append("research is missing")
    else:
        feeds = research.get("feeds")
        if not isinstance(feeds, list) or not feeds:
            errors.append("research.feeds must be a non-empty list")
        else:
            for i, feed in enumerate(feeds):
                if not isinstance(feed, dict):
                    errors.append(f"research.feeds[{i}] must be an object")
                    continue
                if not feed.get("url"):
                    errors.append(f"research.feeds[{i}].url is required")
                if not feed.get("name"):
                    errors.append(f"research.feeds[{i}].name is required")

    generation = configs.get("generation") or {}
    if not isinstance(generation, dict) or not generation:
        errors.append("generation is missing")
    else:
        image = generation.get("image") or {}
        if not isinstance(image, dict) or not image:
            errors.append("generation.image is required")
        else:
            width = image.get("width")
            height = image.get("height")
            if not isinstance(width, (int, float)) or isinstance(width, bool) or width <= 0:
                errors.append("generation.image.width must be > 0")
            if not isinstance(height, (int, float)) or isinstance(height, bool) or height <= 0:
                errors.append("generation.image.height must be > 0")

    return errors
