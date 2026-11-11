"""Facebook Graph API client for HeyMariner.

No real HTTP is ever made while ``dry_run=True`` (the default): every
request returns a ``{"dry_run": True, ...}`` marker instead. When
``dry_run=False`` the page token is sent only as an ``Authorization:
Bearer`` header -- never in the URL and never in logs.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

import logging

_logger = logging.getLogger("heymariner")

try:
    from src.logging_config import log_event as _part_a_log_event
    from src.logging_config import setup_logging as _setup_logging

    _setup_logging()

    def _log_event(event: str, **fields: Any) -> None:
        """Log via Part A ``src.logging_config.log_event``.

        Part A signature is ``log_event(logger, event, **fields)`` and
        it redacts token/secret fields; never pass a token here.
        """
        try:
            _part_a_log_event(_logger, event, **fields)
        except TypeError:
            # Fallback for a (logger-less) log_event(event, **fields).
            _part_a_log_event(event, **fields)  # type: ignore[misc]

except Exception:  # pragma: no cover - logging_config absent
    def _log_event(event: str, **fields: Any) -> None:  # type: ignore[no-redef]
        redacted = {
            k: ("[REDACTED]" if "token" in k.lower() or "secret" in k.lower() else v)
            for k, v in fields.items()
        }
        _logger.info("%s %s", event, redacted)

# Backwards-compatible alias used inside this module.
log_event = _log_event


class FacebookAPIError(Exception):
    """Raised for non-2xx responses from the Facebook Graph API."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_code: int | str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code

    def __str__(self) -> str:
        return self.message


class FacebookClient:
    """Thin wrapper around the Facebook Graph API for a single Page."""

    def __init__(
        self,
        page_id: str | None = None,
        page_token: str | None = None,
        api_version: str = "v21.0",
        dry_run: bool = True,
        timeout: int = 30,
    ) -> None:
        self.page_id = page_id or os.environ.get("META_PAGE_ID")
        self.page_token = page_token or os.environ.get("META_PAGE_ACCESS_TOKEN")
        self.api_version = api_version
        self.dry_run = dry_run
        self.timeout = timeout

    @property
    def base_url(self) -> str:
        return f"https://graph.facebook.com/{self.api_version}"

    # -- low-level request -------------------------------------------------
    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> dict:
        method = method.upper()
        log_event(
            "facebook.request",
            method=method,
            endpoint=endpoint,
            dry_run=self.dry_run,
            page_id=self.page_id,
        )
        if self.dry_run:
            # Never touch the network in dry-run mode, for GET or POST.
            return {"dry_run": True, "endpoint": endpoint, "method": method}

        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self.page_token}"}
        try:
            response = requests.request(
                method,
                url,
                params=params,
                data=data,
                files=files,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise FacebookAPIError(f"Facebook request failed: {exc}") from exc

        if response.status_code == 429:
            raise FacebookAPIError(
                "Facebook rate limit exceeded (HTTP 429)",
                status_code=429,
                error_code=_error_code(response),
            )
        if response.status_code == 401:
            raise FacebookAPIError(
                "Facebook authentication failed (HTTP 401): check META_PAGE_ACCESS_TOKEN",
                status_code=401,
                error_code=_error_code(response),
            )
        if not 200 <= response.status_code < 300:
            detail = _error_message(response)
            raise FacebookAPIError(
                f"Facebook API error (HTTP {response.status_code}): {detail}",
                status_code=response.status_code,
                error_code=_error_code(response),
            )
        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": response.text}
        return payload if isinstance(payload, dict) else {"data": payload}

    # -- publishing --------------------------------------------------------
    def publish_photo(self, image_path: str | Path, caption: str = "") -> dict:
        path = Path(image_path)
        if self.dry_run:
            log_event("facebook.publish_photo", dry_run=True, image=str(path))
            return {"dry_run": True, "id": "dry-run-photo-id"}
        with open(path, "rb") as fh:
            result = self._request(
                "POST",
                f"/{self.page_id}/photos",
                data={"caption": caption},
                files={"source": fh},
            )
        log_event("facebook.publish_photo", dry_run=False, image=str(path))
        return result

    def publish_video(
        self, video_path: str | Path, title: str = "", description: str = ""
    ) -> dict:
        path = Path(video_path)
        if self.dry_run:
            log_event("facebook.publish_video", dry_run=True, video=str(path))
            return {"dry_run": True, "id": "dry-run-video-id"}
        with open(path, "rb") as fh:
            result = self._request(
                "POST",
                f"/{self.page_id}/videos",
                data={"title": title, "description": description},
                files={"source": fh},
            )
        log_event("facebook.publish_video", dry_run=False, video=str(path))
        return result

    def publish_text(self, message: str) -> dict:
        if self.dry_run:
            log_event("facebook.publish_text", dry_run=True)
            return {"dry_run": True, "id": "dry-run-post-id"}
        result = self._request(
            "POST", f"/{self.page_id}/feed", data={"message": message}
        )
        log_event("facebook.publish_text", dry_run=False)
        return result

    # -- reading -----------------------------------------------------------
    def get_page_info(self) -> dict:
        return self._request(
            "GET",
            f"/{self.page_id}",
            params={"fields": "id,name,fan_count"},
        )

    def get_posts(self, limit: int = 10) -> dict:
        return self._request(
            "GET", f"/{self.page_id}/posts", params={"limit": limit}
        )

    def list_comments(self, post_id: str) -> dict:
        return self._request("GET", f"/{post_id}/comments")

    def reply_to_comment(self, comment_id: str, message: str) -> dict:
        if self.dry_run:
            log_event("facebook.reply_to_comment", dry_run=True, comment_id=comment_id)
            return {
                "dry_run": True,
                "id": "dry-run-comment-reply-id",
                "endpoint": f"/{comment_id}/comments",
                "method": "POST",
            }
        result = self._request(
            "POST", f"/{comment_id}/comments", data={"message": message}
        )
        log_event("facebook.reply_to_comment", dry_run=False, comment_id=comment_id)
        return result

    def list_conversations(self) -> dict:
        # Note: reading Page conversations requires the pages_messaging
        # permission and may be unavailable until approved.
        return self._request("GET", f"/{self.page_id}/conversations")


def _error_code(response: "requests.Response") -> int | str | None:
    try:
        error = response.json().get("error") or {}
        return error.get("code")
    except Exception:
        return None


def _error_message(response: "requests.Response") -> str:
    try:
        error = response.json().get("error") or {}
        return str(error.get("message") or response.text)[:500]
    except Exception:
        return response.text[:500]
