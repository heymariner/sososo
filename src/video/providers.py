"""Video generation providers for HeyMariner."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path


class VideoGenerationProvider(ABC):
    """Generates a video (or its script) from *script*."""

    @abstractmethod
    def generate(self, script, output_path: str | Path) -> Path:
        raise NotImplementedError


class ScriptVideoProvider(VideoGenerationProvider):
    """No-real-video provider: writes a JSON script file.

    ``generate(script, output_path)`` writes the script (scenes +
    narration) as JSON to ``output_path.with_suffix(".json")`` and
    returns that path. *script* may be a string (used as narration),
    a dict, or a list of scene dicts.
    """

    def generate(self, script, output_path: str | Path) -> Path:
        out = Path(output_path).with_suffix(".json")
        out.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(script, str):
            payload = {
                "scenes": [{"narration": script, "duration_seconds": 10}],
                "narration": script,
            }
        elif isinstance(script, dict):
            payload = script
        elif isinstance(script, list):
            payload = {"scenes": script}
        else:
            payload = {"scenes": [{"narration": str(script)}]}
        with out.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        return out


class ExternalVideoProvider(VideoGenerationProvider):
    """Placeholder for an external video API.

    Without a video API key it raises :class:`RuntimeError`; with one
    it raises :class:`NotImplementedError` (provider-specific call
    to be implemented; no real API is called here).
    """

    def __init__(self, api_key: str | None = None, provider: str = "external") -> None:
        self.api_key = api_key or os.environ.get("VIDEO_API_KEY")
        self.provider = provider

    def generate(self, script, output_path: str | Path) -> Path:
        if not self.api_key:
            raise RuntimeError(
                "External video provider not configured: set VIDEO_API_KEY "
                "in the environment (or pass api_key=...) before using "
                f"the {self.provider!r} video provider."
            )
        raise NotImplementedError(
            f"External video generation via provider {self.provider!r} is "
            "not implemented: add the provider-specific API call here "
            "(do not call a real API from tests)."
        )
