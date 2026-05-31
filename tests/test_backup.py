from __future__ import annotations

import json
from pathlib import Path

import pytest

from waymark.backup import (
    BackupError,
    create_backup,
    read_backup,
    restore_backup,
    write_backup,
    write_portable_bundle,
)
from waymark.storage import (
    add_decision,
    add_entry,
    add_reflection,
    add_source,
    get_entry,
    init_database,
    link_decision_entry,
    list_decisions,
    list_entries,
    list_reflections,
    list_sources,
    search_entries,
    upsert_entry_embedding,
)


def _seed_home(db_path: Path) -> int:
    init_database(db_path)
    source_id = add_source(
        db_path,
        source_type="markdown",
        path="/notes/a.md",
        original_filename="a.md",
    )
    entry_id = add_entry(
        db_path,
        raw_text="Switched the build to event sourcing today.",
        memory_type="project",
        title="Event sourcing switch",
        summary="Switched the build to event sourcing today.",
        tags=("architecture", "build"),
        source=f"source:{source_id}",
    )
    decision_id = add_decision(
        db_path,
        title="Adopt event sourcing?",
        context="Tradeoffs in the write model.",
        options=("yes", "no"),
    )
    link_decision_entry(db_path, decision_id=decision_id, entry_id=entry_id)
    add_reflection(
        db_path,
        period_type="week",
        period_start="2026-05-25",
        period_end="2026-05-31",
        summary="Made architecture progress.",
        wins=("event sourcing switch",),
    )
    upsert_entry_embedding(db_path, entry_id=entry_id, model="test-model", vector=(0.1, 0.2, 0.3))
    return entry_id


def test_create_backup_captures_all_user_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    _seed_home(db_path)

    snapshot = create_backup(db_path)

    assert snapshot["waymark_backup_version"] == 1
    tables = snapshot["tables"]
    assert len(tables["entries"]) == 1
    assert len(tables["sources"]) == 1
    assert len(tables["decisions"]) == 1
    assert len(tables["decision_entries"]) == 1
    assert len(tables["reflections"]) == 1
    assert len(tables["entry_embeddings"]) == 1
    assert len(tables["tags"]) == 2
    assert len(tables["entry_tags"]) == 2


def test_write_and_restore_roundtrip_into_fresh_home(tmp_path: Path) -> None:
    src_db = tmp_path / "src" / "waymark.sqlite3"
    backup_path = tmp_path / "backup.json"
    _seed_home(src_db)
    write_backup(src_db, backup_path)

    dest_db = tmp_path / "dest" / "waymark.sqlite3"
    summary = restore_backup(read_backup(backup_path), dest_db)

    assert summary.overwrote is False
    entries = list_entries(dest_db)
    assert len(entries) == 1
    restored = get_entry(dest_db, entries[0].id)
    assert restored is not None
    assert restored.title == "Event sourcing switch"
    assert restored.tags == ("architecture", "build")
    assert len(list_sources(dest_db)) == 1
    assert len(list_decisions(dest_db)) == 1
    assert len(list_reflections(dest_db)) == 1
    # FTS triggers re-fire on restore insert, so keyword search still works.
    assert [entry.title for entry in search_entries(dest_db, query="sourcing")] == [
        "Event sourcing switch"
    ]


def test_write_backup_refuses_overwrite_without_force(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    _seed_home(db_path)
    backup_path = tmp_path / "backup.json"
    write_backup(db_path, backup_path)

    with pytest.raises(BackupError, match="already exists"):
        write_backup(db_path, backup_path)

    forced = write_backup(db_path, backup_path, force=True)
    assert forced.path == backup_path.resolve()


def test_write_backup_requires_existing_database(tmp_path: Path) -> None:
    with pytest.raises(BackupError, match="No Waymark database"):
        write_backup(tmp_path / "missing.sqlite3", tmp_path / "out.json")


def test_write_portable_bundle_creates_backup_and_markdown_exports(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    _seed_home(db_path)
    bundle_path = tmp_path / "bundle"

    summary = write_portable_bundle(db_path, bundle_path)

    assert summary.path == bundle_path.resolve()
    assert summary.memory_count == 1
    assert summary.reflection_count == 1
    assert summary.source_count == 1
    assert (bundle_path / "waymark-backup.json").exists()
    assert (bundle_path / "README.md").exists()
    assert (bundle_path / "markdown" / "timeline.md").exists()
    assert (bundle_path / "markdown" / "sources.md").exists()
    assert (bundle_path / "markdown" / "memories" / "000001-event-sourcing-switch.md").exists()
    assert (bundle_path / "markdown" / "reflections" / "000001-week.md").exists()

    readme = (bundle_path / "README.md").read_text(encoding="utf-8")
    assert "waymark backup restore" in readme
    assert "Original imported files are not copied" in readme


def test_write_portable_bundle_refuses_nonempty_folder_without_force(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    _seed_home(db_path)
    bundle_path = tmp_path / "bundle"
    bundle_path.mkdir()
    (bundle_path / "existing.txt").write_text("already here", encoding="utf-8")

    with pytest.raises(BackupError, match="not empty"):
        write_portable_bundle(db_path, bundle_path)

    summary = write_portable_bundle(db_path, bundle_path, force=True)
    assert summary.path == bundle_path.resolve()
    assert (bundle_path / "existing.txt").exists()


def test_restore_refuses_nonempty_home_without_force(tmp_path: Path) -> None:
    src_db = tmp_path / "src.sqlite3"
    _seed_home(src_db)
    backup = read_backup(write_backup(src_db, tmp_path / "b.json").path)

    dest_db = tmp_path / "dest.sqlite3"
    _seed_home(dest_db)

    with pytest.raises(BackupError, match="already holds"):
        restore_backup(backup, dest_db)

    summary = restore_backup(backup, dest_db, force=True)
    assert summary.overwrote is True
    # Overwrite replaces rather than appends.
    assert len(list_entries(dest_db)) == 1


def test_restore_refuses_source_only_home_without_force(tmp_path: Path) -> None:
    src_db = tmp_path / "src.sqlite3"
    _seed_home(src_db)
    backup = read_backup(write_backup(src_db, tmp_path / "b.json").path)

    dest_db = tmp_path / "dest.sqlite3"
    init_database(dest_db)
    add_source(
        dest_db,
        source_type="text",
        path="/notes/orphan.txt",
        original_filename="orphan.txt",
    )

    with pytest.raises(BackupError, match="user-data row"):
        restore_backup(backup, dest_db)

    summary = restore_backup(backup, dest_db, force=True)
    assert summary.overwrote is True
    assert [source.original_filename for source in list_sources(dest_db)] == ["a.md"]


def test_read_backup_rejects_unknown_version(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps({"waymark_backup_version": 99, "tables": {}}),
        encoding="utf-8",
    )

    with pytest.raises(BackupError, match="Unsupported backup version"):
        read_backup(bad)


def test_read_backup_rejects_missing_tables_section(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"waymark_backup_version": 1}), encoding="utf-8")

    with pytest.raises(BackupError, match="missing its tables"):
        read_backup(bad)


def test_restore_rejects_unknown_backup_columns(tmp_path: Path) -> None:
    src_db = tmp_path / "src.sqlite3"
    _seed_home(src_db)
    backup = read_backup(write_backup(src_db, tmp_path / "b.json").path)
    backup["tables"]["entries"][0]["unexpected_column"] = "surprise"

    with pytest.raises(BackupError, match="unknown column"):
        restore_backup(backup, tmp_path / "dest.sqlite3")
