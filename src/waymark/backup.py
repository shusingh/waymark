"""Full local backup and restore for a Waymark home.

A backup is a single versioned JSON snapshot of every user-data table. It is
explicit and local-only: nothing is uploaded, and restore never silently
clobbers an existing home. The derived FTS index is not stored; it is rebuilt by
table triggers when entries are re-inserted on restore.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from waymark.exports import (
    format_entry_markdown,
    format_reflection_markdown,
    format_timeline_markdown,
)
from waymark.storage import (
    connection,
    init_database,
    list_entries,
    list_reflections,
    list_sources,
    utc_now,
)

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

BACKUP_TABLE_COLUMNS = {
    "entries": (
        "id",
        "title",
        "raw_text",
        "summary",
        "type",
        "mood",
        "source",
        "created_at",
        "updated_at",
    ),
    "tags": ("id", "name", "created_at"),
    "sources": ("id", "type", "path", "original_filename", "imported_at", "metadata_json"),
    "reflections": (
        "id",
        "period_type",
        "period_start",
        "period_end",
        "summary",
        "wins_json",
        "patterns_json",
        "suggestions_json",
        "created_at",
    ),
    "decisions": (
        "id",
        "title",
        "context",
        "status",
        "options_json",
        "pros_cons_json",
        "final_choice",
        "confidence",
        "review_date",
        "outcome",
        "created_at",
        "updated_at",
    ),
    "entry_tags": ("entry_id", "tag_id"),
    "decision_entries": ("decision_id", "entry_id", "created_at"),
    "entry_embeddings": (
        "entry_id",
        "model",
        "vector_json",
        "dimensions",
        "created_at",
        "updated_at",
    ),
}


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


@dataclass(frozen=True)
class PortableBundleSummary:
    path: Path
    files: tuple[Path, ...]
    table_counts: dict[str, int]
    total_rows: int
    memory_count: int
    reflection_count: int
    source_count: int


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
        existing_counts = _database_table_counts(conn)
        existing_total = sum(existing_counts.values())
        if existing_total and not force:
            raise BackupError(
                f"Target already holds {existing_total} user-data row(s). "
                "Use force to overwrite it."
            )

        overwrote = bool(existing_total)
        if overwrote:
            _clear_user_tables(conn)

        counts: dict[str, int] = {}
        for table in BACKUP_TABLES:
            rows = tables.get(table, [])
            counts[table] = len(rows)
            if not rows:
                continue
            columns = list(rows[0].keys())
            column_list = ", ".join(columns)
            placeholders = ", ".join("?" for _ in columns)
            try:
                conn.executemany(
                    f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})",
                    [tuple(row[column] for column in columns) for row in rows],
                )
            except sqlite3.Error as error:
                raise BackupError(f"Could not restore backup table {table}: {error}") from error

    return RestoreSummary(
        table_counts=counts,
        total_rows=sum(counts.values()),
        overwrote=overwrote,
    )


def write_portable_bundle(
    db_path: Path,
    out_dir: Path,
    *,
    force: bool = False,
) -> PortableBundleSummary:
    """Write a restore-ready and human-readable Waymark bundle to a folder."""

    if not db_path.exists():
        raise BackupError(f"No Waymark database found at {db_path}.")

    resolved_dir = out_dir.expanduser().resolve()
    if resolved_dir.exists() and not resolved_dir.is_dir():
        raise BackupError("Portable bundle target must be a folder path.")
    if resolved_dir.exists() and any(resolved_dir.iterdir()) and not force:
        raise BackupError(
            f"Portable bundle folder is not empty: {resolved_dir}. Use force to write there."
        )
    resolved_dir.mkdir(parents=True, exist_ok=True)

    backup_summary = write_backup(
        db_path,
        resolved_dir / "waymark-backup.json",
        force=force,
    )
    entries = sorted(list_entries(db_path, limit=1_000_000), key=lambda entry: entry.id)
    reflections = sorted(
        list_reflections(db_path, limit=1_000_000),
        key=lambda reflection: reflection.id,
    )
    sources = sorted(list_sources(db_path, limit=1_000_000), key=lambda source: source.id)

    written_files = [backup_summary.path]
    written_files.append(
        _write_bundle_text(
            resolved_dir / "README.md",
            _format_bundle_readme(
                backup_summary=backup_summary,
                memory_count=len(entries),
                reflection_count=len(reflections),
                source_count=len(sources),
            ),
            force=force,
        )
    )
    written_files.append(
        _write_bundle_text(
            resolved_dir / "markdown" / "timeline.md",
            format_timeline_markdown(db_path, entries),
            force=force,
        )
    )
    written_files.append(
        _write_bundle_text(
            resolved_dir / "markdown" / "sources.md",
            _format_sources_markdown(sources),
            force=force,
        )
    )

    for entry in entries:
        written_files.append(
            _write_bundle_text(
                resolved_dir / "markdown" / "memories" / _memory_filename(entry.id, entry.title),
                format_entry_markdown(db_path, entry),
                force=force,
            )
        )
    for reflection in reflections:
        written_files.append(
            _write_bundle_text(
                resolved_dir
                / "markdown"
                / "reflections"
                / _reflection_filename(reflection.id, reflection.period_type),
                format_reflection_markdown(reflection),
                force=force,
            )
        )

    return PortableBundleSummary(
        path=resolved_dir,
        files=tuple(written_files),
        table_counts=backup_summary.table_counts,
        total_rows=backup_summary.total_rows,
        memory_count=len(entries),
        reflection_count=len(reflections),
        source_count=len(sources),
    )


def _validate_backup(obj: Any) -> None:
    if not isinstance(obj, dict):
        raise BackupError("Backup is not a valid Waymark backup object.")
    version = obj.get("waymark_backup_version")
    if version != BACKUP_VERSION:
        raise BackupError(
            f"Unsupported backup version {version!r}; expected {BACKUP_VERSION}."
        )
    tables = obj.get("tables")
    if not isinstance(tables, dict):
        raise BackupError("Backup is missing its tables section.")
    unexpected_tables = sorted(set(tables) - set(BACKUP_TABLES))
    if unexpected_tables:
        raise BackupError(f"Backup contains unknown table(s): {', '.join(unexpected_tables)}")
    for table in BACKUP_TABLES:
        if table not in tables:
            raise BackupError(f"Backup is missing table: {table}")
        _validate_table_rows(table, tables[table])


def _table_counts(snapshot: dict[str, Any]) -> dict[str, int]:
    tables: dict[str, Any] = snapshot["tables"]
    return {table: len(tables.get(table, [])) for table in BACKUP_TABLES}


def _database_table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in BACKUP_TABLES:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        counts[table] = int(row[0]) if row is not None else 0
    return counts


def _clear_user_tables(conn: sqlite3.Connection) -> None:
    for table in reversed(BACKUP_TABLES):
        conn.execute(f"DELETE FROM {table}")


def _validate_table_rows(table: str, rows: Any) -> None:
    if not isinstance(rows, list):
        raise BackupError(f"Backup table {table} must be a list.")
    expected_columns = set(BACKUP_TABLE_COLUMNS[table])
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise BackupError(f"Backup row {index} in table {table} is not an object.")
        actual_columns = set(row)
        missing = sorted(expected_columns - actual_columns)
        unexpected = sorted(actual_columns - expected_columns)
        if missing:
            raise BackupError(
                f"Backup row {index} in table {table} is missing column(s): "
                f"{', '.join(missing)}"
            )
        if unexpected:
            raise BackupError(
                f"Backup row {index} in table {table} has unknown column(s): "
                f"{', '.join(unexpected)}"
            )


def _write_bundle_text(path: Path, content: str, *, force: bool) -> Path:
    if path.exists() and path.is_dir():
        raise BackupError(f"Portable bundle output is a folder, not a file: {path}")
    if path.exists() and not force:
        raise BackupError(f"Portable bundle file already exists: {path}. Use force to overwrite.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _format_bundle_readme(
    *,
    backup_summary: BackupSummary,
    memory_count: int,
    reflection_count: int,
    source_count: int,
) -> str:
    lines = [
        "# Waymark Portable Bundle",
        "",
        f"Created: {utc_now()}",
        "",
        "## Restore",
        "",
        "Restore the exact local data with:",
        "",
        "```powershell",
        "waymark backup restore .\\waymark-backup.json",
        "```",
        "",
        "## Contents",
        "",
        "- `waymark-backup.json`: complete restore-ready data snapshot",
        "- `markdown/timeline.md`: readable timeline export",
        "- `markdown/memories/`: one Markdown file per memory",
        "- `markdown/reflections/`: one Markdown file per saved reflection",
        "- `markdown/sources.md`: imported source metadata",
        "",
        "Original imported files are not copied into this bundle; source metadata is stored in "
        "the backup and in `markdown/sources.md`.",
        "",
        "## Counts",
        "",
        f"- Memories: {memory_count}",
        f"- Reflections: {reflection_count}",
        f"- Sources: {source_count}",
        f"- Backup rows: {backup_summary.total_rows}",
    ]
    lines.extend(f"- {table}: {count}" for table, count in backup_summary.table_counts.items())
    lines.append("")
    return "\n".join(lines)


def _format_sources_markdown(sources: list[Any]) -> str:
    lines = [
        "# Waymark Sources",
        "",
        f"Exported sources: {len(sources)}",
        "",
    ]
    if not sources:
        lines.extend(["No imported sources yet.", ""])
        return "\n".join(lines)

    for source in sources:
        metadata = json.dumps(source.metadata, indent=2, sort_keys=True)
        lines.extend(
            [
                f"## Source #{source.id}",
                "",
                f"- Type: {source.type}",
                f"- Filename: {source.original_filename or 'none'}",
                f"- Path: {source.path or 'none'}",
                f"- Imported: {source.imported_at}",
                "",
                "```json",
                metadata,
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def _memory_filename(entry_id: int, title: str) -> str:
    return f"{entry_id:06d}-{_slug(title)}.md"


def _reflection_filename(reflection_id: int, period_type: str) -> str:
    return f"{reflection_id:06d}-{_slug(period_type)}.md"


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized[:80].strip("-") or "untitled"
