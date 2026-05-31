from __future__ import annotations

from pathlib import Path

from waymark.memory import draft_memory, fallback_summary, fallback_title, parse_tags
from waymark.storage import (
    add_decision,
    add_entry,
    add_reflection,
    add_source,
    cosine_similarity,
    count_entries_missing_embeddings,
    count_entry_embeddings,
    finalize_decision,
    fts_query_from_text,
    get_decision,
    get_entry,
    get_entry_embedding,
    get_reflection,
    get_source,
    get_source_by_path,
    init_database,
    link_decision_entry,
    list_decision_entries,
    list_decisions,
    list_entries,
    list_entries_between,
    list_entries_missing_embeddings,
    list_entry_decisions,
    list_reflections,
    list_sources,
    record_decision_outcome,
    search_entries,
    search_entries_by_embedding,
    search_entries_by_tags,
    source_id_from_entry,
    source_label,
    tag_terms_from_text,
    unlink_decision_entry,
    update_entry,
    upsert_entry_embedding,
)


def test_add_and_list_entry(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    init_database(db_path)

    entry_id = add_entry(
        db_path,
        raw_text="I started building Waymark today.",
        memory_type="project",
        title="Started building Waymark",
        summary="A project memory about starting Waymark.",
        tags=("project", "local-first"),
    )

    entries = list_entries(db_path)

    assert entry_id == 1
    assert len(entries) == 1
    assert entries[0].title == "Started building Waymark"
    assert entries[0].tags == ("local-first", "project")

    entry = get_entry(db_path, entry_id)
    assert entry is not None
    assert entry.title == "Started building Waymark"
    assert entry.tags == ("local-first", "project")


def test_update_entry_replaces_fields_and_tags(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    init_database(db_path)
    entry_id = add_entry(
        db_path,
        raw_text="Original memory text.",
        memory_type="daily",
        title="Original title",
        summary="Original summary",
        tags=("old",),
    )

    updated = update_entry(
        db_path,
        entry_id=entry_id,
        raw_text="Updated memory text.",
        memory_type="project",
        title="Updated title",
        summary="Updated summary",
        tags=("new", "project"),
    )

    entry = get_entry(db_path, entry_id)
    results = search_entries(db_path, query="Updated", limit=5)
    assert updated
    assert entry is not None
    assert entry.raw_text == "Updated memory text."
    assert entry.type == "project"
    assert entry.title == "Updated title"
    assert entry.summary == "Updated summary"
    assert entry.tags == ("new", "project")
    assert results[0].id == entry_id


def test_update_entry_can_clear_tags_and_reports_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    init_database(db_path)
    entry_id = add_entry(
        db_path,
        raw_text="Tagged memory.",
        memory_type="daily",
        title="Tagged memory",
        summary="Tagged memory.",
        tags=("remove",),
    )

    assert update_entry(db_path, entry_id=entry_id, tags=())
    entry = get_entry(db_path, entry_id)
    assert entry is not None
    assert entry.tags == ()
    assert not update_entry(db_path, entry_id=999, title="Missing")


def test_entry_embeddings_can_be_upserted_and_listed(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    init_database(db_path)
    entry_id = add_entry(
        db_path,
        raw_text="A memory that needs an embedding.",
        memory_type="project",
        title="Embedding memory",
        summary="A memory that needs an embedding.",
    )

    missing = list_entries_missing_embeddings(db_path, model="nomic-embed-text")
    assert count_entries_missing_embeddings(db_path, model="nomic-embed-text") == 1
    assert missing[0].id == entry_id

    assert upsert_entry_embedding(
        db_path,
        entry_id=entry_id,
        model="nomic-embed-text",
        vector=(0.1, 0.2, 0.3),
    )
    assert count_entry_embeddings(db_path, model="nomic-embed-text") == 1
    assert count_entries_missing_embeddings(db_path, model="nomic-embed-text") == 0
    assert not list_entries_missing_embeddings(db_path, model="nomic-embed-text")

    embedding = get_entry_embedding(
        db_path,
        entry_id=entry_id,
        model="nomic-embed-text",
    )
    assert embedding is not None
    assert embedding.vector == (0.1, 0.2, 0.3)
    assert embedding.dimensions == 3


def test_embedding_search_returns_entries_by_cosine_similarity(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    init_database(db_path)
    project_id = add_entry(
        db_path,
        raw_text="We chose explicit local indexing for Waymark.",
        memory_type="project",
        title="Local indexing",
        summary="Waymark should only build embeddings when asked.",
    )
    unrelated_id = add_entry(
        db_path,
        raw_text="Dinner was pasta with lemon.",
        memory_type="daily",
        title="Dinner note",
        summary="A small personal dinner note.",
    )
    assert upsert_entry_embedding(
        db_path,
        entry_id=project_id,
        model="nomic-embed-text",
        vector=(1.0, 0.0),
    )
    assert upsert_entry_embedding(
        db_path,
        entry_id=unrelated_id,
        model="nomic-embed-text",
        vector=(0.0, 1.0),
    )

    results = search_entries_by_embedding(
        db_path,
        model="nomic-embed-text",
        query_vector=(0.9, 0.1),
        limit=2,
    )

    assert cosine_similarity((1.0, 0.0), (1.0, 0.0)) == 1.0
    assert [result.entry.title for result in results] == ["Local indexing", "Dinner note"]
    assert results[0].score > results[1].score


def test_list_entries_between_uses_created_date(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    init_database(db_path)
    add_entry(
        db_path,
        raw_text="A memory for today.",
        memory_type="daily",
        title="Today memory",
        summary="A memory for today.",
    )

    entries = list_entries_between(
        db_path,
        period_start="2000-01-01",
        period_end="2999-12-31",
    )

    assert len(entries) == 1
    assert entries[0].title == "Today memory"


def test_keyword_search_returns_sources(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    init_database(db_path)
    add_entry(
        db_path,
        raw_text="Waymark should cite memories when answering questions.",
        memory_type="principle",
        title="Grounded answers",
        summary="Answers should cite saved source memories.",
        tags=("retrieval",),
    )

    results = search_entries(db_path, query="cite", limit=5)

    assert len(results) == 1
    assert results[0].title == "Grounded answers"


def test_keyword_search_accepts_natural_questions_and_hyphens(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    init_database(db_path)
    add_entry(
        db_path,
        raw_text="Waymark should stay local-first and memory-first.",
        memory_type="principle",
        title="Local-first principle",
        summary="Keep Waymark local-first before adding integrations.",
        tags=("local-first",),
    )

    assert len(search_entries(db_path, query="what is local-first?", limit=5)) == 1
    assert fts_query_from_text("what is local-first?") == (
        '"what" OR "is" OR "local" OR "first"'
    )


def test_tag_search_accepts_natural_questions_and_hyphens(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    init_database(db_path)
    add_entry(
        db_path,
        raw_text="This body deliberately omits the matching phrase.",
        memory_type="principle",
        title="Tagged principle",
        summary="A memory found by tag.",
        tags=("local-first",),
    )

    results = search_entries_by_tags(db_path, query="local first", limit=5)

    assert tag_terms_from_text("local first") == ("first", "local", "local-first", "local_first")
    assert len(results) == 1
    assert results[0].title == "Tagged principle"


def test_add_and_list_decision(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    init_database(db_path)

    decision_id = add_decision(
        db_path,
        title="Build CLI first?",
        context="The memory engine matters more than desktop polish.",
        options=("CLI first", "Desktop first"),
        confidence=4,
        review_date="2026-06-12",
    )

    decisions = list_decisions(db_path, status="open")

    assert decision_id == 1
    assert len(decisions) == 1
    assert decisions[0].title == "Build CLI first?"
    assert decisions[0].options == ("CLI first", "Desktop first")
    assert decisions[0].confidence == 4
    assert decisions[0].entry_ids == ()

    decision = get_decision(db_path, decision_id)
    assert decision is not None
    assert decision.title == "Build CLI first?"


def test_link_decision_entry(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    init_database(db_path)
    entry_id = add_entry(
        db_path,
        raw_text="This memory should inform the decision.",
        memory_type="project",
        title="Decision context memory",
        summary="This memory should inform the decision.",
    )
    decision_id = add_decision(
        db_path,
        title="Use linked memory?",
        context="A decision should carry its source trail.",
    )

    assert link_decision_entry(db_path, decision_id=decision_id, entry_id=entry_id)
    assert not link_decision_entry(db_path, decision_id=decision_id, entry_id=999)

    decision = get_decision(db_path, decision_id)
    linked_entries = list_decision_entries(db_path, decision_id=decision_id)
    assert decision is not None
    assert decision.entry_ids == (entry_id,)
    assert linked_entries[0].title == "Decision context memory"
    entry_decisions = list_entry_decisions(db_path, entry_id=entry_id)
    assert entry_decisions[0].title == "Use linked memory?"

    assert unlink_decision_entry(db_path, decision_id=decision_id, entry_id=entry_id)
    assert not unlink_decision_entry(db_path, decision_id=decision_id, entry_id=entry_id)
    unlinked_decision = get_decision(db_path, decision_id)
    assert unlinked_decision is not None
    assert unlinked_decision.entry_ids == ()


def test_finalize_and_record_decision_outcome(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    init_database(db_path)
    decision_id = add_decision(
        db_path,
        title="Build CLI first?",
        context="The memory engine matters more than desktop polish.",
        options=("CLI first", "Desktop first"),
    )

    assert finalize_decision(
        db_path,
        decision_id=decision_id,
        final_choice="CLI first",
        confidence=5,
    )
    decided = list_decisions(db_path)[0]
    assert decided.status == "decided"
    assert decided.final_choice == "CLI first"
    assert decided.confidence == 5

    assert record_decision_outcome(
        db_path,
        decision_id=decision_id,
        outcome="The CLI foundation made later UI work easier.",
    )
    reviewed = list_decisions(db_path)[0]
    assert reviewed.status == "reviewed"
    assert reviewed.outcome == "The CLI foundation made later UI work easier."


def test_add_and_list_reflection(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    init_database(db_path)

    reflection_id = add_reflection(
        db_path,
        period_type="week",
        period_start="2026-05-24",
        period_end="2026-05-30",
        summary="You captured two meaningful memories.",
        wins=("Built capture",),
        patterns=("Project work dominated.",),
        suggestions=("Record one decision.",),
    )

    reflections = list_reflections(db_path)

    assert reflection_id == 1
    assert len(reflections) == 1
    assert reflections[0].summary == "You captured two meaningful memories."
    assert reflections[0].wins == ("Built capture",)

    reflection = get_reflection(db_path, reflection_id)
    assert reflection is not None
    assert reflection.summary == "You captured two meaningful memories."
    assert reflection.suggestions == ("Record one decision.",)


def test_add_source_is_listed(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    init_database(db_path)

    source_id = add_source(
        db_path,
        source_type="markdown",
        path="D:\\notes\\note.md",
        original_filename="note.md",
        metadata={"size_bytes": 42},
    )

    sources = list_sources(db_path)
    assert source_id == 1
    assert sources[0].type == "markdown"
    assert sources[0].metadata["size_bytes"] == 42

    source = get_source_by_path(
        db_path,
        source_type="markdown",
        path="D:\\notes\\note.md",
    )
    assert source is not None
    assert source.id == source_id


def test_source_label_for_imported_entry(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    init_database(db_path)
    source_id = add_source(
        db_path,
        source_type="markdown",
        path="D:\\notes\\note.md",
        original_filename="note.md",
    )
    entry_id = add_entry(
        db_path,
        raw_text="Imported note",
        memory_type="import",
        title="Imported note",
        summary="Imported note",
        source=f"source:{source_id}",
    )
    entry = list_entries(db_path)[0]
    source = get_source(db_path, source_id_from_entry(entry) or 0)

    assert entry_id == 1
    assert source_label(source) == "markdown: note.md"


def test_memory_draft_normalizes_fallback_fields() -> None:
    draft = draft_memory(
        "Waymark should keep manual capture useful before local AI.",
        memory_type=" Project ",
        raw_tags="#Terminal, local-first, terminal",
    )

    assert draft.memory_type == "project"
    assert draft.title == "Waymark should keep manual capture useful before local AI."
    assert draft.summary == "Waymark should keep manual capture useful before local AI."
    assert draft.tags == ("local-first", "terminal")


def test_fallback_title_and_summary_truncate_long_text() -> None:
    long_text = "a" * 260

    assert fallback_title(long_text) == f"{'a' * 69}..."
    assert fallback_summary(long_text) == f"{'a' * 217}..."
    assert parse_tags("project, #AI, project") == ("ai", "project")
