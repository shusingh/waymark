"""Daily loop summary for returning to Waymark."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from waymark.journey import (
    DecisionReviewQueue,
    build_decision_review_queue,
    format_decision_review_queue,
)
from waymark.reflection import ReflectionQueue, build_reflection_queue
from waymark.storage import Decision, Entry, Reflection

DAILY_CAPTURE_COMMAND = (
    'waymark capture --type daily "One detail from today that future-me should remember."'
)


@dataclass(frozen=True)
class TodayBrief:
    current_date: date
    entries_today: tuple[Entry, ...]
    reflection_queue: ReflectionQueue
    decision_queue: DecisionReviewQueue
    suggested_commands: tuple[str, ...]


def parse_today_date(value: str | None) -> date:
    if value is None:
        return datetime.now(UTC).date()
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("date must be in YYYY-MM-DD format") from error


def build_today_brief(
    *,
    entries: list[Entry],
    entries_today: list[Entry],
    decisions: list[Decision],
    reflections: list[Reflection],
    today: date | None = None,
) -> TodayBrief:
    current_date = today or datetime.now(UTC).date()
    reflection_queue = build_reflection_queue(
        entries=entries,
        reflections=reflections,
        today=current_date,
    )
    decision_queue = build_decision_review_queue(decisions, today=current_date)

    return TodayBrief(
        current_date=current_date,
        entries_today=tuple(entries_today),
        reflection_queue=reflection_queue,
        decision_queue=decision_queue,
        suggested_commands=suggest_today_commands(
            entries_today=entries_today,
            reflection_queue=reflection_queue,
            decision_queue=decision_queue,
        ),
    )


def suggest_today_commands(
    *,
    entries_today: list[Entry],
    reflection_queue: ReflectionQueue,
    decision_queue: DecisionReviewQueue,
) -> tuple[str, ...]:
    commands: list[str] = []
    if not entries_today:
        commands.append(DAILY_CAPTURE_COMMAND)
    commands.extend(item.command for item in reflection_queue.items[:2])
    if decision_queue.due_for_review or decision_queue.waiting_for_outcome:
        commands.append("waymark decision review")
    if not commands:
        commands.append(DAILY_CAPTURE_COMMAND)
    return tuple(dict.fromkeys(commands))


def format_today_brief(brief: TodayBrief) -> str:
    lines = [
        f"Today - {brief.current_date.isoformat()}",
        "",
        "Captures Today",
    ]
    if brief.entries_today:
        lines.extend(format_entry_line(entry) for entry in brief.entries_today[:5])
        if len(brief.entries_today) > 5:
            lines.append(f"- {len(brief.entries_today) - 5} more capture(s) today.")
    else:
        lines.append("- none yet")

    lines.extend(
        [
            "",
            "Reflection Windows",
            *format_reflection_queue_lines(brief.reflection_queue),
            "",
            "Decisions",
            *format_decision_queue_lines(brief.decision_queue),
            "",
            "Next Commands",
            *[f"- {command}" for command in brief.suggested_commands],
        ]
    )
    return "\n".join(lines)


def format_entry_line(entry: Entry) -> str:
    tags = f"; tags: {', '.join(entry.tags)}" if entry.tags else ""
    return f"- #{entry.id} {entry.title} ({entry.type}{tags})"


def format_reflection_queue_lines(queue: ReflectionQueue) -> list[str]:
    if not queue.items:
        return ["- no reflection windows need attention right now"]

    lines: list[str] = []
    for item in queue.items:
        lines.append(
            f"- {item.period_type}: {item.period_start} to {item.period_end} "
            f"({item.entry_count} memories)"
        )
        lines.append(f"  {item.command}")
    return lines


def format_decision_queue_lines(queue: DecisionReviewQueue) -> list[str]:
    text = format_decision_review_queue(queue)
    return [
        f"- {line}" if line and not line.startswith("-") else line
        for line in text.splitlines()
    ]
