"""Image generation providers for HeyMariner."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path

from src.image.card import DEFAULT_BRAND, generate_brand_card


class ImageGenerationProvider(ABC):
    """Generates an image for a prompt and saves it to *output_path*."""

    @abstractmethod
    def generate(self, prompt: str, output_path: str | Path) -> Path:
        raise NotImplementedError


class LocalCardProvider(ImageGenerationProvider):
    """Local provider: renders a HeyMariner brand card with Pillow."""

    def __init__(self, brand: dict | None = None) -> None:
        self.brand = brand or DEFAULT_BRAND

    def generate(self, prompt: str, output_path: str | Path) -> Path:
        return generate_brand_card(
            prompt, brand=self.brand, output_path=Path(output_path)
        )


class ExternalImageProvider(ImageGenerationProvider):
    """Placeholder for an external image API (e.g. OpenAI).

    Never calls a real API in this codebase: without an API key it
    raises :class:`RuntimeError`; with a key it raises
    :class:`NotImplementedError` directing the implementer to add the
    provider-specific call.
    """

    def __init__(self, api_key: str | None = None, provider: str = "openai") -> None:
        self.api_key = api_key or os.environ.get("IMAGE_API_KEY")
        self.provider = provider

    def generate(self, prompt: str, output_path: str | Path) -> Path:
        if not self.api_key:
            raise RuntimeError(
                "External image provider not configured: set IMAGE_API_KEY "
                "in the environment (or pass api_key=...) before using "
                f"the {self.provider!r} image provider."
            )
        raise NotImplementedError(
            f"External image generation via provider {self.provider!r} is "
            "not implemented: add the provider-specific API call here "
            "(do not call a real API from tests)."
        )
