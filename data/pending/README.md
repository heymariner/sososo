# Pending queue

`data/pending/` is the human-review queue. The research/content pipeline
writes one JSON file per candidate post here. Nothing in this directory is
published automatically.

## How a post gets here

1. A scheduled run (`maritime-content.yml`) researches the feeds in
   `config/research.json`.
2. Items are scored (see `docs/CONTENT_ENGINE.md`). Items at or above the
   content threshold (default 60) and not duplicates are written here as
   `*.json`, with `status: "pending"`.
3. The run uploads the pending files as a GitHub Actions artifact, so a
   reviewer can read them without checking out the repo.

## How to approve a post

1. Open the pending JSON file and read the title, caption, source, score,
   and format.
2. Check the source link yourself. If the facts do not match the source,
   reject the post (see below).
3. To approve: change `"status"` from `"pending"` to `"approved"`, commit
   the file, and run the publishing workflow
   (`.github/workflows/facebook-publishing.yml`) with `live` set to true —
   or, for a dry run, leave `live` off and check the logs first.
4. To reject: change `"status"` to `"rejected"` and add a short
   `"review_note"` explaining why (e.g. "source does not support the
   claim"). Rejected posts are kept as a record and are never published.
5. To edit: fix the caption/title in the JSON, keep the character limit
   (2000) and the source attribution, and set `"status"` to `"approved"`.

## Safety rules

- The default mode is dry-run (`DRY_RUN=true`, `AUTO_PUBLISH=false`).
  Nothing is published unless a human approves it and live publishing is
  explicitly switched on.
- A post is only publishable when it is validated, approved, not a
  duplicate, within the daily limits, and outside quiet hours
  (22:00–06:00 UTC) unless a human overrides it.
- Never put tokens, Page IDs, or other secrets in a pending file.

## Example

`example-post.json` in this directory shows the exact shape of a pending
post. It is a sample only — do not publish it.
