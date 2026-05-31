"""Memory-card drafting helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryDraft:
    raw_text: str
    memory_type: str
    title: str
    summary: str
    tags: tuple[str, ...]


def fallback_title(raw_text: str) -> str:
    first_line = raw_text.strip().splitlines()[0].strip()
    if len(first_line) <= 72:
        return first_line
    return f"{first_line[:69].rstrip()}..."


def fallback_summary(raw_text: str) -> str:
    normalized = " ".join(raw_text.strip().split())
    if len(normalized) <= 220:
        return normalized
    return f"{normalized[:217].rstrip()}..."


def parse_tags(raw_tags: str) -> tuple[str, ...]:
    tags = {tag.strip().lower() for tag in raw_tags.replace("#", "").split(",")}
    return tuple(sorted(tag for tag in tags if tag))


def draft_memory(raw_text: str, *, memory_type: str, raw_tags: str = "") -> MemoryDraft:
    clean_text = raw_text.strip()
    clean_type = memory_type.strip().lower() or "daily"
    return MemoryDraft(
        raw_text=clean_text,
        memory_type=clean_type,
        title=fallback_title(clean_text),
        summary=fallback_summary(clean_text),
        tags=parse_tags(raw_tags),
    )

