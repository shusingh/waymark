from __future__ import annotations

from datetime import date

from waymark.journey import (
    build_decision_review_queue,
    build_journey_map,
    format_decision_review_queue,
    format_journey_map,
)
from waymark.storage import Decision, Entry, Reflection


def test_build_journey_map_summarizes_memory_health() -> None:
    entries = (
        Entry(
            id=1,
            title="Today",
            raw_text="Captured today.",
            summary="A current memory.",
            type="project",
            source="manual",
            created_at="2026-05-30T10:00:00+00:00",
            tags=("local-first", "waymark"),
        ),
        Entry(
            id=2,
            title="Older",
            raw_text="Captured earlier.",
            summary="An older memory.",
            type="daily",
            source="manual",
            created_at="2026-05-01T10:00:00+00:00",
            tags=("waymark",),
        ),
    )
    decisions = (
        Decision(
            id=1,
            title="Review this",
            context="Needs review.",
            status="open",
            options=("A", "B"),
            final_choice=None,
            confidence=None,
            review_date="2026-05-29",
            outcome=None,
            created_at="2026-05-01T00:00:00+00:00",
            entry_ids=(),
        ),
        Decision(
            id=2,
            title="Chosen",
            context="Needs outcome.",
            status="decided",
            options=("A",),
            final_choice="A",
            confidence=4,
            review_date=None,
            outcome=None,
            created_at="2026-05-02T00:00:00+00:00",
            entry_ids=(1,),
        ),
    )
    reflections = (
        Reflection(
            id=1,
            period_type="week",
            period_start="2026-05-24",
            period_end="2026-05-30",
            summary="A saved reflection.",
            wins=(),
            patterns=(),
            suggestions=(),
            created_at="2026-05-30T12:00:00+00:00",
        ),
    )

    journey_map = build_journey_map(
        entries=entries,
        decisions=decisions,
        reflections=reflections,
        today=date(2026, 5, 30),
    )

    assert journey_map.total_memories == 2
    assert journey_map.memories_last_7_days == 1
    assert journey_map.memories_last_30_days == 2
    assert journey_map.top_tags[0].name == "waymark"
    assert journey_map.thin_memory_areas == ("work", "career", "health", "decision", "learning")
    assert journey_map.capture_prompts[0] == "Capture one work signal, tradeoff, or conversation."
    assert journey_map.open_decisions == 1
    assert journey_map.decisions_due_for_review == 1
    assert journey_map.decisions_waiting_for_outcome == 1
    assert journey_map.open_decision_refs == ("#1 Review this",)
    assert journey_map.review_decision_refs == ("#1 Review this",)
    assert journey_map.outcome_decision_refs == ("#2 Chosen",)
    assert journey_map.latest_reflection == "week 2026-05-24 to 2026-05-30"
    assert journey_map.suggested_reflection_command == "waymark reflect --period today --save"
    assert journey_map.reflection_commands == ("waymark reflect --period today --save",)


def test_format_journey_map_includes_next_signals() -> None:
    journey_map = build_journey_map(
        entries=(),
        decisions=(),
        reflections=(),
        today=date(2026, 5, 30),
    )

    text = format_journey_map(journey_map)

    assert "Memory Health" in text
    assert "Total memories: 0" in text
    assert "Suggested command: none yet" in text
    assert "Thin areas: daily, project, work, career, health" in text
    assert "Start with one capture" in text
    assert "No saved reflections yet" in text


def test_reflection_suggestions_expand_with_capture_rhythm() -> None:
    entries = tuple(
        Entry(
            id=index,
            title=f"Memory {index}",
            raw_text=f"Raw {index}",
            summary=f"Summary {index}.",
            type="daily",
            source="manual",
            created_at=f"2026-05-{30 - index:02d}T10:00:00+00:00",
            tags=(),
        )
        for index in range(0, 6)
    )

    journey_map = build_journey_map(
        entries=entries,
        decisions=(),
        reflections=(),
        today=date(2026, 5, 30),
    )

    assert journey_map.reflection_commands == (
        "waymark reflect --period today --save",
        "waymark reflect --period week --save",
        "waymark reflect --period month --save",
    )


def test_decision_review_queue_formats_due_and_outcome_items() -> None:
    due = Decision(
        id=1,
        title="Due decision",
        context="Needs review.",
        status="open",
        options=(),
        final_choice=None,
        confidence=3,
        review_date="2026-05-29",
        outcome=None,
        created_at="2026-05-01T00:00:00+00:00",
        entry_ids=(),
    )
    waiting = Decision(
        id=2,
        title="Waiting decision",
        context="Needs outcome.",
        status="decided",
        options=("A",),
        final_choice="A",
        confidence=4,
        review_date=None,
        outcome=None,
        created_at="2026-05-02T00:00:00+00:00",
        entry_ids=(),
    )

    queue = build_decision_review_queue((waiting, due), today=date(2026, 5, 30))
    text = format_decision_review_queue(queue)

    assert queue.due_for_review == (due,)
    assert queue.waiting_for_outcome == (waiting,)
    assert "#1 Due decision" in text
    assert "#2 Waiting decision" in text
