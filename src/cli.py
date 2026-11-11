"""HeyMariner command-line interface.

Subcommands: research, generate, publish, monitor, health-check, dry-run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Allow `python -m src.cli` / `python src/cli.py` from the repo root.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _cmd_research(args) -> int:
    from src.pipeline import _normalise_item, collect_items

    items, errors = collect_items(
        Path(args.root), sample=args.sample, max_items=args.max_items
    )
    print(json.dumps(
        {"researched": len(items), "items": [_normalise_item(i) for i in items], "errors": errors},
        indent=2,
    ))
    return 0


def _cmd_generate(args) -> int:
    from src.pipeline import run_pipeline

    summary = run_pipeline(
        root=Path(args.root),
        sample=args.sample,
        dry_run=True,
        auto_publish=False,
        max_items=args.max_items,
    )
    print(json.dumps(summary, indent=2))
    return 0


def _cmd_dry_run(args) -> int:
    from src.pipeline import run_pipeline

    summary = run_pipeline(
        root=Path(args.root),
        sample=args.sample,
        dry_run=True,
        auto_publish=False,
        max_items=args.max_items,
    )
    print(json.dumps(summary, indent=2))
    return 0


def _cmd_publish(args) -> int:
    from src.facebook.client import FacebookClient
    from src.facebook.publisher import FacebookPublisher
    from src.pipeline import run_pipeline  # noqa: F401  (kept for parity)
    from src.publishing.gate import check_publishing_gate
    from src.publishing.queue import load_pending
    from src.publishing.state import StateStore

    root = Path(args.root)
    live = bool(args.live) and os.environ.get("AUTO_PUBLISH", "").strip().lower() in (
        "1", "true", "yes", "on",
    )
    dry_run = not live
    page_id = os.environ.get("META_PAGE_ID")
    page_token = os.environ.get("META_PAGE_ACCESS_TOKEN")

    pending = load_pending(root)
    state = StateStore(root / "data" / "state")
    client = FacebookClient(
        page_id=page_id, page_token=page_token, dry_run=dry_run
    )
    publisher = FacebookPublisher(client)
    published, skipped, errors = 0, 0, []
    for post in pending:
        fingerprint = str(post.get("fingerprint") or "")
        try:
            gate = check_publishing_gate(
                dry_run=dry_run,
                auto_publish=live,
                page_id=page_id,
                page_token=page_token,
                validated=bool(post.get("title") and post.get("caption")),
                is_duplicate=state.is_published(fingerprint),
                content_type=str(post.get("format") or "NO_POST"),
            )
            if not gate.allowed:
                skipped += 1
                errors.append(f"{fingerprint}: gate blocked: {'; '.join(gate.reasons)}")
                continue
            result = publisher.publish(post)
            state.mark_published(
                fingerprint, result.get("post_id") or result.get("id")
            )
            published += 1
        except Exception as exc:
            errors.append(f"{fingerprint}: {exc}")
    print(json.dumps({
        "pending": len(pending),
        "published": published,
        "skipped": skipped,
        "dry_run": dry_run,
        "errors": errors,
    }, indent=2))
    return 0


def _cmd_monitor(args) -> int:
    from src.facebook.client import FacebookClient
    from src.facebook.comments import classify_comment, should_reply
    from src.facebook.messages import summarize_conversations

    live = bool(args.live)
    dry_run = not live
    allow_replies = bool(args.allow_replies) and not dry_run
    client = FacebookClient(dry_run=dry_run)
    posts = client.get_posts(limit=args.max_items)
    comments_out: list[dict] = []
    # In dry-run mode the client returns a marker dict with no real
    # posts, so there is nothing to classify; report that honestly.
    post_items = posts.get("data") if isinstance(posts, dict) else None
    if isinstance(post_items, list):
        for post in post_items:
            post_id = str(post.get("id", ""))
            if not post_id:
                continue
            raw_comments = client.list_comments(post_id)
            comment_items = raw_comments.get("data") if isinstance(raw_comments, dict) else None
            if not isinstance(comment_items, list):
                continue
            for comment in comment_items:
                text = str(comment.get("message", ""))
                category = classify_comment(text)
                entry = {
                    "post_id": post_id,
                    "comment_id": str(comment.get("id", "")),
                    "text": text,
                    "category": category,
                    "should_reply": should_reply(category),
                    "replied": False,
                }
                if allow_replies and should_reply(category):
                    try:
                        client.reply_to_comment(
                            entry["comment_id"],
                            "Thanks for your comment — the HeyMariner team will follow up.",
                        )
                        entry["replied"] = True
                    except Exception as exc:
                        entry["reply_error"] = str(exc)
                comments_out.append(entry)
    conversations = client.list_conversations()
    conv_items = conversations.get("data") if isinstance(conversations, dict) else None
    conv_summary = summarize_conversations(conv_items if isinstance(conv_items, list) else [])
    print(json.dumps({
        "dry_run": dry_run,
        "posts": posts,
        "comments": comments_out,
        "conversations": conv_summary,
    }, indent=2))
    return 0


def _health_check_lines(root: Path) -> tuple[bool, list[str]]:
    """Shared health logic: config, env names, imports, workflows YAML."""
    lines: list[str] = []
    ok = True
    # Config validation.
    try:
        from src.config import load_all_configs, validate_config

        raw = load_all_configs(root)
        configs = {}
        for key, value in raw.items():
            if isinstance(value, dict) and set(value.keys()) == {key}:
                configs[key] = value[key]
            else:
                configs[key] = value
        errors = validate_config(configs)
        if errors:
            ok = False
            lines.append(f"config: FAIL - {'; '.join(errors)}")
        else:
            lines.append("config: PASS")
    except Exception as exc:
        ok = False
        lines.append(f"config: FAIL - {exc}")
    # Required env presence (names only, never values).
    try:
        from src.utils.secrets import check_secrets_present

        presence = check_secrets_present(["META_PAGE_ID", "META_PAGE_ACCESS_TOKEN"])
    except Exception:
        presence = {
            name: bool(os.environ.get(name))
            for name in ("META_PAGE_ID", "META_PAGE_ACCESS_TOKEN")
        }
    for name, present in presence.items():
        lines.append(f"env {name}: {'PASS' if present else 'FAIL - not set'}")
        if not present:
            ok = False
    # Imports.
    for module, label in (
        ("requests", "requests"),
        ("PIL", "Pillow"),
        ("yaml", "PyYAML"),
        ("feedparser", "feedparser"),
    ):
        try:
            __import__(module)
            lines.append(f"import {label}: PASS")
        except Exception as exc:
            ok = False
            lines.append(f"import {label}: FAIL - {exc}")
    # Workflows YAML parse.
    workflows_dir = root / ".github" / "workflows"
    if workflows_dir.exists():
        try:
            import yaml

            files = sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml"))
            if not files:
                lines.append("workflows: PASS - none found")
            else:
                for wf in files:
                    yaml.safe_load(wf.read_text(encoding="utf-8"))
                lines.append(f"workflows: PASS - {len(files)} file(s) parsed")
        except Exception as exc:
            ok = False
            lines.append(f"workflows: FAIL - {exc}")
    else:
        lines.append("workflows: PASS - none found")
    return ok, lines


def _cmd_health_check(args) -> int:
    ok, lines = _health_check_lines(Path(args.root))
    for line in lines:
        print(line)
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="heymariner", description="HeyMariner engine")
    parser.add_argument("--root", default=".", help="Repo root (default: .)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("research", help="Run research and print a JSON summary")
    p.add_argument("--root", default=".", help="Repo root (default: .)")
    p.add_argument("--sample", action="store_true")
    p.add_argument("--max-items", type=int, default=3)
    p.set_defaults(func=_cmd_research)

    p = sub.add_parser("generate", help="Generate posts (dry-run, saved as pending)")
    p.add_argument("--root", default=".", help="Repo root (default: .)")
    p.add_argument("--sample", action="store_true")
    p.add_argument("--max-items", type=int, default=3)
    p.set_defaults(func=_cmd_generate)

    p = sub.add_parser("publish", help="Publish pending posts (dry-run unless --live and AUTO_PUBLISH=true)")
    p.add_argument("--root", default=".", help="Repo root (default: .)")
    p.add_argument("--live", action="store_true")
    p.set_defaults(func=_cmd_publish)

    p = sub.add_parser("monitor", help="List posts/comments and classify them")
    p.add_argument("--root", default=".", help="Repo root (default: .)")
    p.add_argument("--max-items", type=int, default=10)
    p.add_argument("--allow-replies", action="store_true")
    p.add_argument("--live", action="store_true")
    p.set_defaults(func=_cmd_monitor)

    p = sub.add_parser("health-check", help="Validate configs, env, imports and workflows")
    p.add_argument("--root", default=".", help="Repo root (default: .)")
    p.set_defaults(func=_cmd_health_check)

    p = sub.add_parser("dry-run", help="Run the full pipeline in dry-run mode")
    p.add_argument("--root", default=".", help="Repo root (default: .)")
    p.add_argument("--sample", action="store_true")
    p.add_argument("--max-items", type=int, default=3)
    p.set_defaults(func=_cmd_dry_run)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
