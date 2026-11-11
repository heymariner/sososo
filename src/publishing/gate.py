"""Publishing gate: all conditions must pass before a live publish."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GateResult:
    allowed: bool
    reasons: list[str] = field(default_factory=list)


def check_publishing_gate(
    *,
    dry_run: bool,
    auto_publish: bool,
    page_id: str | None,
    page_token: str | None,
    validated: bool,
    is_duplicate: bool,
    content_type: str,
) -> GateResult:
    """Return whether publishing is allowed, with reasons when not.

    Allowed only when *every* check passes: not a dry run, auto-publish
    enabled, Page id + token present, content validated, not a
    duplicate, and the content type is a real post type.
    """
    reasons: list[str] = []
    if dry_run:
        reasons.append("DRY_RUN enabled")
    if not auto_publish:
        reasons.append("AUTO_PUBLISH is false — save as pending candidate")
    if not page_id or not page_token:
        reasons.append("Missing META_PAGE_ID / META_PAGE_ACCESS_TOKEN")
    if not validated:
        reasons.append("Content not validated")
    if is_duplicate:
        reasons.append("Duplicate content (already processed/published)")
    if content_type == "NO_POST":
        reasons.append("Content type is NO_POST — nothing to publish")
    return GateResult(allowed=not reasons, reasons=reasons)
