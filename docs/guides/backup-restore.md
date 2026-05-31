# Backup & restore

A Waymark home should be safe to keep, move, and recover — without ever leaving
your machine. `waymark backup` writes a versioned **JSON snapshot** of every
user-data table, restores it on demand, and can create a readable portable
folder bundle.

## Create a backup

```bash
waymark backup create .\backups\waymark-backup.json
```

The snapshot captures every user-data table: entries, tags, sources, decisions,
decision links, reflections, and embeddings. It will **not** overwrite an
existing file unless you add `--force`:

```bash
waymark backup create .\backups\waymark-backup.json --force
```

!!! note "What is *not* in the backup"
    The full-text search index is derived data and is intentionally excluded.
    When entries are restored, database triggers rebuild it automatically, so
    keyword search works immediately.

## Inspect a backup

See what a file contains — timestamp and per-table row counts — without
restoring it:

```bash
waymark backup info .\backups\waymark-backup.json
```

## Restore a backup

```bash
waymark backup restore .\backups\waymark-backup.json
```

Restore is deliberately cautious:

- Into an empty or new home, it simply rebuilds everything.
- Into a home that **already holds any user data**, it refuses unless you pass
  `--force`, which clears existing user data first and then restores.

```bash
waymark backup restore .\backups\waymark-backup.json --force
```

## Create a portable bundle

```bash
waymark backup bundle .\backups\waymark-portable
```

A bundle contains:

- `waymark-backup.json` for exact restore
- `README.md` with restore instructions and counts
- `markdown/timeline.md`
- one Markdown file per memory
- one Markdown file per saved reflection
- `markdown/sources.md`

Original imported files are not copied into the bundle. Source metadata is kept
inside the backup and readable `sources.md` export.

## Move your memory trail to another machine

1. `waymark backup create waymark-backup.json` on the old machine.
2. Copy the JSON file across (it's plain, local, and portable).
3. Set `WAYMARK_HOME` on the new machine if you want a specific location.
4. `waymark backup restore waymark-backup.json`.

Everything stays on disk on both ends — no network access is involved.
