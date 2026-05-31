"""Full local backup and restore for a Waymark home.

A backup is a single versioned JSON snapshot of every user-data table. It is
explicit and local-only: nothing is uploaded, and restore never silently
clobbers an existing home. The derived FTS index is not stored; it is rebuilt by
table triggers when entries are re-inserted on restore.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from waymark.storage import connection, init_database, utc_now

BACKUP_VERSION = 1

# User-data tables in dependency order: parents before children so that a
# restore with foreign keys enabled inserts cleanly. The derived `entries_fts`
# table is intentionally excluded (its triggers rebuild it from `entries`).
BACKUP_TABLES = (
    "entries",
    "tags",
    "sources",
    "reflections",
    "decisions",
    "entry_tags",
    "decision_entries",
    "entry_embeddings",
)


class BackupError(ValueError):
    """Raised when a backup cannot be read, written, or restored."""


@dataclass(frozen=True)
class BackupSummary:
    path: Path
    table_counts: dict[str, int]
    total_rows: int


@dataclass(frozen=True)
class RestoreSummary:
    table_counts: dict[str, int]
    total_rows: int
    overwrote: bool


def create_backup(db_path: Path) -> dict[str, Any]:
    """Read every user-data table into a serialisable snapshot dict."""

    init_database(db_path)
    tables: dict[str, list[dict[str, Any]]] = {}
    with connection(db_path) as conn:
        for table in BACKUP_TABLES:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            tables[table] = [dict(row) for row in rows]
    return {
        "waymark_backup_version": BACKUP_VERSION,
        "created_at": utc_now(),
        "tables": tables,
    }


def write_backup(db_path: Path, out_path: Path, *, force: bool = False) -> BackupSummary:
    """Write a JSON backup of ``db_path`` to ``out_path``."""

    if not db_path.exists():
        raise BackupError(f"No Waymark database found at {db_path}.")

    resolved_out = out_path.expanduser().resolve()
    if resolved_out.exists() and not force:
        raise BackupError(f"Backup file already exists: {resolved_out}. Use force to overwrite.")
    if resolved_out.is_dir():
        raise BackupError("Backup target is a folder; choose a file path.")

    snapshot = create_backup(db_path)
    resolved_out.parent.mkdir(parents=True, exist_ok=True)
    resolved_out.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    counts = _table_counts(snapshot)
    return BackupSummary(
        path=resolved_out,
        table_counts=counts,
        total_rows=sum(counts.values()),
    )


def read_backup(path: Path) -> dict[str, Any]:
    """Load and validate a backup JSON file."""

    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise BackupError(f"Backup file not found: {resolved}")
    if not resolved.is_file():
        raise BackupError("Backup path must be a file.")

    try:
        loaded = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BackupError(f"Could not read backup file: {error}") from error

    _validate_backup(loaded)
    return cast(dict[str, Any], loaded)


def restore_backup(backup: dict[str, Any], db_path: Path, *, force: bool = False) -> RestoreSummary:
    """Rebuild ``db_path`` from a validated backup snapshot.

    Refuses to overwrite a home that already holds memories unless ``force`` is
    set, in which case existing user data is cleared first.
    """

    _validate_backup(backup)
    tables: dict[str, Any] = backup["tables"]

    init_database(db_path)
    with connection(db_path) as conn:
        existing = int(conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0])
        if existing and not force:
            raise BackupError(
                f"Target already holds {existing} memories. Use force to overwrite it."
            )

        overwrote = bool(existing)
        if overwrote:
            for table in reversed(BACKUP_TABLES):
                conn.execute(f"DELETE FROM {table}")

        counts: dict[str, int] = {}
        for table in BACKUP_TABLES:
            rows = tables.get(table, [])
            counts[table] = len(rows)
            if not rows:
                continue
            columns = list(rows[0].keys())
            column_list = ", ".join(columns)
            placeholders = ", ".join("?" for _ in columns)
            conn.executemany(
                f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})",
                [tuple(row[column] for column in columns) for row in rows],
            )

    return RestoreSummary(
        table_counts=counts,
        total_rows=sum(counts.values()),
        overwrote=overwrote,
    )


def _validate_backup(obj: Any) -> None:
    if not isinstance(obj, dict):
        raise BackupError("Backup is not a valid Waymark backup object.")
    version = obj.get("waymark_backup_version")
    if version != BACKUP_VERSION:
        raise BackupError(
            f"Unsupported backup version {version!r}; expected {BACKUP_VERSION}."
        )
    if not isinstance(obj.get("tables"), dict):
        raise BackupError("Backup is missing its tables section.")


def _table_counts(snapshot: dict[str, Any]) -> dict[str, int]:
    tables: dict[str, Any] = snapshot["tables"]
    return {table: len(tables.get(table, [])) for table in BACKUP_TABLES}
