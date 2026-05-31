from __future__ import annotations

from waymark.retrieval import compose_source_answer, rank_retrieved_entries
from waymark.storage import Entry, ScoredEntry


def test_compose_source_answer_cites_memory_ids() -> None:
    entries = (
        Entry(
            id=7,
            title="Private memory",
            raw_text="Waymark should keep retrieval grounded.",
            summary="Waymark answers should cite saved memories.",
            type="principle",
            source="manual",
            created_at="2026-05-30T00:00:00+00:00",
            tags=("retrieval",),
        ),
    )

    answer = compose_source_answer("how should answers work?", entries)

    assert 'For "how should answers work?"' in answer
    assert "Waymark answers should cite saved memories. [#7]" in answer


def test_compose_source_answer_reports_extra_sources() -> None:
    entries = tuple(
        Entry(
            id=index,
            title=f"Memory {index}",
            raw_text=f"Raw {index}",
            summary=f"Summary {index}.",
            type="daily",
            source="manual",
            created_at="2026-05-30T00:00:00+00:00",
            tags=(),
        )
        for index in range(1, 5)
    )

    answer = compose_source_answer("what happened?", entries, max_sources=2)

    assert "Summary 1. [#1]" in answer
    assert "Summary 2. [#2]" in answer
    assert "2 more source(s) are listed below." in answer
    assert "Summary 3." not in answer


def test_rank_retrieved_entries_combines_keyword_and_semantic_scores() -> None:
    first = Entry(
        id=1,
        title="Exact and semantic",
        raw_text="Raw 1",
        summary="Summary 1.",
        type="project",
        source="manual",
        created_at="2026-05-30T00:00:02+00:00",
        tags=(),
    )
    second = Entry(
        id=2,
        title="Semantic only",
        raw_text="Raw 2",
        summary="Summary 2.",
        type="project",
        source="manual",
        created_at="2026-05-30T00:00:01+00:00",
        tags=(),
    )

    ranked = rank_retrieved_entries(
        keyword_entries=(first,),
        tag_entries=(),
        semantic_entries=(
            ScoredEntry(entry=second, score=0.95),
            ScoredEntry(entry=first, score=0.5),
        ),
        limit=2,
    )

    assert [result.entry.id for result in ranked] == [1, 2]
    assert ranked[0].reasons == ("keyword", "semantic")
    assert ranked[0].score == 1.5


def test_rank_retrieved_entries_includes_tag_reason() -> None:
    entry = Entry(
        id=3,
        title="Tagged only",
        raw_text="Raw 3",
        summary="Summary 3.",
        type="project",
        source="manual",
        created_at="2026-05-30T00:00:03+00:00",
        tags=("local-first",),
    )

    ranked = rank_retrieved_entries(
        keyword_entries=(),
        tag_entries=(entry,),
        semantic_entries=(),
        limit=1,
    )

    assert ranked[0].entry.id == 3
    assert ranked[0].reasons == ("tag",)
