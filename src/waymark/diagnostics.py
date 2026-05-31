"""Local diagnostics for Waymark data health."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from waymark.backup import BACKUP_TABLES
from waymark.storage import connection, init_database


@dataclass(frozen=True)
class DatabaseHealth:
    integrity_details: tuple[str, ...]
    foreign_key_violations: tuple[str, ...]
    table_counts: dict[str, int]

    @property
    def integrity_ok(self) -> bool:
        return self.integrity_details == ("ok",)

    @property
    def foreign_keys_ok(self) -> bool:
        return not self.foreign_key_violations

    @property
    def ok(self) -> bool:
        return self.integrity_ok and self.foreign_keys_ok


def collect_database_health(db_path: Path) -> DatabaseHealth:
    init_database(db_path)
    with connection(db_path) as conn:
        integrity_rows = conn.execute("PRAGMA integrity_check").fetchall()
        foreign_key_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
        table_counts: dict[str, int] = {}
        for table in BACKUP_TABLES:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            table_counts[table] = int(row[0]) if row is not None else 0

    return DatabaseHealth(
        integrity_details=tuple(str(row[0]) for row in integrity_rows),
        foreign_key_violations=tuple(
            f"{row[0]} row {row[1]} -> {row[2]} ({row[3]})" for row in foreign_key_rows
        ),
        table_counts=table_counts,
    )


def format_database_health(health: DatabaseHealth) -> str:
    lines = [
        "Integrity: ok" if health.integrity_ok else "Integrity: needs attention",
        "Foreign keys: ok" if health.foreign_keys_ok else "Foreign keys: needs attention",
        "",
        "User data rows",
    ]
    lines.extend(f"- {table}: {count}" for table, count in health.table_counts.items())

    if not health.integrity_ok:
        lines.append("")
        lines.append("Integrity details")
        lines.extend(f"- {detail}" for detail in health.integrity_details)

    if health.foreign_key_violations:
        lines.append("")
        lines.append("Foreign key violations")
        lines.extend(f"- {violation}" for violation in health.foreign_key_violations)

    return "\n".join(lines)
