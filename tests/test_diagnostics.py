from __future__ import annotations

from pathlib import Path

from waymark.diagnostics import collect_database_health, format_database_health
from waymark.storage import add_entry, init_database


def test_collect_database_health_reports_integrity_and_counts(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    init_database(db_path)
    add_entry(
        db_path,
        raw_text="Health check memory.",
        memory_type="project",
        title="Health check",
        summary="Health check memory.",
        tags=("diagnostics",),
    )

    health = collect_database_health(db_path)
    text = format_database_health(health)

    assert health.ok is True
    assert health.table_counts["entries"] == 1
    assert health.table_counts["tags"] == 1
    assert "Integrity: ok" in text
    assert "- entries: 1" in text
