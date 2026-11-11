"""Pending-post queue: posts awaiting human approval.

Files live in ``<root>/data/pending/<fingerprint>.json`` plus a
``<fingerprint>.txt`` caption file. *root* is the repo root; a ``data``
directory or a ``pending`` directory is also accepted.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def pending_dir(root: Path | str) -> Path:
    root = Path(root)
    if root.name == "pending":
        return root
    if root.name == "data":
        return root / "pending"
    return root / "data" / "pending"


def _fingerprint(post: dict) -> str:
    fingerprint = post.get("fingerprint")
    if fingerprint:
        return str(fingerprint)
    seed = str(post.get("source_url") or post.get("title") or "")
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def save_pending(root: Path | str, post: dict) -> Path:
    """Write *post* to the pending queue; return the JSON file path."""
    directory = pending_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    fingerprint = _fingerprint(post)
    record: dict[str, Any] = dict(post)
    record.setdefault("fingerprint", fingerprint)
    record.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    record.setdefault("status", "pending")
    json_path = directory / f"{fingerprint}.json"
    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, ensure_ascii=False)
    caption = str(record.get("caption") or "")
    txt_path = directory / f"{fingerprint}.txt"
    txt_path.write_text(caption, encoding="utf-8")
    return json_path


def load_pending(root: Path | str) -> list[dict]:
    """Load all pending posts, sorted by ``created_at`` (oldest first)."""
    directory = pending_dir(root)
    if not directory.exists():
        return []
    posts: list[dict] = []
    for json_path in sorted(directory.glob("*.json")):
        try:
            with json_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (ValueError, OSError):
            continue
        if isinstance(data, dict):
            posts.append(data)
    posts.sort(key=lambda p: str(p.get("created_at") or ""))
    return posts


def approve_pending(root: Path | str, fingerprint: str) -> dict | None:
    """Mark the pending post *fingerprint* as approved; return it or None."""
    directory = pending_dir(root)
    json_path = directory / f"{fingerprint}.json"
    if not json_path.exists():
        return None
    try:
        with json_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (ValueError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    data["status"] = "approved"
    data["approved"] = True
    data["approved_at"] = datetime.now(timezone.utc).isoformat()
    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    return data
