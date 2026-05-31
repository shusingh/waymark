"""SQLite storage for Waymark's local memory system."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    summary TEXT NOT NULL,
    type TEXT NOT NULL,
    mood TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entry_tags (
    entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, tag_id)
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    context TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    options_json TEXT NOT NULL DEFAULT '[]',
    pros_cons_json TEXT NOT NULL DEFAULT '{}',
    final_choice TEXT,
    confidence INTEGER,
    review_date TEXT,
    outcome TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_entries (
    decision_id INTEGER NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (decision_id, entry_id)
);

CREATE TABLE IF NOT EXISTS reflections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_type TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    summary TEXT NOT NULL,
    wins_json TEXT NOT NULL DEFAULT '[]',
    patterns_json TEXT NOT NULL DEFAULT '[]',
    suggestions_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    path TEXT,
    original_filename TEXT,
    imported_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS entry_embeddings (
    entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    vector_json TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (entry_id, model)
);

CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
    title,
    raw_text,
    summary,
    content='entries',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
    INSERT INTO entries_fts(rowid, title, raw_text, summary)
    VALUES (new.id, new.title, new.raw_text, new.summary);
END;

CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, title, raw_text, summary)
    VALUES('delete', old.id, old.title, old.raw_text, old.summary);
END;

CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, title, raw_text, summary)
    VALUES('delete', old.id, old.title, old.raw_text, old.summary);
    INSERT INTO entries_fts(rowid, title, raw_text, summary)
    VALUES (new.id, new.title, new.raw_text, new.summary);
END;
"""

SEARCH_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


@dataclass(frozen=True)
class Entry:
    id: int
    title: str
    raw_text: str
    summary: str
    type: str
    source: str
    created_at: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class Decision:
    id: int
    title: str
    context: str
    status: str
    options: tuple[str, ...]
    final_choice: str | None
    confidence: int | None
    review_date: str | None
    outcome: str | None
    created_at: str
    entry_ids: tuple[int, ...]


@dataclass(frozen=True)
class Reflection:
    id: int
    period_type: str
    period_start: str
    period_end: str
    summary: str
    wins: tuple[str, ...]
    patterns: tuple[str, ...]
    suggestions: tuple[str, ...]
    created_at: str


@dataclass(frozen=True)
class Source:
    id: int
    type: str
    path: str | None
    original_filename: str | None
    imported_at: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class EntryEmbedding:
    entry_id: int
    model: str
    vector: tuple[float, ...]
    dimensions: int
    created_at: str


@dataclass(frozen=True)
class ScoredEntry:
    entry: Entry
    score: float


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_database(db_path: Path) -> None:
    with connection(db_path) as conn:
        conn.executescript(SCHEMA)


def clean_tag_tuple(tags: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({tag.strip().lower() for tag in tags if tag.strip()}))


def set_entry_tags(
    conn: sqlite3.Connection,
    *,
    entry_id: int,
    tags: Iterable[str],
    now: str,
) -> None:
    conn.execute("DELETE FROM entry_tags WHERE entry_id = ?", (entry_id,))
    for tag in clean_tag_tuple(tags):
        conn.execute(
            "INSERT OR IGNORE INTO tags (name, created_at) VALUES (?, ?)",
            (tag, now),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO entry_tags (entry_id, tag_id)
            SELECT ?, id FROM tags WHERE name = ?
            """,
            (entry_id, tag),
        )


def add_entry(
    db_path: Path,
    *,
    raw_text: str,
    memory_type: str,
    title: str,
    summary: str,
    tags: Iterable[str] = (),
    source: str = "manual",
) -> int:
    now = utc_now()

    with connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO entries (title, raw_text, summary, type, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, raw_text, summary, memory_type, source, now, now),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("SQLite did not return an entry id.")
        entry_id = cursor.lastrowid

        set_entry_tags(conn, entry_id=entry_id, tags=tags, now=now)

    return entry_id


def clean_required_text(value: str, *, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} cannot be empty")
    return cleaned


def update_entry(
    db_path: Path,
    *,
    entry_id: int,
    raw_text: str | None = None,
    memory_type: str | None = None,
    title: str | None = None,
    summary: str | None = None,
    tags: Iterable[str] | None = None,
) -> bool:
    now = utc_now()
    fields: list[tuple[str, str]] = []
    if raw_text is not None:
        fields.append(("raw_text", clean_required_text(raw_text, field_name="raw_text")))
    if memory_type is not None:
        fields.append(("type", clean_required_text(memory_type, field_name="type").lower()))
    if title is not None:
        fields.append(("title", clean_required_text(title, field_name="title")))
    if summary is not None:
        fields.append(("summary", clean_required_text(summary, field_name="summary")))

    with connection(db_path) as conn:
        exists = conn.execute("SELECT 1 FROM entries WHERE id = ?", (entry_id,)).fetchone()
        if exists is None:
            return False

        if fields:
            assignments = [f"{column} = ?" for column, _ in fields]
            assignments.append("updated_at = ?")
            params: list[str | int] = [value for _, value in fields]
            params.extend([now, entry_id])
            conn.execute(
                f"""
                UPDATE entries
                SET {", ".join(assignments)}
                WHERE id = ?
                """,
                params,
            )

        if tags is not None:
            set_entry_tags(conn, entry_id=entry_id, tags=tags, now=now)

    return True


def add_decision(
    db_path: Path,
    *,
    title: str,
    context: str,
    options: Iterable[str] = (),
    confidence: int | None = None,
    review_date: str | None = None,
) -> int:
    now = utc_now()
    clean_options = [option.strip() for option in options if option.strip()]

    with connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO decisions (
                title,
                context,
                options_json,
                confidence,
                review_date,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title.strip(),
                context.strip(),
                json.dumps(clean_options),
                confidence,
                review_date,
                now,
                now,
            ),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("SQLite did not return a decision id.")
        return cursor.lastrowid


def link_decision_entry(db_path: Path, *, decision_id: int, entry_id: int) -> bool:
    now = utc_now()
    with connection(db_path) as conn:
        decision_exists = conn.execute(
            "SELECT 1 FROM decisions WHERE id = ?",
            (decision_id,),
        ).fetchone()
        entry_exists = conn.execute(
            "SELECT 1 FROM entries WHERE id = ?",
            (entry_id,),
        ).fetchone()
        if decision_exists is None or entry_exists is None:
            return False

        conn.execute(
            """
            INSERT OR IGNORE INTO decision_entries (decision_id, entry_id, created_at)
            VALUES (?, ?, ?)
            """,
            (decision_id, entry_id, now),
        )
        return True


def unlink_decision_entry(db_path: Path, *, decision_id: int, entry_id: int) -> bool:
    with connection(db_path) as conn:
        cursor = conn.execute(
            """
            DELETE FROM decision_entries
            WHERE decision_id = ? AND entry_id = ?
            """,
            (decision_id, entry_id),
        )
        return cursor.rowcount > 0


def finalize_decision(
    db_path: Path,
    *,
    decision_id: int,
    final_choice: str,
    confidence: int | None = None,
) -> bool:
    now = utc_now()
    clean_choice = final_choice.strip()
    if not clean_choice:
        raise ValueError("final_choice is required")

    assignments = ["status = ?", "final_choice = ?", "updated_at = ?"]
    params: list[str | int] = ["decided", clean_choice, now]
    if confidence is not None:
        assignments.append("confidence = ?")
        params.append(confidence)
    params.append(decision_id)

    with connection(db_path) as conn:
        cursor = conn.execute(
            f"""
            UPDATE decisions
            SET {", ".join(assignments)}
            WHERE id = ?
            """,
            params,
        )
        return cursor.rowcount > 0


def record_decision_outcome(
    db_path: Path,
    *,
    decision_id: int,
    outcome: str,
) -> bool:
    now = utc_now()
    clean_outcome = outcome.strip()
    if not clean_outcome:
        raise ValueError("outcome is required")

    with connection(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE decisions
            SET status = ?, outcome = ?, updated_at = ?
            WHERE id = ?
            """,
            ("reviewed", clean_outcome, now, decision_id),
        )
        return cursor.rowcount > 0


def add_reflection(
    db_path: Path,
    *,
    period_type: str,
    period_start: str,
    period_end: str,
    summary: str,
    wins: Iterable[str] = (),
    patterns: Iterable[str] = (),
    suggestions: Iterable[str] = (),
) -> int:
    now = utc_now()
    with connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO reflections (
                period_type,
                period_start,
                period_end,
                summary,
                wins_json,
                patterns_json,
                suggestions_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                period_type,
                period_start,
                period_end,
                summary,
                json.dumps(list(wins)),
                json.dumps(list(patterns)),
                json.dumps(list(suggestions)),
                now,
            ),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("SQLite did not return a reflection id.")
        return cursor.lastrowid


def add_source(
    db_path: Path,
    *,
    source_type: str,
    path: str | None = None,
    original_filename: str | None = None,
    metadata: dict[str, object] | None = None,
) -> int:
    now = utc_now()
    with connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO sources (type, path, original_filename, imported_at, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                source_type,
                path,
                original_filename,
                now,
                json.dumps(metadata or {}, sort_keys=True),
            ),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("SQLite did not return a source id.")
        return cursor.lastrowid


def upsert_entry_embedding(
    db_path: Path,
    *,
    entry_id: int,
    model: str,
    vector: Iterable[float],
) -> bool:
    now = utc_now()
    clean_model = clean_required_text(model, field_name="model")
    clean_vector = tuple(float(value) for value in vector)
    if not clean_vector:
        raise ValueError("embedding vector cannot be empty")

    with connection(db_path) as conn:
        entry_exists = conn.execute("SELECT 1 FROM entries WHERE id = ?", (entry_id,)).fetchone()
        if entry_exists is None:
            return False
        conn.execute(
            """
            INSERT INTO entry_embeddings (
                entry_id,
                model,
                vector_json,
                dimensions,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(entry_id, model) DO UPDATE SET
                vector_json = excluded.vector_json,
                dimensions = excluded.dimensions,
                updated_at = excluded.updated_at
            """,
            (
                entry_id,
                clean_model,
                json.dumps(list(clean_vector)),
                len(clean_vector),
                now,
                now,
            ),
        )
    return True


def get_entry_embedding(
    db_path: Path,
    *,
    entry_id: int,
    model: str,
) -> EntryEmbedding | None:
    with connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT entry_id, model, vector_json, dimensions, created_at
            FROM entry_embeddings
            WHERE entry_id = ? AND model = ?
            """,
            (entry_id, model),
        ).fetchone()

    if row is None:
        return None

    vector = tuple(float(value) for value in json.loads(str(row["vector_json"])))
    return EntryEmbedding(
        entry_id=int(row["entry_id"]),
        model=str(row["model"]),
        vector=vector,
        dimensions=int(row["dimensions"]),
        created_at=str(row["created_at"]),
    )


def count_entry_embeddings(db_path: Path, *, model: str) -> int:
    with connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS generated
            FROM entry_embeddings
            WHERE model = ?
            """,
            (model,),
        ).fetchone()
    return int(row["generated"]) if row is not None else 0


def count_entries_missing_embeddings(db_path: Path, *, model: str) -> int:
    with connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS missing
            FROM entries e
            WHERE NOT EXISTS (
                SELECT 1
                FROM entry_embeddings ee
                WHERE ee.entry_id = e.id AND ee.model = ?
            )
            """,
            (model,),
        ).fetchone()
    return int(row["missing"]) if row is not None else 0


def list_entries_missing_embeddings(
    db_path: Path,
    *,
    model: str,
    limit: int = 20,
) -> list[Entry]:
    with connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                e.id,
                e.title,
                e.raw_text,
                e.summary,
                e.type,
                e.source,
                e.created_at,
                COALESCE(group_concat(t.name, ','), '') AS tags
            FROM entries e
            LEFT JOIN entry_tags et ON et.entry_id = e.id
            LEFT JOIN tags t ON t.id = et.tag_id
            WHERE NOT EXISTS (
                SELECT 1
                FROM entry_embeddings ee
                WHERE ee.entry_id = e.id AND ee.model = ?
            )
            GROUP BY e.id
            ORDER BY e.created_at DESC
            LIMIT ?
            """,
            (model, limit),
        ).fetchall()

    return [entry_from_row(row) for row in rows]


def embedding_vector_from_json(vector_json: str) -> tuple[float, ...]:
    data = json.loads(vector_json)
    if not isinstance(data, list):
        return ()
    try:
        return tuple(float(value) for value in data)
    except (TypeError, ValueError):
        return ()


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    left_vector = tuple(float(value) for value in left)
    right_vector = tuple(float(value) for value in right)
    if not left_vector or len(left_vector) != len(right_vector):
        return 0.0

    left_norm: float = sum(value * value for value in left_vector) ** 0.5
    right_norm: float = sum(value * value for value in right_vector) ** 0.5
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0

    dot_product: float = sum(
        left_value * right_value
        for left_value, right_value in zip(left_vector, right_vector, strict=True)
    )
    return dot_product / (left_norm * right_norm)


def search_entries_by_embedding(
    db_path: Path,
    *,
    model: str,
    query_vector: Iterable[float],
    limit: int = 10,
) -> list[ScoredEntry]:
    clean_model = clean_required_text(model, field_name="model")
    clean_query_vector = tuple(float(value) for value in query_vector)
    if limit <= 0 or not clean_query_vector:
        return []

    with connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                e.id,
                e.title,
                e.raw_text,
                e.summary,
                e.type,
                e.source,
                e.created_at,
                ee.vector_json,
                COALESCE(group_concat(t.name, ','), '') AS tags
            FROM entry_embeddings ee
            JOIN entries e ON e.id = ee.entry_id
            LEFT JOIN entry_tags et ON et.entry_id = e.id
            LEFT JOIN tags t ON t.id = et.tag_id
            WHERE ee.model = ?
            GROUP BY e.id, ee.vector_json
            """,
            (clean_model,),
        ).fetchall()

    scored_entries: list[ScoredEntry] = []
    for row in rows:
        vector = embedding_vector_from_json(str(row["vector_json"]))
        score = cosine_similarity(clean_query_vector, vector)
        if score <= 0.0:
            continue
        scored_entries.append(ScoredEntry(entry=entry_from_row(row), score=score))

    scored_entries.sort(key=lambda scored: (scored.score, scored.entry.created_at), reverse=True)
    return scored_entries[:limit]


def list_sources(db_path: Path, *, limit: int = 20) -> list[Source]:
    with connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, type, path, original_filename, imported_at, metadata_json
            FROM sources
            ORDER BY imported_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        Source(
            id=int(row["id"]),
            type=str(row["type"]),
            path=str(row["path"]) if row["path"] is not None else None,
            original_filename=(
                str(row["original_filename"]) if row["original_filename"] is not None else None
            ),
            imported_at=str(row["imported_at"]),
            metadata=dict(json.loads(str(row["metadata_json"]))),
        )
        for row in rows
    ]


def get_source(db_path: Path, source_id: int) -> Source | None:
    with connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, type, path, original_filename, imported_at, metadata_json
            FROM sources
            WHERE id = ?
            """,
            (source_id,),
        ).fetchone()

    if row is None:
        return None

    return Source(
        id=int(row["id"]),
        type=str(row["type"]),
        path=str(row["path"]) if row["path"] is not None else None,
        original_filename=(
            str(row["original_filename"]) if row["original_filename"] is not None else None
        ),
        imported_at=str(row["imported_at"]),
        metadata=dict(json.loads(str(row["metadata_json"]))),
    )


def get_source_by_path(
    db_path: Path,
    *,
    source_type: str,
    path: str,
) -> Source | None:
    with connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, type, path, original_filename, imported_at, metadata_json
            FROM sources
            WHERE type = ? AND path = ?
            ORDER BY imported_at DESC
            LIMIT 1
            """,
            (source_type, path),
        ).fetchone()

    if row is None:
        return None

    return Source(
        id=int(row["id"]),
        type=str(row["type"]),
        path=str(row["path"]) if row["path"] is not None else None,
        original_filename=(
            str(row["original_filename"]) if row["original_filename"] is not None else None
        ),
        imported_at=str(row["imported_at"]),
        metadata=dict(json.loads(str(row["metadata_json"]))),
    )


def source_id_from_entry(entry: Entry) -> int | None:
    if not entry.source.startswith("source:"):
        return None
    try:
        return int(entry.source.removeprefix("source:"))
    except ValueError:
        return None


def source_label(source: Source | None) -> str:
    if source is None:
        return "unknown source"
    name = source.original_filename or source.path or f"source:{source.id}"
    return f"{source.type}: {name}"


def entry_from_row(row: sqlite3.Row) -> Entry:
    return Entry(
        id=int(row["id"]),
        title=str(row["title"]),
        raw_text=str(row["raw_text"]),
        summary=str(row["summary"]),
        type=str(row["type"]),
        source=str(row["source"]),
        created_at=str(row["created_at"]),
        tags=tuple(tag for tag in str(row["tags"]).split(",") if tag),
    )


def list_reflections(db_path: Path, *, limit: int = 20) -> list[Reflection]:
    with connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                period_type,
                period_start,
                period_end,
                summary,
                wins_json,
                patterns_json,
                suggestions_json,
                created_at
            FROM reflections
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        Reflection(
            id=int(row["id"]),
            period_type=str(row["period_type"]),
            period_start=str(row["period_start"]),
            period_end=str(row["period_end"]),
            summary=str(row["summary"]),
            wins=tuple(str(item) for item in json.loads(str(row["wins_json"]))),
            patterns=tuple(str(item) for item in json.loads(str(row["patterns_json"]))),
            suggestions=tuple(str(item) for item in json.loads(str(row["suggestions_json"]))),
            created_at=str(row["created_at"]),
        )
        for row in rows
    ]


def get_reflection(db_path: Path, reflection_id: int) -> Reflection | None:
    with connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                id,
                period_type,
                period_start,
                period_end,
                summary,
                wins_json,
                patterns_json,
                suggestions_json,
                created_at
            FROM reflections
            WHERE id = ?
            """,
            (reflection_id,),
        ).fetchone()

    if row is None:
        return None

    return Reflection(
        id=int(row["id"]),
        period_type=str(row["period_type"]),
        period_start=str(row["period_start"]),
        period_end=str(row["period_end"]),
        summary=str(row["summary"]),
        wins=tuple(str(item) for item in json.loads(str(row["wins_json"]))),
        patterns=tuple(str(item) for item in json.loads(str(row["patterns_json"]))),
        suggestions=tuple(str(item) for item in json.loads(str(row["suggestions_json"]))),
        created_at=str(row["created_at"]),
    )


def entry_ids_from_row(value: object) -> tuple[int, ...]:
    return tuple(sorted(int(entry_id) for entry_id in str(value).split(",") if entry_id))


def list_decisions(db_path: Path, *, status: str | None = None, limit: int = 20) -> list[Decision]:
    filters = []
    params: list[str | int] = []
    if status:
        filters.append("d.status = ?")
        params.append(status)

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    params.append(limit)

    with connection(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT
                d.id,
                d.title,
                d.context,
                d.status,
                d.options_json,
                d.final_choice,
                d.confidence,
                d.review_date,
                d.outcome,
                d.created_at,
                COALESCE(group_concat(de.entry_id, ','), '') AS entry_ids
            FROM decisions d
            LEFT JOIN decision_entries de ON de.decision_id = d.id
            {where_clause}
            GROUP BY d.id
            ORDER BY d.created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()

    return [
        Decision(
            id=int(row["id"]),
            title=str(row["title"]),
            context=str(row["context"]),
            status=str(row["status"]),
            options=tuple(str(option) for option in json.loads(str(row["options_json"]))),
            final_choice=str(row["final_choice"]) if row["final_choice"] is not None else None,
            confidence=int(row["confidence"]) if row["confidence"] is not None else None,
            review_date=str(row["review_date"]) if row["review_date"] is not None else None,
            outcome=str(row["outcome"]) if row["outcome"] is not None else None,
            created_at=str(row["created_at"]),
            entry_ids=entry_ids_from_row(row["entry_ids"]),
        )
        for row in rows
    ]


def get_decision(db_path: Path, decision_id: int) -> Decision | None:
    with connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                d.id,
                d.title,
                d.context,
                d.status,
                d.options_json,
                d.final_choice,
                d.confidence,
                d.review_date,
                d.outcome,
                d.created_at,
                COALESCE(group_concat(de.entry_id, ','), '') AS entry_ids
            FROM decisions d
            LEFT JOIN decision_entries de ON de.decision_id = d.id
            WHERE d.id = ?
            GROUP BY d.id
            """,
            (decision_id,),
        ).fetchone()

    if row is None:
        return None

    return Decision(
        id=int(row["id"]),
        title=str(row["title"]),
        context=str(row["context"]),
        status=str(row["status"]),
        options=tuple(str(option) for option in json.loads(str(row["options_json"]))),
        final_choice=str(row["final_choice"]) if row["final_choice"] is not None else None,
        confidence=int(row["confidence"]) if row["confidence"] is not None else None,
        review_date=str(row["review_date"]) if row["review_date"] is not None else None,
        outcome=str(row["outcome"]) if row["outcome"] is not None else None,
        created_at=str(row["created_at"]),
        entry_ids=entry_ids_from_row(row["entry_ids"]),
    )


def list_entry_decisions(db_path: Path, *, entry_id: int) -> list[Decision]:
    with connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                d.id,
                d.title,
                d.context,
                d.status,
                d.options_json,
                d.final_choice,
                d.confidence,
                d.review_date,
                d.outcome,
                d.created_at,
                COALESCE(group_concat(de_all.entry_id, ','), '') AS entry_ids
            FROM decision_entries de_match
            JOIN decisions d ON d.id = de_match.decision_id
            LEFT JOIN decision_entries de_all ON de_all.decision_id = d.id
            WHERE de_match.entry_id = ?
            GROUP BY d.id
            ORDER BY d.created_at DESC
            """,
            (entry_id,),
        ).fetchall()

    return [
        Decision(
            id=int(row["id"]),
            title=str(row["title"]),
            context=str(row["context"]),
            status=str(row["status"]),
            options=tuple(str(option) for option in json.loads(str(row["options_json"]))),
            final_choice=str(row["final_choice"]) if row["final_choice"] is not None else None,
            confidence=int(row["confidence"]) if row["confidence"] is not None else None,
            review_date=str(row["review_date"]) if row["review_date"] is not None else None,
            outcome=str(row["outcome"]) if row["outcome"] is not None else None,
            created_at=str(row["created_at"]),
            entry_ids=entry_ids_from_row(row["entry_ids"]),
        )
        for row in rows
    ]


def list_entries(db_path: Path, *, limit: int = 20) -> list[Entry]:
    with connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                e.id,
                e.title,
                e.raw_text,
                e.summary,
                e.type,
                e.source,
                e.created_at,
                COALESCE(group_concat(t.name, ','), '') AS tags
            FROM entries e
            LEFT JOIN entry_tags et ON et.entry_id = e.id
            LEFT JOIN tags t ON t.id = et.tag_id
            GROUP BY e.id
            ORDER BY e.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        Entry(
            id=int(row["id"]),
            title=str(row["title"]),
            raw_text=str(row["raw_text"]),
            summary=str(row["summary"]),
            type=str(row["type"]),
            source=str(row["source"]),
            created_at=str(row["created_at"]),
            tags=tuple(tag for tag in str(row["tags"]).split(",") if tag),
        )
        for row in rows
    ]


def get_entry(db_path: Path, entry_id: int) -> Entry | None:
    with connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                e.id,
                e.title,
                e.raw_text,
                e.summary,
                e.type,
                e.source,
                e.created_at,
                COALESCE(group_concat(t.name, ','), '') AS tags
            FROM entries e
            LEFT JOIN entry_tags et ON et.entry_id = e.id
            LEFT JOIN tags t ON t.id = et.tag_id
            WHERE e.id = ?
            GROUP BY e.id
            """,
            (entry_id,),
        ).fetchone()

    if row is None:
        return None

    return Entry(
        id=int(row["id"]),
        title=str(row["title"]),
        raw_text=str(row["raw_text"]),
        summary=str(row["summary"]),
        type=str(row["type"]),
        source=str(row["source"]),
        created_at=str(row["created_at"]),
        tags=tuple(tag for tag in str(row["tags"]).split(",") if tag),
    )


def list_decision_entries(db_path: Path, *, decision_id: int) -> list[Entry]:
    with connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                e.id,
                e.title,
                e.raw_text,
                e.summary,
                e.type,
                e.source,
                e.created_at,
                COALESCE(group_concat(t.name, ','), '') AS tags
            FROM decision_entries de
            JOIN entries e ON e.id = de.entry_id
            LEFT JOIN entry_tags et ON et.entry_id = e.id
            LEFT JOIN tags t ON t.id = et.tag_id
            WHERE de.decision_id = ?
            GROUP BY e.id, de.created_at
            ORDER BY de.created_at ASC
            """,
            (decision_id,),
        ).fetchall()

    return [
        Entry(
            id=int(row["id"]),
            title=str(row["title"]),
            raw_text=str(row["raw_text"]),
            summary=str(row["summary"]),
            type=str(row["type"]),
            source=str(row["source"]),
            created_at=str(row["created_at"]),
            tags=tuple(tag for tag in str(row["tags"]).split(",") if tag),
        )
        for row in rows
    ]


def list_entries_between(
    db_path: Path,
    *,
    period_start: str,
    period_end: str,
    limit: int = 100,
) -> list[Entry]:
    with connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                e.id,
                e.title,
                e.raw_text,
                e.summary,
                e.type,
                e.source,
                e.created_at,
                COALESCE(group_concat(t.name, ','), '') AS tags
            FROM entries e
            LEFT JOIN entry_tags et ON et.entry_id = e.id
            LEFT JOIN tags t ON t.id = et.tag_id
            WHERE substr(e.created_at, 1, 10) BETWEEN ? AND ?
            GROUP BY e.id
            ORDER BY e.created_at DESC
            LIMIT ?
            """,
            (period_start, period_end, limit),
        ).fetchall()

    return [
        Entry(
            id=int(row["id"]),
            title=str(row["title"]),
            raw_text=str(row["raw_text"]),
            summary=str(row["summary"]),
            type=str(row["type"]),
            source=str(row["source"]),
            created_at=str(row["created_at"]),
            tags=tuple(tag for tag in str(row["tags"]).split(",") if tag),
        )
        for row in rows
    ]


def fts_query_from_text(query: str) -> str:
    tokens = SEARCH_TOKEN_RE.findall(query.lower())
    return " OR ".join(f'"{token}"' for token in tokens)


def tag_terms_from_text(query: str) -> tuple[str, ...]:
    tokens = SEARCH_TOKEN_RE.findall(query.lower())
    terms = set(tokens)
    if len(tokens) > 1:
        terms.add("-".join(tokens))
        terms.add("_".join(tokens))
    full_term = re.sub(r"[^a-z0-9_-]+", "-", query.lower()).strip("-_")
    if full_term:
        terms.add(full_term)
    return tuple(sorted(term for term in terms if term))


def search_entries(db_path: Path, *, query: str, limit: int = 10) -> list[Entry]:
    fts_query = fts_query_from_text(query)
    if not fts_query:
        return []

    with connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                e.id,
                e.title,
                e.raw_text,
                e.summary,
                e.type,
                e.source,
                e.created_at,
                COALESCE(group_concat(t.name, ','), '') AS tags
            FROM entries_fts f
            JOIN entries e ON e.id = f.rowid
            LEFT JOIN entry_tags et ON et.entry_id = e.id
            LEFT JOIN tags t ON t.id = et.tag_id
            WHERE entries_fts MATCH ?
            GROUP BY e.id
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, limit),
        ).fetchall()

    return [
        Entry(
            id=int(row["id"]),
            title=str(row["title"]),
            raw_text=str(row["raw_text"]),
            summary=str(row["summary"]),
            type=str(row["type"]),
            source=str(row["source"]),
            created_at=str(row["created_at"]),
            tags=tuple(tag for tag in str(row["tags"]).split(",") if tag),
        )
        for row in rows
    ]


def search_entries_by_tags(db_path: Path, *, query: str, limit: int = 10) -> list[Entry]:
    terms = tag_terms_from_text(query)
    if limit <= 0 or not terms:
        return []

    placeholders = ",".join("?" for _ in terms)
    with connection(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT
                e.id,
                e.title,
                e.raw_text,
                e.summary,
                e.type,
                e.source,
                e.created_at,
                COALESCE(group_concat(t_all.name, ','), '') AS tags,
                COUNT(DISTINCT t_match.name) AS matched_tags
            FROM entries e
            JOIN entry_tags et_match ON et_match.entry_id = e.id
            JOIN tags t_match ON t_match.id = et_match.tag_id
            LEFT JOIN entry_tags et_all ON et_all.entry_id = e.id
            LEFT JOIN tags t_all ON t_all.id = et_all.tag_id
            WHERE t_match.name IN ({placeholders})
            GROUP BY e.id
            ORDER BY matched_tags DESC, e.created_at DESC
            LIMIT ?
            """,
            (*terms, limit),
        ).fetchall()

    return [entry_from_row(row) for row in rows]
