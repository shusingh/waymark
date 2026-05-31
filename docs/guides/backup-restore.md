# Backup & restore

A Waymark home should be safe to keep, move, and recover — without ever leaving
your machine. `waymark backup` writes a single, versioned **JSON snapshot** of
every user-data table and restores it on demand.

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
- Into a home that **already holds memories**, it refuses unless you pass
  `--force`, which clears existing user data first and then restores.

```bash
waymark backup restore .\backups\waymark-backup.json --force
```

## Move your memory trail to another machine

1. `waymark backup create waymark-backup.json` on the old machine.
2. Copy the JSON file across (it's plain, local, and portable).
3. Set `WAYMARK_HOME` on the new machine if you want a specific location.
4. `waymark backup restore waymark-backup.json`.

Everything stays on disk on both ends — no network access is involved.
