"""App-only reflection generation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from waymark.storage import Entry, Reflection


@dataclass(frozen=True)
class ReflectionDraft:
    period_type: str
    period_start: str
    period_end: str
    summary: str
    wins: tuple[str, ...]
    patterns: tuple[str, ...]
    suggestions: tuple[str, ...]


@dataclass(frozen=True)
class ReflectionQueueItem:
    period_type: str
    period_start: str
    period_end: str
    entry_count: int
    latest_saved_reflection_id: int | None
    latest_saved_window: str | None
    command: str
    reason: str


@dataclass(frozen=True)
class ReflectionQueue:
    items: tuple[ReflectionQueueItem, ...]


@dataclass(frozen=True)
class ReflectionComparison:
    period_type: str
    period_start: str
    period_end: str
    current_entry_count: int
    current_summary: str
    latest_saved_reflection_id: int | None
    latest_saved_window: str | None
    saved_summary: str | None
    new_wins: tuple[str, ...]
    repeated_wins: tuple[str, ...]
    dropped_wins: tuple[str, ...]
    current_suggestions: tuple[str, ...]


@dataclass(frozen=True)
class TrendItem:
    text: str
    count: int


@dataclass(frozen=True)
class ReflectionTrend:
    period_type: str
    total_reflections: int
    first_window: str | None
    latest_window: str | None
    repeated_patterns: tuple[TrendItem, ...]
    repeated_suggestions: tuple[TrendItem, ...]
    latest_summaries: tuple[str, ...]
    scope_description: str | None = None


def first_reflection_queue_item(queue: ReflectionQueue) -> ReflectionQueueItem | None:
    return queue.items[0] if queue.items else None


def reflection_window(period_type: str, *, today: date | None = None) -> tuple[str, str]:
    current_date = today or datetime.now(UTC).date()
    normalized = normalize_period_type(period_type)

    if normalized == "today":
        start = current_date
    elif normalized == "week":
        start = current_date - timedelta(days=6)
    elif normalized == "month":
        start = current_date.replace(day=1)
    else:
        raise ValueError(f"Unsupported reflection period: {period_type}")

    return start.isoformat(), current_date.isoformat()


def normalize_period_type(period_type: str) -> str:
    normalized = period_type.strip().lower().replace("_", "-")
    aliases = {
        "day": "today",
        "daily": "today",
        "today": "today",
        "week": "week",
        "weekly": "week",
        "this-week": "week",
        "month": "month",
        "monthly": "month",
        "this-month": "month",
    }
    return aliases.get(normalized, normalized)


def build_reflection_queue(
    *,
    entries: list[Entry],
    reflections: list[Reflection],
    today: date | None = None,
) -> ReflectionQueue:
    current_date = today or datetime.now(UTC).date()
    items: list[ReflectionQueueItem] = []
    for period_type in ("today", "week", "month"):
        period_start, period_end = reflection_window(period_type, today=current_date)
        entry_count = count_entries_in_window(
            entries,
            period_start=period_start,
            period_end=period_end,
        )
        if entry_count == 0:
            continue
        if has_saved_reflection(
            reflections,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
        ):
            continue
        latest_saved = latest_saved_reflection(reflections, period_type=period_type)
        items.append(
            ReflectionQueueItem(
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
                entry_count=entry_count,
                latest_saved_reflection_id=latest_saved.id if latest_saved else None,
                latest_saved_window=reflection_window_label(latest_saved),
                command=f"waymark reflect --period {period_type} --save",
                reason=reflection_queue_reason(
                    period_type=period_type,
                    entry_count=entry_count,
                    latest_saved_reflection=latest_saved,
                ),
            )
        )
    return ReflectionQueue(items=tuple(items))


def format_reflection_queue(queue: ReflectionQueue) -> str:
    if not queue.items:
        return "No reflection windows need attention right now."

    lines = ["Reflection Windows"]
    for item in queue.items:
        lines.append(
            f"- {item.period_type}: {item.period_start} to {item.period_end} "
            f"({item.entry_count} memories)"
        )
        if item.latest_saved_window:
            lines.append(f"  Latest saved: {item.latest_saved_window}")
        lines.append(f"  {item.reason}")
        lines.append(f"  {item.command}")
    return "\n".join(lines)


def generate_reflection(
    entries: list[Entry],
    *,
    period_type: str,
    period_start: str,
    period_end: str,
) -> ReflectionDraft:
    normalized_period = normalize_period_type(period_type)

    if not entries:
        return ReflectionDraft(
            period_type=normalized_period,
            period_start=period_start,
            period_end=period_end,
            summary=f"No saved memories found for {period_start} to {period_end}.",
            wins=(),
            patterns=("This period is under-documented.",),
            suggestions=("Capture one honest moment before the day ends.",),
        )

    type_counts = Counter(entry.type for entry in entries)
    tag_counts = Counter(tag for entry in entries for tag in entry.tags)
    top_types = ", ".join(f"{name} ({count})" for name, count in type_counts.most_common(3))
    top_tags = ", ".join(f"{name} ({count})" for name, count in tag_counts.most_common(5))
    area_word = "area" if len(type_counts) == 1 else "areas"

    summary = (
        f"You captured {len(entries)} memories across {len(type_counts)} {area_word}"
        f" from {period_start} to {period_end}."
    )
    wins = tuple(f"#{entry.id} {entry.title}" for entry in entries[:3])

    patterns = [f"Most active memory types: {top_types}."]
    if top_tags:
        patterns.append(f"Recurring tags: {top_tags}.")
    if "decision" not in type_counts:
        patterns.append("No decision-type memories were captured in this period.")

    suggestions = []
    if "decision" not in type_counts:
        suggestions.append("Record one decision you are currently carrying.")
    if len(entries) < 3:
        suggestions.append("Capture a little more context before generating a deeper reflection.")
    else:
        suggestions.append("Review the top theme and decide whether it deserves a next step.")

    return ReflectionDraft(
        period_type=normalized_period,
        period_start=period_start,
        period_end=period_end,
        summary=summary,
        wins=wins,
        patterns=tuple(patterns),
        suggestions=tuple(suggestions),
    )


def build_reflection_comparison(
    *,
    entries: list[Entry],
    reflections: list[Reflection],
    period_type: str,
    period_start: str,
    period_end: str,
) -> ReflectionComparison:
    draft = generate_reflection(
        entries,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
    )
    latest_saved = latest_saved_reflection(reflections, period_type=draft.period_type)
    saved_wins = latest_saved.wins if latest_saved is not None else ()
    current_wins = draft.wins
    saved_win_set = set(saved_wins)
    current_win_set = set(current_wins)

    return ReflectionComparison(
        period_type=draft.period_type,
        period_start=period_start,
        period_end=period_end,
        current_entry_count=len(entries),
        current_summary=draft.summary,
        latest_saved_reflection_id=latest_saved.id if latest_saved is not None else None,
        latest_saved_window=reflection_window_label(latest_saved),
        saved_summary=latest_saved.summary if latest_saved is not None else None,
        new_wins=tuple(win for win in current_wins if win not in saved_win_set),
        repeated_wins=tuple(win for win in current_wins if win in saved_win_set),
        dropped_wins=tuple(win for win in saved_wins if win not in current_win_set),
        current_suggestions=draft.suggestions,
    )


def format_reflection_comparison(comparison: ReflectionComparison) -> str:
    latest_saved = comparison.latest_saved_window or "none"
    saved_summary = comparison.saved_summary or "No saved reflection for this period yet."
    return "\n\n".join(
        [
            (
                f"{comparison.period_type.title()} Reflection Comparison "
                f"({comparison.period_start} to {comparison.period_end})"
            ),
            f"Current window: {comparison.current_entry_count} memories",
            f"Current summary\n{comparison.current_summary}",
            f"Latest saved: {latest_saved}",
            f"Saved summary\n{saved_summary}",
            format_section("New source wins", comparison.new_wins),
            format_section("Repeated source wins", comparison.repeated_wins),
            format_section("Previously saved wins not in current window", comparison.dropped_wins),
            format_section("Current suggested next step", comparison.current_suggestions[:1]),
        ]
    )


def build_reflection_trend(
    reflections: list[Reflection],
    *,
    period_type: str | None = None,
    entries: list[Entry] | None = None,
    tags: Iterable[str] = (),
    memory_types: Iterable[str] = (),
    limit: int = 5,
) -> ReflectionTrend:
    normalized_period = normalize_period_type(period_type) if period_type else "all"
    normalized_tags = normalize_scope_values(tags)
    normalized_memory_types = normalize_scope_values(memory_types)
    scope_description = reflection_trend_scope_description(
        tags=normalized_tags,
        memory_types=normalized_memory_types,
    )
    matching = [
        reflection
        for reflection in reflections
        if period_type is None
        or normalize_period_type(reflection.period_type) == normalized_period
    ]
    if scope_description is not None:
        scoped_entries = entries or []
        matching = [
            reflection
            for reflection in matching
            if reflection_window_has_matching_entry(
                reflection,
                scoped_entries,
                tags=normalized_tags,
                memory_types=normalized_memory_types,
            )
        ]
    matching.sort(key=lambda reflection: reflection.period_start)
    latest = sorted(matching, key=lambda reflection: reflection.created_at, reverse=True)

    return ReflectionTrend(
        period_type=normalized_period,
        total_reflections=len(matching),
        first_window=reflection_window_label(matching[0]) if matching else None,
        latest_window=reflection_window_label(matching[-1]) if matching else None,
        repeated_patterns=count_trend_items(
            pattern for reflection in matching for pattern in reflection.patterns
        ),
        repeated_suggestions=count_trend_items(
            suggestion for reflection in matching for suggestion in reflection.suggestions
        ),
        latest_summaries=tuple(
            f"#{reflection.id} {reflection.period_start} to {reflection.period_end}: "
            f"{reflection.summary}"
            for reflection in latest[:limit]
        ),
        scope_description=scope_description,
    )


def format_reflection_trend(trend: ReflectionTrend) -> str:
    if trend.total_reflections == 0:
        if trend.scope_description:
            return (
                f"No saved {trend.period_type} reflections matched "
                f"{trend.scope_description}."
            )
        return f"No saved {trend.period_type} reflections yet."

    lines = [
        f"Saved Reflection Trends ({trend.period_type})",
        f"Saved reflections: {trend.total_reflections}",
    ]
    if trend.scope_description:
        lines.append(f"Memory scope: {trend.scope_description}")
    lines.extend(
        [
            f"Window range: {trend.first_window} -> {trend.latest_window}",
            format_trend_section("Repeated patterns", trend.repeated_patterns),
            format_trend_section("Repeated suggestions", trend.repeated_suggestions),
            format_section("Latest summaries", trend.latest_summaries),
        ]
    )
    return "\n\n".join(lines)


def reflection_window_has_matching_entry(
    reflection: Reflection,
    entries: list[Entry],
    *,
    tags: tuple[str, ...],
    memory_types: tuple[str, ...],
) -> bool:
    return any(
        entry_matches_scope(entry, tags=tags, memory_types=memory_types)
        for entry in entries
        if (entry_date := entry_date_from_created_at(entry.created_at)) is not None
        and reflection.period_start <= entry_date <= reflection.period_end
    )


def entry_matches_scope(
    entry: Entry,
    *,
    tags: tuple[str, ...],
    memory_types: tuple[str, ...],
) -> bool:
    entry_tags = set(normalize_scope_values(entry.tags))
    entry_type = entry.type.strip().lower()
    matches_tags = not tags or bool(entry_tags.intersection(tags))
    matches_type = not memory_types or entry_type in memory_types
    return matches_tags and matches_type


def normalize_scope_values(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({value.strip().lower() for value in values if value.strip()}))


def reflection_trend_scope_description(
    *,
    tags: tuple[str, ...],
    memory_types: tuple[str, ...],
) -> str | None:
    parts: list[str] = []
    if tags:
        parts.append(f"tags: {', '.join(tags)}")
    if memory_types:
        parts.append(f"types: {', '.join(memory_types)}")
    return "; ".join(parts) if parts else None


def count_trend_items(values: Iterable[object]) -> tuple[TrendItem, ...]:
    counter = Counter(str(value) for value in values if str(value).strip())
    return tuple(TrendItem(text=text, count=count) for text, count in counter.most_common(5))


def count_entries_in_window(
    entries: list[Entry],
    *,
    period_start: str,
    period_end: str,
) -> int:
    return sum(
        1
        for entry in entries
        if (entry_date := entry_date_from_created_at(entry.created_at)) is not None
        and period_start <= entry_date <= period_end
    )


def entry_date_from_created_at(created_at: str) -> str | None:
    try:
        return datetime.fromisoformat(created_at).date().isoformat()
    except ValueError:
        prefix = created_at[:10]
        try:
            return date.fromisoformat(prefix).isoformat()
        except ValueError:
            return None


def has_saved_reflection(
    reflections: list[Reflection],
    *,
    period_type: str,
    period_start: str,
    period_end: str,
) -> bool:
    return (
        saved_reflection_for_window(
            reflections,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
        )
        is not None
    )


def saved_reflection_for_window(
    reflections: list[Reflection],
    *,
    period_type: str,
    period_start: str,
    period_end: str,
) -> Reflection | None:
    normalized_period = normalize_period_type(period_type)
    matching = [
        reflection
        for reflection in reflections
        if normalize_period_type(reflection.period_type) == normalized_period
        and reflection.period_start == period_start
        and reflection.period_end == period_end
    ]
    if not matching:
        return None
    return max(matching, key=lambda reflection: reflection.created_at)


def latest_saved_reflection(
    reflections: list[Reflection],
    *,
    period_type: str,
) -> Reflection | None:
    normalized_period = normalize_period_type(period_type)
    matching = [
        reflection
        for reflection in reflections
        if normalize_period_type(reflection.period_type) == normalized_period
    ]
    if not matching:
        return None
    return max(matching, key=lambda reflection: reflection.created_at)


def reflection_window_label(reflection: Reflection | None) -> str | None:
    if reflection is None:
        return None
    return f"#{reflection.id} {reflection.period_start} to {reflection.period_end}"


def reflection_queue_reason(
    *,
    period_type: str,
    entry_count: int,
    latest_saved_reflection: Reflection | None,
) -> str:
    memory_word = "memory" if entry_count == 1 else "memories"
    if latest_saved_reflection is None:
        return f"{entry_count} {memory_word} captured; no saved {period_type} reflection yet."
    return (
        f"{entry_count} {memory_word} captured; latest saved {period_type} reflection "
        f"is {reflection_window_label(latest_saved_reflection)}."
    )


def format_reflection(draft: ReflectionDraft) -> str:
    return "\n\n".join(
        [
            f"{draft.period_type.title()} Reflection ({draft.period_start} to {draft.period_end})",
            draft.summary,
            format_section("Wins", draft.wins),
            format_section("Patterns", draft.patterns),
            format_section("Suggested next step", draft.suggestions[:1]),
        ]
    )


def format_saved_reflection(reflection: Reflection) -> str:
    return "\n\n".join(
        [
            (
                f"Saved Reflection #{reflection.id} "
                f"({reflection.period_start} to {reflection.period_end})"
            ),
            reflection.summary,
            format_section("Wins", reflection.wins),
            format_section("Patterns", reflection.patterns),
            format_section("Suggested next step", reflection.suggestions[:1]),
            f"Created: {reflection.created_at}",
        ]
    )


def format_trend_section(title: str, items: tuple[TrendItem, ...]) -> str:
    if not items:
        return f"{title}\n- None yet"
    return f"{title}\n" + "\n".join(f"- {item.text} ({item.count})" for item in items)


def format_section(title: str, items: tuple[str, ...]) -> str:
    if not items:
        return f"{title}\n- None yet"
    return f"{title}\n" + "\n".join(f"- {item}" for item in items)
