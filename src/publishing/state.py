"""Persistent publishing state (processed / published fingerprints)."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateStore:
    """Stores ``processed.json`` and ``published.json`` under *root*.

    Entries are dicts with at least a ``fingerprint`` key. Writes are
    atomic-ish (temp file + rename) and corrupt JSON is tolerated
    (treated as an empty list).
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # -- generic JSON list handling ---------------------------------------
    def load_json_list(self, name: str) -> list[dict]:
        path = self.root / name
        if not path.exists():
            return []
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (ValueError, OSError):
            return []
        return data if isinstance(data, list) else []

    def _save(self, name: str, data: list[dict]) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent), prefix=f".{name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp_name, path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    # -- processed ----------------------------------------------------------
    def is_processed(self, fingerprint: str) -> bool:
        return any(
            entry.get("fingerprint") == fingerprint
            for entry in self.load_json_list("processed.json")
        )

    def mark_processed(self, fingerprint: str, meta: dict | None = None) -> None:
        entries = self.load_json_list("processed.json")
        entries = [
            e for e in entries if e.get("fingerprint") != fingerprint
        ]
        entry: dict[str, Any] = {"fingerprint": fingerprint, "marked_at": _now_iso()}
        if meta:
            entry.update(meta)
        entries.append(entry)
        self._save("processed.json", entries)

    def list_processed(self) -> list[dict]:
        return self.load_json_list("processed.json")

    # -- published ----------------------------------------------------------
    def is_published(self, fingerprint: str) -> bool:
        return any(
            entry.get("fingerprint") == fingerprint
            for entry in self.load_json_list("published.json")
        )

    def mark_published(
        self,
        fingerprint: str,
        post_id: str | None,
        meta: dict | None = None,
    ) -> None:
        entries = self.load_json_list("published.json")
        entries = [
            e for e in entries if e.get("fingerprint") != fingerprint
        ]
        entry: dict[str, Any] = {
            "fingerprint": fingerprint,
            "post_id": post_id,
            "marked_at": _now_iso(),
        }
        if meta:
            entry.update(meta)
        entries.append(entry)
        self._save("published.json", entries)

    def list_published(self) -> list[dict]:
        return self.load_json_list("published.json")
