"""Social publisher abstraction + Facebook implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.facebook.client import FacebookClient


class SocialPublisher(ABC):
    """Publishes a prepared post dict to a social platform."""

    @abstractmethod
    def publish(self, post: dict) -> dict:
        """Publish *post* and return the platform result dict."""
        raise NotImplementedError


class FacebookPublisher(SocialPublisher):
    """Publishes HeyMariner posts via :class:`FacebookClient`."""

    def __init__(self, client: FacebookClient) -> None:
        self.client = client

    def publish(self, post: dict) -> dict:
        fmt = str(post.get("format", "")).upper()
        caption = str(post.get("caption") or post.get("text") or "")
        if fmt == "IMAGE_POST":
            result = self.client.publish_photo(
                post["image_path"], caption=caption
            )
        elif fmt == "VIDEO":
            result = self.client.publish_video(
                post["video_path"],
                title=str(post.get("title") or ""),
                description=caption,
            )
        elif fmt == "TEXT_LED":
            result = self.client.publish_text(caption)
        else:
            # Unknown / unspecified format: fall back to a text post if
            # there is text, otherwise treat an image as an image post.
            if post.get("image_path"):
                result = self.client.publish_photo(
                    post["image_path"], caption=caption
                )
            else:
                result = self.client.publish_text(caption)
        post_id = result.get("id") or result.get("post_id")
        return {**result, "post_id": post_id, "format": fmt}
