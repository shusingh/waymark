from __future__ import annotations

from datetime import date

from waymark.reflection import (
    build_reflection_comparison,
    build_reflection_queue,
    build_reflection_trend,
    first_reflection_queue_item,
    format_reflection_comparison,
    format_reflection_queue,
    format_reflection_trend,
    generate_reflection,
    reflection_window,
    saved_reflection_for_window,
)
from waymark.storage import Entry, Reflection


def make_entry(
    *,
    entry_id: int,
    title: str,
    memory_type: str,
    tags: tuple[str, ...] = (),
    created_at: str = "2026-05-30T00:00:00+00:00",
) -> Entry:
    return Entry(
        id=entry_id,
        title=title,
        raw_text=title,
        summary=title,
        type=memory_type,
        source="manual",
        created_at=created_at,
        tags=tags,
    )


def test_reflection_window_week_is_last_seven_days() -> None:
    assert reflection_window("week", today=date(2026, 5, 30)) == (
        "2026-05-24",
        "2026-05-30",
    )


def test_generate_reflection_summarizes_entries() -> None:
    draft = generate_reflection(
        [
            make_entry(entry_id=1, title="Built the capture loop", memory_type="project"),
            make_entry(
                entry_id=2,
                title="Tracked a product decision",
                memory_type="decision",
                tags=("product", "cli"),
            ),
        ],
        period_type="week",
        period_start="2026-05-24",
        period_end="2026-05-30",
    )

    assert draft.period_type == "week"
    assert "2 memories" in draft.summary
    assert draft.wins == ("#1 Built the capture loop", "#2 Tracked a product decision")
    assert any("project" in pattern for pattern in draft.patterns)


def test_generate_reflection_handles_empty_period() -> None:
    draft = generate_reflection(
        [],
        period_type="today",
        period_start="2026-05-30",
        period_end="2026-05-30",
    )

    assert "No saved memories" in draft.summary
    assert draft.patterns == ("This period is under-documented.",)


def test_reflection_queue_lists_unsaved_windows() -> None:
    queue = build_reflection_queue(
        entries=[
            make_entry(entry_id=1, title="Captured today", memory_type="daily"),
        ],
        reflections=[],
        today=date(2026, 5, 30),
    )

    assert [item.period_type for item in queue.items] == ["today", "week", "month"]
    assert first_reflection_queue_item(queue) == queue.items[0]
    assert queue.items[0].command == "waymark reflect --period today --save"
    assert "no saved today reflection yet" in queue.items[0].reason


def test_reflection_queue_skips_saved_current_window() -> None:
    saved_today = Reflection(
        id=1,
        period_type="today",
        period_start="2026-05-30",
        period_end="2026-05-30",
        summary="Saved today.",
        wins=(),
        patterns=(),
        suggestions=(),
        created_at="2026-05-30T12:00:00+00:00",
    )

    queue = build_reflection_queue(
        entries=[
            make_entry(entry_id=1, title="Captured today", memory_type="daily"),
        ],
        reflections=[saved_today],
        today=date(2026, 5, 30),
    )

    assert [item.period_type for item in queue.items] == ["week", "month"]
    assert (
        saved_reflection_for_window(
            [saved_today],
            period_type="today",
            period_start="2026-05-30",
            period_end="2026-05-30",
        )
        == saved_today
    )


def test_reflection_queue_shows_latest_saved_window_for_stale_period() -> None:
    saved_week = Reflection(
        id=7,
        period_type="week",
        period_start="2026-05-17",
        period_end="2026-05-23",
        summary="Saved previous week.",
        wins=(),
        patterns=(),
        suggestions=(),
        created_at="2026-05-23T12:00:00+00:00",
    )

    queue = build_reflection_queue(
        entries=[
            make_entry(entry_id=1, title="Captured today", memory_type="daily"),
        ],
        reflections=[saved_week],
        today=date(2026, 5, 30),
    )
    week_item = next(item for item in queue.items if item.period_type == "week")
    text = format_reflection_queue(queue)

    assert week_item.latest_saved_reflection_id == 7
    assert week_item.latest_saved_window == "#7 2026-05-17 to 2026-05-23"
    assert "Latest saved: #7 2026-05-17 to 2026-05-23" in text


def test_format_reflection_queue_reports_empty_queue() -> None:
    queue = build_reflection_queue(
        entries=[],
        reflections=[],
        today=date(2026, 5, 30),
    )

    assert format_reflection_queue(queue) == "No reflection windows need attention right now."


def test_reflection_comparison_shows_new_and_dropped_wins() -> None:
    saved = Reflection(
        id=3,
        period_type="week",
        period_start="2026-05-17",
        period_end="2026-05-23",
        summary="Saved previous week.",
        wins=("#1 Old win",),
        patterns=("Old pattern.",),
        suggestions=("Old suggestion.",),
        created_at="2026-05-23T12:00:00+00:00",
    )
    entries = [
        make_entry(entry_id=2, title="New win", memory_type="project"),
    ]

    comparison = build_reflection_comparison(
        entries=entries,
        reflections=[saved],
        period_type="week",
        period_start="2026-05-24",
        period_end="2026-05-30",
    )
    text = format_reflection_comparison(comparison)

    assert comparison.latest_saved_reflection_id == 3
    assert comparison.new_wins == ("#2 New win",)
    assert comparison.dropped_wins == ("#1 Old win",)
    assert "Latest saved: #3 2026-05-17 to 2026-05-23" in text
    assert "New source wins" in text


def test_reflection_trend_counts_repeated_patterns_and_suggestions() -> None:
    reflections = [
        Reflection(
            id=1,
            period_type="week",
            period_start="2026-05-17",
            period_end="2026-05-23",
            summary="Saved previous week.",
            wins=(),
            patterns=("Most active memory types: project (2).",),
            suggestions=("Review the top theme.",),
            created_at="2026-05-23T12:00:00+00:00",
        ),
        Reflection(
            id=2,
            period_type="week",
            period_start="2026-05-24",
            period_end="2026-05-30",
            summary="Saved current week.",
            wins=(),
            patterns=("Most active memory types: project (2).",),
            suggestions=("Review the top theme.",),
            created_at="2026-05-30T12:00:00+00:00",
        ),
    ]

    trend = build_reflection_trend(reflections, period_type="week")
    text = format_reflection_trend(trend)

    assert trend.period_type == "week"
    assert trend.total_reflections == 2
    assert trend.repeated_patterns[0].count == 2
    assert "Saved Reflection Trends (week)" in text
    assert "Most active memory types: project (2). (2)" in text


def test_reflection_trend_filters_by_memory_scope() -> None:
    reflections = [
        Reflection(
            id=1,
            period_type="week",
            period_start="2026-05-17",
            period_end="2026-05-23",
            summary="Saved health week.",
            wins=(),
            patterns=("Health pattern.",),
            suggestions=("Review health.",),
            created_at="2026-05-23T12:00:00+00:00",
        ),
        Reflection(
            id=2,
            period_type="week",
            period_start="2026-05-24",
            period_end="2026-05-30",
            summary="Saved project week.",
            wins=(),
            patterns=("Project pattern.",),
            suggestions=("Review project.",),
            created_at="2026-05-30T12:00:00+00:00",
        ),
    ]
    entries = [
        make_entry(
            entry_id=1,
            title="Health source",
            memory_type="health",
            tags=("body",),
            created_at="2026-05-18T00:00:00+00:00",
        ),
        make_entry(
            entry_id=2,
            title="Project source",
            memory_type="project",
            tags=("focus",),
            created_at="2026-05-25T00:00:00+00:00",
        ),
    ]

    trend = build_reflection_trend(
        reflections,
        period_type="week",
        entries=entries,
        tags=("Focus",),
        memory_types=("PROJECT",),
    )
    text = format_reflection_trend(trend)

    assert trend.total_reflections == 1
    assert trend.scope_description == "tags: focus; types: project"
    assert "Memory scope: tags: focus; types: project" in text
    assert "Saved project week." in text
    assert "Saved health week." not in text


def test_reflection_trend_reports_empty_period() -> None:
    trend = build_reflection_trend([], period_type="month")

    assert format_reflection_trend(trend) == "No saved month reflections yet."
