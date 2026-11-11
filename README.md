# HeyMariner

**Trusted maritime updates for seafarers and shipping professionals.**

HeyMariner is an automated maritime content engine. It researches trusted
maritime sources, scores and selects the stories that matter, generates
on-brand image cards (and short video scripts), and publishes approved
posts to the HeyMariner Facebook Page — with a human in the loop by
default.

Repo: <https://github.com/heymariner/sososo>

> **Safety first:** the system ships in dry-run mode (`DRY_RUN=true`,
> `AUTO_PUBLISH=false`). Nothing is published to Facebook until a human
> approves a post and live publishing is explicitly switched on. No
> secrets, tokens, or Page IDs are stored anywhere in this repository.

---

## 1. What the system does

1. **Research** — fetches maritime news from configured feeds (IMO,
   Lloyd's List, TradeWinds, Splash 247, gCaptain, Maritime Executive)
   twice a day.
2. **Score** — every item is scored 0–100 on relevance, recency, source
   reliability, and topic fit. Items below 40 are rejected; 60+ are
   publishable; 90+ are priority.
3. **Decide** — the engine picks a format (`IMAGE_POST`, `VIDEO_POST`,
   `TEXT_POST`, or `NO_POST`) and checks for duplicates.
4. **Generate** — builds a 1080×1080 on-brand image card (navy
   `#0B2C4A`, teal `#14919B`, white) and a caption of at most 2000
   characters, always attributed to its source.
5. **Queue** — publishable items land in `data/pending/` as JSON for
   human review. Nothing is published from the queue automatically.
6. **Publish** — only approved posts, only from the manual publishing
   workflow, only when live mode is on.
7. **Monitor** — comments and messages are checked every 6 hours;
   spam is flagged and genuine questions are surfaced for a human reply.

## 2. Architecture

```
Muse (build / review)
   │
   ▼
GitHub repo  https://github.com/heymariner/sososo
   │
   ▼
GitHub Actions ──► Secrets (META_PAGE_ID, META_PAGE_ACCESS_TOKEN,
   │                META_API_VERSION) — env vars only, never logged
   ▼
Meta Graph API ──► HeyMariner Facebook Page
   │                (posts, photos, comments, messages*)
   ▼
data/state/  (deduplication + daily counters, committed back by Actions)
```

`*` Messenger access depends on the permissions Meta grants the app;
see §6 and `docs/META_API.md`. If messaging is unavailable, monitoring
still covers comments and the system reports the limitation instead of
failing.

See `docs/ARCHITECTURE.md` for the full diagram and module map.

## 3. Repo structure

```
.
├── .github/workflows/
│   ├── maritime-content.yml      # research + queue, 07:00 & 19:00 UTC
│   ├── facebook-publishing.yml   # manual, live publishing only
│   ├── facebook-monitoring.yml   # comments/messages, every 6h
│   └── health-check.yml          # tests + config validation on push/PR
├── assets/brand/
│   ├── heymariner-logo.svg       # clean SVG recreation of the logo
│   └── heymariner-logo.jpg       # original JPG — add manually (see below)
├── config/
│   ├── brand.json                # name, colours, tone, CTA, hashtags
│   ├── content-policy.json       # allowed/banned content, limits
│   ├── publishing.json           # limits, quiet hours, thresholds
│   ├── research.json             # feeds, categories, lookback
│   └── generation.json           # image/video/text settings
├── data/
│   ├── pending/                  # human-review queue (+ example-post.json)
│   └── state/                    # dedup + counters (committed by Actions)
├── docs/                         # architecture, setup, API, security, ...
├── prompts/                      # research / caption / image prompts
├── scripts/                      # validate_config.py, run_dry_run.py,
│                                 # health_check.py
├── src/
│   ├── cli.py                    # `python -m src.cli publish|monitor|...`
│   ├── content/                  # scoring, duplicates, captions
│   ├── facebook/                 # Graph API client, monitoring
│   ├── image/                    # 1080x1080 card generation (Pillow)
│   ├── research/                 # RSS/HTML providers, classification
│   ├── utils/                    # config loading, env helpers
│   ├── validation/               # publishing gates
│   └── video/                    # short video scripting/rendering
└── tests/                        # pytest suite (see §19)
```

## 4. Required GitHub Secrets

Set these in **Settings → Secrets and variables → Actions**:

| Secret | Purpose |
| --- | --- |
| `META_PAGE_ID` | Numeric ID of the HeyMariner Facebook Page |
| `META_PAGE_ACCESS_TOKEN` | Long-lived Page access token (see §5) |
| `META_API_VERSION` | e.g. `v21.0` (no leading slash) |

No other secrets are needed. Secrets are passed to workflows only as
environment variables and are never echoed, printed, or committed.
There is no `.env` file in the repo, and `.gitignore` blocks one.

## 5. Meta / Facebook setup

1. Create a Meta developer app at <https://developers.facebook.com/> and
   add the **Facebook Login / Pages** products as needed.
2. Create or select the HeyMariner Facebook Page.
3. Request the permissions in §6 and complete Meta's app review for any
   permission that requires it.
4. Generate a **Page access token**: get a User token with the page
   permissions, then exchange it for a long-lived Page token
   (`GET /{page-id}?fields=access_token`). Long-lived Page tokens do not
   expire while the page admin's grant stands, but they can be revoked —
   see §17 on rotation.
5. Store the token and Page ID as the GitHub Secrets in §4.
6. Verify with a dry run before ever going live (see §18).

## 6. Required permissions

| Permission | Used for |
| --- | --- |
| `pages_manage_posts` | Publishing posts and photos to the Page |
| `pages_read_engagement` | Reading comments, reactions, and post insights |
| `pages_read_user_content` | Reading user content on the Page |
| `pages_messaging` | Reading/replying to Page messages — **only if Meta grants it; Messenger access is frequently restricted, and the monitor treats its absence as a degraded mode, not a failure** |
| `pages_show_list` | Listing Pages the app can manage |

The app requests the least privilege it needs; it never asks for
personal-profile access.

## 7. GitHub Actions setup

1. Push the repo to <https://github.com/heymariner/sososo>.
2. Add the three secrets from §4.
3. Confirm the workflows appear under the **Actions** tab:
   `Maritime Content`, `Facebook Publishing`, `Facebook Monitoring`,
   `Health Check`.
4. Run **Health Check** manually once (Actions → Health Check →
   Run workflow) and confirm it is green.
5. Run **Maritime Content** manually once and check the
   `pending-posts` artifact — it should contain queued JSON files, and
   nothing should have been published.
6. Only then consider a live publish (see §15).

## 8. Research system

- Feeds are listed in `config/research.json` (IMO, Lloyd's List,
  TradeWinds, Splash 247, gCaptain, Maritime Executive), with a
  reliability rating per feed (`high`/`medium`) and a type
  (`rss` or `rss/html`).
- The IMO press-briefings page is primarily HTML and may not expose a
  stable RSS feed; it is marked `rss/html` and the research code must
  handle it gracefully rather than failing the whole run.
- `max_items_per_feed: 10`, `lookback_days: 7` — only recent items are
  considered.
- `LocalSampleProvider` (used in tests and dry runs) returns 3 sample
  items without any network access.
- Sources are classified (`classify_source`): `imo.org` is high
  reliability; unknown blogs are not. Claims are classified as fact vs
  commentary (`classify_claim`).
- Feeds are configurable: edit `config/research.json` and re-run
  `python scripts/validate_config.py`.

## 9. Image generation

- Local generation with Pillow — no external image service, no API key.
- Output: 1080×1080 JPG (see `config/generation.json`).
- Layout: title at the top in navy on white, teal wave accent, the
  HeyMariner logo top-left, footer brand line.
- The logo used is `assets/brand/heymariner-logo.svg` (a clean
  recreation). The original `heymariner-logo.jpg` should be placed at
  `assets/brand/heymariner-logo.jpg` manually — GitHub push tooling
  does not support binary uploads, so the automation cannot add it.
- No misleading visuals: the card never implies a specific vessel,
  incident, or location the story does not show.

## 10. Video generation

- Video is script-based (`config/generation.json`: `enabled: true`,
  `max_duration_seconds: 60`, `provider: "script"`).
- At most 1 video per day (`max_daily_videos: 1`).
- Rendering needs `ffmpeg` on the machine that renders; if it is
  missing, video generation is skipped with a clear log message and the
  post falls back to `IMAGE_POST`. See `docs/TROUBLESHOOTING.md`.

## 11. Publishing system

- The content workflow (`maritime-content.yml`) runs at **07:00 and
  19:00 UTC** and only ever writes to `data/pending/` and `data/state/`.
- The publishing workflow (`facebook-publishing.yml`) is **manual only**
  (`workflow_dispatch`, no schedule). It takes a `live` boolean input
  (default `false`).
- The CLI entry point is `python -m src.cli publish`.
- Publishing gates (see `src/validation/gates.py`, `tests/test_gates.py`)
  block a post unless **all** of these hold: not a dry run,
  auto-publish on, Page ID + token present, post validated and approved,
  not a duplicate, and a publishable format.
- Daily limits: max 2 posts and max 1 video per day; quiet hours
  22:00–06:00 UTC.
- State (what was published, fingerprints seen) is committed back to
  `data/state/` by the content workflow when it changes.

## 12. Comment monitoring

- Runs every 6 hours (`facebook-monitoring.yml`, cron `0 */6 * * *`)
  via `python -m src.cli monitor`.
- Comments are classified: spam is flagged, genuine questions are
  surfaced for a human to answer. The system never auto-replies with
  invented facts.
- See `docs/META_API.md` for the endpoints used.

## 13. Message monitoring

- Page messages are checked in the same monitoring run, **if** the app
  holds `pages_messaging`.
- Messenger access may not be available for a new app; the monitor logs
  that clearly and continues with comments. Do not treat a missing
  messaging permission as a failure — treat it as a known limitation
  and answer messages in Meta Business Suite until access is granted.

## 14. Configuration

All behaviour is driven by JSON in `config/` — no code changes needed
to tune the system:

| File | Controls |
| --- | --- |
| `config/brand.json` | Name, tagline, colours, fonts, tone, CTA, hashtags |
| `config/content-policy.json` | Allowed/banned topics, 2000-char caption cap, source requirement |
| `config/publishing.json` | Daily limits, quiet hours, thresholds, dry-run defaults |
| `config/research.json` | Feeds, reliability, categories, lookback |
| `config/generation.json` | Image size/format, video on/off and length |

Validate any change with:

```bash
python scripts/validate_config.py
```

## 15. Auto-publish mode

Auto-publish is **off by default** and should stay off until the
pipeline has run cleanly in dry-run mode for at least a few days.

To enable it:

1. Set `AUTO_PUBLISH=true` and `DRY_RUN=false` — in the workflow
   inputs / environment, not in the repo.
2. Run the publishing workflow with `live: true`.
3. Even in auto-publish mode, the gates still apply: only posts that
   are validated, approved, non-duplicate, and within daily limits and
   quiet hours are published. Approval still comes from the pending
   queue — auto-publish never publishes an unreviewed item.

## 16. Human approval mode (default)

1. The content run writes candidates to `data/pending/*.json` and
   uploads them as the `pending-posts` artifact.
2. A human reads each file and checks the source link.
3. Approve by setting `"status": "approved"` in the JSON (or reject
   with `"status": "rejected"` and a `"review_note"`). See
   `data/pending/README.md`.
4. Run **Facebook Publishing** with `live: true` to publish approved
   posts, or with `live: false` for a dry run that logs exactly what
   *would* have been published.

## 17. Security

- No secrets, tokens, or Page IDs anywhere in the repo — ever.
  (`.gitignore` blocks `.env`; workflows pass secrets only as env vars
  and never echo them.)
- Least privilege: the app requests only the permissions in §6; the
  workflows use `contents: read` except where a write is genuinely
  needed.
- Logs redact tokens: the Facebook client never prints an access token
  or a full request URL containing one.
- See `docs/SECURITY.md`.

### Token rotation

1. Generate a new long-lived Page token in Meta (see §5, step 4).
2. Update the `META_PAGE_ACCESS_TOKEN` GitHub Secret.
3. Re-run **Health Check** and a dry-run publish to confirm.
4. Revoke the old token in Meta. If a token is ever suspected leaked,
   revoke it immediately and rotate — do not wait for a scheduled
   rotation.

## 18. How to run manually

```bash
# 1. Install dependencies (Python 3.11+)
pip install -r requirements.txt

# 2. Validate configuration
python scripts/validate_config.py

# 3. Dry run — researches, scores, queues; publishes nothing
DRY_RUN=true AUTO_PUBLISH=false python scripts/run_dry_run.py

# 4. Check the pending queue
ls data/pending/

# 5. Health check
python scripts/health_check.py

# 6. Publish (dry run — safe)
DRY_RUN=true AUTO_PUBLISH=false python -m src.cli publish

# 7. Publish live — only after human approval, with real secrets set
DRY_RUN=false AUTO_PUBLISH=true \
  META_PAGE_ID=<id> META_PAGE_ACCESS_TOKEN=<token> META_API_VERSION=v21.0 \
  python -m src.cli publish

# 8. Monitor comments/messages
python -m src.cli monitor
```

## 19. How to test safely

```bash
pip install -r requirements.txt
pytest -q
```

- The suite covers config loading, scoring bands, duplicate detection,
  caption rules, the Facebook client in dry-run mode (no network),
  publishing gates, and research providers (including a bad feed).
- The Facebook tests use `dry_run=True` and a fake token — they never
  touch the Graph API.
- The sample provider returns 3 items with no network access.
- Always test with `DRY_RUN=true` and `live: false` first. A dry run
  that logs "would publish" is the correct result — it proves the
  gates work without posting anything.

## 20. Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| Token expired / `OAuthException` | Rotate the Page token (§17); re-check secrets |
| Permission denied (`(#200)`) | Missing permission from §6; check app review status |
| Post rejected as duplicate | Fingerprint already in `data/state/`; check the pending file |
| Rate limit (`#4` / 429) | Back off; the daily limits exist to avoid this |
| `ffmpeg` missing | Video falls back to `IMAGE_POST`; install ffmpeg to enable video |
| Feed returns nothing | Publisher changed its feed — update `config/research.json` |
| Workflow fails on `validate_config` | Run it locally; it prints the exact bad key |

Full guide: `docs/TROUBLESHOOTING.md`.

## 21. License

MIT — see `LICENSE`. Copyright (c) 2026 HeyMariner.
