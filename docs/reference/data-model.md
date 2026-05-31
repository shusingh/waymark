# Data model

Waymark stores everything in one local SQLite database
(`$WAYMARK_HOME/waymark.sqlite3`). All timestamps are UTC ISO strings. The
schema is intentionally simple and relational; there is no hidden vector
database.

## Tables

| Table | Purpose |
| --- | --- |
| `entries` | Memory cards: `title`, `raw_text`, `summary`, `type`, `mood`, `source`, timestamps. |
| `tags` | Unique tag names. |
| `entry_tags` | Many-to-many link between entries and tags. |
| `decisions` | First-class decisions: context, options, status, final choice, confidence, review date, outcome. |
| `decision_entries` | Links decisions to the memory entries that informed them. |
| `reflections` | Saved reflections per period, with wins, patterns, and suggestions. |
| `sources` | Imported files: type, path, original filename, metadata. |
| `entry_embeddings` | Explicitly generated vectors per entry and model. |
| `entries_fts` | FTS5 full-text index over entries — **derived**, rebuilt by triggers. |

## How pieces connect

- A memory **entry** can carry a `source` of `manual`, a local-AI draft, or
  `source:<id>` pointing at a row in `sources` (for imported files). Retrieval
  resolves that into a label such as `pdf: brief.pdf`.
- **Tags** are normalized (lowercased, de-duplicated, sorted) and shared across
  entries through `entry_tags`.
- **Decisions** link to the entries that informed them via `decision_entries`,
  keeping each decision's evidence trail visible.
- **Embeddings** are opt-in. Nothing is embedded until you run
  `waymark embeddings backfill --apply`.

## Full-text search

`entries_fts` is a contentless FTS5 index kept in sync with `entries` by insert,
update, and delete triggers. Because it is derived, it is **excluded from
backups**; restoring entries re-fires the triggers and rebuilds the index
automatically.

See the canonical schema in
[`src/waymark/storage.py`](https://github.com/shusingh/waymark/blob/main/src/waymark/storage.py).
