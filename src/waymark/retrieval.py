"""Source-grounded retrieval presentation helpers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from waymark.storage import Entry, ScoredEntry


@dataclass(frozen=True)
class RankedEntry:
    entry: Entry
    score: float
    reasons: tuple[str, ...]


@dataclass
class MutableRank:
    entry: Entry
    score: float
    reasons: list[str]


def compose_source_answer(query: str, entries: Sequence[Entry], *, max_sources: int = 3) -> str:
    if not entries:
        return "No saved sources were found for this question."

    source_lines = [
        f"- {entry.summary} [#{entry.id}]" for entry in entries[:max_sources]
    ]
    extra_count = len(entries) - max_sources
    if extra_count > 0:
        source_lines.append(f"- {extra_count} more source(s) are listed below.")

    return "\n".join(
        [
            f'For "{query}", saved memories point to:',
            "",
            *source_lines,
        ]
    )


def rank_retrieved_entries(
    *,
    keyword_entries: Sequence[Entry],
    tag_entries: Sequence[Entry],
    semantic_entries: Sequence[ScoredEntry],
    limit: int,
) -> list[RankedEntry]:
    if limit <= 0:
        return []

    ranks: dict[int, MutableRank] = {}

    for index, entry in enumerate(keyword_entries, start=1):
        add_rank(
            ranks,
            entry=entry,
            score=1.0 / index,
            reason="keyword",
        )

    for index, entry in enumerate(tag_entries, start=1):
        add_rank(
            ranks,
            entry=entry,
            score=0.75 / index,
            reason="tag",
        )

    for scored in semantic_entries:
        add_rank(
            ranks,
            entry=scored.entry,
            score=scored.score,
            reason="semantic",
        )

    ranked_entries = [
        RankedEntry(
            entry=rank.entry,
            score=rank.score,
            reasons=tuple(rank.reasons),
        )
        for rank in ranks.values()
    ]
    ranked_entries.sort(key=lambda rank: (rank.score, rank.entry.created_at), reverse=True)
    return ranked_entries[:limit]


def add_rank(
    ranks: dict[int, MutableRank],
    *,
    entry: Entry,
    score: float,
    reason: str,
) -> None:
    current = ranks.get(entry.id)
    if current is None:
        ranks[entry.id] = MutableRank(entry=entry, score=score, reasons=[reason])
        return

    current.score += score
    if reason not in current.reasons:
        current.reasons.append(reason)
