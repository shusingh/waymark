"""Markdown export helpers for explicit user-selected outputs."""

from __future__ import annotations

from pathlib import Path

from waymark.reflection import ReflectionTrend, format_reflection_trend
from waymark.storage import Entry, Reflection, get_source, source_id_from_entry, source_label


def entry_source_text(db_path: Path, entry: Entry) -> str:
    source_id = source_id_from_entry(entry)
    if source_id is None:
        return entry.source
    return source_label(get_source(db_path, source_id))


def format_entry_markdown(db_path: Path, entry: Entry) -> str:
    tags = ", ".join(entry.tags) if entry.tags else "none"
    source = entry_source_text(db_path, entry)
    return "\n".join(
        [
            f"# {entry.title}",
            "",
            f"- ID: {entry.id}",
            f"- Created: {entry.created_at}",
            f"- Type: {entry.type}",
            f"- Tags: {tags}",
            f"- Source: {source}",
            "",
            "## Summary",
            "",
            entry.summary,
            "",
            "## Memory",
            "",
            entry.raw_text.strip(),
            "",
        ]
    )


def format_timeline_markdown(db_path: Path, entries: list[Entry]) -> str:
    lines = [
        "# Waymark Timeline",
        "",
        f"Exported entries: {len(entries)}",
        "",
    ]
    for entry in entries:
        tags = ", ".join(entry.tags) if entry.tags else "none"
        source = entry_source_text(db_path, entry)
        lines.extend(
            [
                f"## #{entry.id} {entry.title}",
                "",
                f"- Created: {entry.created_at}",
                f"- Type: {entry.type}",
                f"- Tags: {tags}",
                f"- Source: {source}",
                "",
                entry.summary,
                "",
                entry.raw_text.strip(),
                "",
            ]
        )
    return "\n".join(lines)


def format_reflection_markdown(reflection: Reflection) -> str:
    lines = [
        f"# Saved Reflection #{reflection.id}",
        "",
        f"- Period: {reflection.period_type}",
        f"- Window: {reflection.period_start} to {reflection.period_end}",
        f"- Created: {reflection.created_at}",
        "",
        "## Summary",
        "",
        reflection.summary,
        "",
        "## Wins",
        "",
        *markdown_bullets(reflection.wins),
        "",
        "## Patterns",
        "",
        *markdown_bullets(reflection.patterns),
        "",
        "## Suggestions",
        "",
        *markdown_bullets(reflection.suggestions),
        "",
    ]
    return "\n".join(lines)


def format_reflection_trend_markdown(trend: ReflectionTrend) -> str:
    return "\n".join(
        [
            "# Waymark Reflection Trends",
            "",
            format_reflection_trend(trend),
            "",
        ]
    )


def markdown_bullets(items: tuple[str, ...]) -> list[str]:
    if not items:
        return ["- None yet"]
    return [f"- {item}" for item in items]


def write_markdown_export(path: Path, content: str, *, force: bool = False) -> Path:
    resolved_path = path.expanduser().resolve()
    if resolved_path.exists() and resolved_path.is_dir():
        raise ValueError("Markdown export output must be a file path, not a folder.")
    if resolved_path.exists() and not force:
        raise FileExistsError(f"Export file already exists: {resolved_path}")

    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(content, encoding="utf-8")
    return resolved_path
