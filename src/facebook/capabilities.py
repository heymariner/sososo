"""Facebook capability / permission requirements for HeyMariner.

Facebook features are gated by Page permissions that must be granted
and, for some, reviewed/approved by Meta. This module only *describes*
what each operation needs; it never calls the Graph API.
"""

from __future__ import annotations

REQUIRED_PERMISSIONS: dict[str, list[str]] = {
    "publish_photo": ["pages_manage_posts", "pages_read_engagement"],
    "publish_video": ["pages_manage_posts"],
    "publish_text": ["pages_manage_posts"],
    "read_comments": ["pages_read_engagement", "pages_read_user_content"],
    "reply_comments": ["pages_manage_posts", "pages_read_engagement"],
    "read_messages": ["pages_messaging", "pages_read_engagement"],
    "page_info": ["pages_read_engagement"],
}

CAPABILITY_NOTES: dict[str, str] = {
    "publish_photo": (
        "Publishing photos requires pages_manage_posts; the Page must be "
        "connected and the token must not be expired. Photo publishing may "
        "be unavailable until the app is approved for pages_manage_posts."
    ),
    "publish_video": (
        "Publishing videos requires pages_manage_posts. Large videos use "
        "the resumable upload flow and may be unavailable until approved."
    ),
    "publish_text": (
        "Publishing text posts requires pages_manage_posts. Text-only posts "
        "may be unavailable until the app is approved for pages_manage_posts."
    ),
    "read_comments": (
        "Reading comments requires pages_read_engagement and "
        "pages_read_user_content. Some comments may be hidden by Facebook "
        "moderation or unavailable for older posts."
    ),
    "reply_comments": (
        "Replying to comments requires pages_manage_posts and "
        "pages_read_engagement. Replies are rate-limited and may be "
        "unavailable until the app is approved."
    ),
    "read_messages": (
        "Reading Page conversations requires pages_messaging and "
        "pages_read_engagement. This is the most restricted capability: "
        "pages_messaging needs Meta app review and approval, and messages "
        "may be unavailable without it."
    ),
    "page_info": (
        "Reading basic Page info requires pages_read_engagement. Fan count "
        "and other fields may be unavailable for restricted Pages."
    ),
}


def check_capabilities(granted: set | None = None) -> dict[str, dict]:
    """Map each operation to its required permissions and grant status.

    If *granted* is None, nothing is known about the token's grants, so
    ``granted_known`` is False for every operation.
    """
    granted_set = set(granted) if granted is not None else set()
    result: dict[str, dict] = {}
    for operation, required in REQUIRED_PERMISSIONS.items():
        result[operation] = {
            "required": list(required),
            "granted_known": granted is not None,
            "granted": (
                [p for p in required if p in granted_set]
                if granted is not None
                else []
            ),
            "missing": (
                [p for p in required if p not in granted_set]
                if granted is not None
                else list(required)
            ),
            "note": CAPABILITY_NOTES.get(operation, ""),
        }
    return result
