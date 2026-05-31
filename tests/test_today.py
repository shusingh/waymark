from __future__ import annotations

from datetime import date

import pytest

from waymark.storage import Decision, Entry
from waymark.today import build_today_brief, format_today_brief, parse_today_date


def test_build_today_brief_collects_daily_actions() -> None:
    today_entry = Entry(
        id=1,
        title="Shipped release",
        raw_text="Released Waymark.",
        summary="Released the first package.",
        type="project",
        source="manual",
        created_at="2026-05-31T10:00:00+00:00",
        tags=("release",),
    )
    older_entry = Entry(
        id=2,
        title="Older note",
        raw_text="Earlier.",
        summary="Earlier note.",
        type="daily",
        source="manual",
        created_at="2026-05-28T10:00:00+00:00",
        tags=(),
    )
    due_decision = Decision(
        id=1,
        title="Review package channel",
        context="Confirm release path.",
        status="open",
        options=(),
        final_choice=None,
        confidence=None,
        review_date="2026-05-30",
        outcome=None,
        created_at="2026-05-20T10:00:00+00:00",
        entry_ids=(),
    )

    brief = build_today_brief(
        entries=[today_entry, older_entry],
        entries_today=[today_entry],
        decisions=[due_decision],
        reflections=[],
        today=date(2026, 5, 31),
    )

    assert brief.entries_today == (today_entry,)
    assert brief.reflection_queue.items[0].period_type == "today"
    assert brief.decision_queue.due_for_review == (due_decision,)
    assert "waymark reflect --period today --save" in brief.suggested_commands
    assert "waymark decision review" in brief.suggested_commands


def test_format_today_brief_shows_empty_day_capture_prompt() -> None:
    brief = build_today_brief(
        entries=[],
        entries_today=[],
        decisions=[],
        reflections=[],
        today=date(2026, 5, 31),
    )

    text = format_today_brief(brief)

    assert "Today - 2026-05-31" in text
    assert "Captures Today" in text
    assert "- none yet" in text
    assert "waymark capture --type daily" in text


def test_parse_today_date_rejects_non_iso_dates() -> None:
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        parse_today_date("05/31/2026")
