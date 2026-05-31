"""App-only memory health and journey map summaries."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from waymark.storage import Decision, Entry, Reflection

CORE_MEMORY_AREAS = (
    "daily",
    "project",
    "work",
    "career",
    "health",
    "decision",
    "learning",
    "personal",
)
CAPTURE_PROMPTS = {
    "daily": "Capture one ordinary detail from today before it disappears.",
    "project": "Capture one project move, blocker, or next bet.",
    "work": "Capture one work signal, tradeoff, or conversation.",
    "career": "Capture one career question, progress signal, or opportunity.",
    "health": "Capture one health pattern, energy note, or constraint.",
    "decision": "Capture one decision you are circling or need to revisit.",
    "learning": "Capture one thing you learned and how it may change behavior.",
    "personal": "Capture one personal moment that future-you would want preserved.",
}


@dataclass(frozen=True)
class CountItem:
    name: str
    count: int


@dataclass(frozen=True)
class JourneyMap:
    total_memories: int
    memories_last_7_days: int
    memories_last_30_days: int
    top_types: tuple[CountItem, ...]
    top_tags: tuple[CountItem, ...]
    thin_memory_areas: tuple[str, ...]
    capture_prompts: tuple[str, ...]
    open_decisions: int
    decisions_due_for_review: int
    decisions_waiting_for_outcome: int
    open_decision_refs: tuple[str, ...]
    review_decision_refs: tuple[str, ...]
    outcome_decision_refs: tuple[str, ...]
    saved_reflections: int
    latest_reflection: str | None
    suggested_reflection_command: str | None
    reflection_commands: tuple[str, ...]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class DecisionReviewQueue:
    due_for_review: tuple[Decision, ...]
    waiting_for_outcome: tuple[Decision, ...]


def build_journey_map(
    *,
    entries: Sequence[Entry],
    decisions: Sequence[Decision],
    reflections: Sequence[Reflection],
    today: date | None = None,
) -> JourneyMap:
    current_date = today or datetime.now(UTC).date()
    top_types = count_items(entry.type for entry in entries)
    top_tags = count_items(tag for entry in entries for tag in entry.tags)
    thin_memory_areas = find_thin_memory_areas(entries, today=current_date)
    open_decision_list = tuple(decision for decision in decisions if decision.status == "open")
    review_decision_list = tuple(
        decision for decision in decisions if decision_is_due_for_review(decision, current_date)
    )
    outcome_decision_list = tuple(
        decision for decision in decisions if decision.status == "decided" and not decision.outcome
    )
    latest_reflection = format_latest_reflection(reflections)

    journey_map = JourneyMap(
        total_memories=len(entries),
        memories_last_7_days=count_recent_entries(entries, today=current_date, days=7),
        memories_last_30_days=count_recent_entries(entries, today=current_date, days=30),
        top_types=top_types,
        top_tags=top_tags,
        thin_memory_areas=thin_memory_areas,
        capture_prompts=capture_prompts_for_areas(thin_memory_areas),
        open_decisions=len(open_decision_list),
        decisions_due_for_review=len(review_decision_list),
        decisions_waiting_for_outcome=len(outcome_decision_list),
        open_decision_refs=decision_refs(open_decision_list),
        review_decision_refs=decision_refs(review_decision_list),
        outcome_decision_refs=decision_refs(outcome_decision_list),
        saved_reflections=len(reflections),
        latest_reflection=latest_reflection,
        suggested_reflection_command=suggest_reflection_command(entries, today=current_date),
        reflection_commands=suggest_reflection_commands(entries, today=current_date),
        notes=(),
    )
    return journey_map_with_notes(journey_map)


def build_decision_review_queue(
    decisions: Sequence[Decision],
    *,
    today: date | None = None,
) -> DecisionReviewQueue:
    current_date = today or datetime.now(UTC).date()
    due_for_review = tuple(
        sorted(
            (
                decision
                for decision in decisions
                if decision_is_due_for_review(decision, current_date)
            ),
            key=lambda decision: (decision.review_date or "", decision.id),
        )
    )
    waiting_for_outcome = tuple(
        decision
        for decision in decisions
        if decision.status == "decided" and not decision.outcome
    )
    return DecisionReviewQueue(
        due_for_review=due_for_review,
        waiting_for_outcome=waiting_for_outcome,
    )


def format_decision_review_queue(queue: DecisionReviewQueue) -> str:
    if not queue.due_for_review and not queue.waiting_for_outcome:
        return "No decisions need review right now."

    lines = ["Due for Review"]
    if queue.due_for_review:
        lines.extend(format_review_decision(decision) for decision in queue.due_for_review)
    else:
        lines.append("- none")

    lines.append("")
    lines.append("Waiting for Outcome")
    if queue.waiting_for_outcome:
        lines.extend(format_outcome_decision(decision) for decision in queue.waiting_for_outcome)
    else:
        lines.append("- none")

    return "\n".join(lines)


def journey_map_with_notes(journey_map: JourneyMap) -> JourneyMap:
    notes: list[str] = []
    if journey_map.total_memories == 0:
        notes.append("Start with one capture; the map grows from saved memories.")
    elif journey_map.memories_last_7_days == 0:
        notes.append("No captures in the last 7 days; add one recent memory to refresh context.")
    else:
        notes.append("Recent capture rhythm is active.")

    if journey_map.open_decisions:
        notes.append(f"{journey_map.open_decisions} open decision(s) need a next step.")
    if journey_map.decisions_due_for_review:
        notes.append(
            f"{journey_map.decisions_due_for_review} decision(s) are ready for review."
        )
    if journey_map.decisions_waiting_for_outcome:
        notes.append(
            f"{journey_map.decisions_waiting_for_outcome} decided item(s) need outcomes."
        )

    if journey_map.saved_reflections == 0:
        notes.append("No saved reflections yet; try waymark reflect --save.")
    else:
        notes.append(f"Latest reflection: {journey_map.latest_reflection}.")
    if journey_map.thin_memory_areas:
        areas = ", ".join(journey_map.thin_memory_areas[:3])
        notes.append(f"Thin memory areas from the last 30 days: {areas}.")

    return JourneyMap(
        total_memories=journey_map.total_memories,
        memories_last_7_days=journey_map.memories_last_7_days,
        memories_last_30_days=journey_map.memories_last_30_days,
        top_types=journey_map.top_types,
        top_tags=journey_map.top_tags,
        thin_memory_areas=journey_map.thin_memory_areas,
        capture_prompts=journey_map.capture_prompts,
        open_decisions=journey_map.open_decisions,
        decisions_due_for_review=journey_map.decisions_due_for_review,
        decisions_waiting_for_outcome=journey_map.decisions_waiting_for_outcome,
        open_decision_refs=journey_map.open_decision_refs,
        review_decision_refs=journey_map.review_decision_refs,
        outcome_decision_refs=journey_map.outcome_decision_refs,
        saved_reflections=journey_map.saved_reflections,
        latest_reflection=journey_map.latest_reflection,
        suggested_reflection_command=journey_map.suggested_reflection_command,
        reflection_commands=journey_map.reflection_commands,
        notes=tuple(notes),
    )


def format_journey_map(journey_map: JourneyMap) -> str:
    return "\n".join(
        [
            "Memory Health",
            f"- Total memories: {journey_map.total_memories}",
            f"- Captured in last 7 days: {journey_map.memories_last_7_days}",
            f"- Captured in last 30 days: {journey_map.memories_last_30_days}",
            f"- Top memory types: {format_count_items(journey_map.top_types)}",
            f"- Top tags: {format_count_items(journey_map.top_tags)}",
            f"- Thin areas: {format_refs(journey_map.thin_memory_areas)}",
            "",
            "Capture Prompts",
            *[f"- {prompt}" for prompt in journey_map.capture_prompts],
            "",
            "Decisions",
            f"- Open: {journey_map.open_decisions}",
            f"- Due for review: {journey_map.decisions_due_for_review}",
            f"- Waiting for outcome: {journey_map.decisions_waiting_for_outcome}",
            f"- Open IDs: {format_refs(journey_map.open_decision_refs)}",
            f"- Review IDs: {format_refs(journey_map.review_decision_refs)}",
            f"- Outcome IDs: {format_refs(journey_map.outcome_decision_refs)}",
            "",
            "Reflections",
            f"- Saved reflections: {journey_map.saved_reflections}",
            f"- Latest: {journey_map.latest_reflection or 'none'}",
            f"- Suggested command: {journey_map.suggested_reflection_command or 'none yet'}",
            f"- Reflection options: {format_refs(journey_map.reflection_commands)}",
            "",
            "Next Signals",
            *[f"- {note}" for note in journey_map.notes],
        ]
    )


def decision_is_due_for_review(decision: Decision, today: date) -> bool:
    if decision.review_date is None or decision.status not in {"open", "decided"}:
        return False
    review_date = parse_date(decision.review_date)
    return review_date is not None and review_date <= today


def decision_refs(decisions: Sequence[Decision], *, limit: int = 5) -> tuple[str, ...]:
    return tuple(f"#{decision.id} {decision.title}" for decision in decisions[:limit])


def format_review_decision(decision: Decision) -> str:
    review_date = decision.review_date or "no date"
    confidence = f", confidence {decision.confidence}/5" if decision.confidence else ""
    return (
        f"- #{decision.id} {decision.title} "
        f"({decision.status}, review {review_date}{confidence})"
    )


def format_outcome_decision(decision: Decision) -> str:
    choice = f", choice: {decision.final_choice}" if decision.final_choice else ""
    return f"- #{decision.id} {decision.title} ({decision.status}{choice})"


def find_thin_memory_areas(
    entries: Sequence[Entry],
    *,
    today: date,
    areas: Sequence[str] = CORE_MEMORY_AREAS,
    limit: int = 5,
) -> tuple[str, ...]:
    start_date = today - timedelta(days=29)
    recent_types = {
        entry.type
        for entry in entries
        if (entry_date := parse_entry_date(entry.created_at)) is not None
        and start_date <= entry_date <= today
    }
    return tuple(area for area in areas if area not in recent_types)[:limit]


def capture_prompts_for_areas(areas: Sequence[str], *, limit: int = 3) -> tuple[str, ...]:
    prompts = [CAPTURE_PROMPTS[area] for area in areas if area in CAPTURE_PROMPTS]
    return tuple(prompts[:limit])


def suggest_reflection_command(entries: Sequence[Entry], *, today: date) -> str | None:
    commands = suggest_reflection_commands(entries, today=today)
    return commands[0] if commands else None


def suggest_reflection_commands(entries: Sequence[Entry], *, today: date) -> tuple[str, ...]:
    if not entries:
        return ()
    commands: list[str] = []
    if count_recent_entries(entries, today=today, days=1) > 0:
        commands.append("waymark reflect --period today --save")
    if count_recent_entries(entries, today=today, days=7) >= 2:
        commands.append("waymark reflect --period week --save")
    if count_recent_entries(entries, today=today, days=30) >= 6:
        commands.append("waymark reflect --period month --save")
    if not commands:
        commands.append("waymark reflect --period week --save")
    return tuple(commands)


def count_items(values: Iterable[str]) -> tuple[CountItem, ...]:
    counter = Counter(value for value in values if value)
    return tuple(CountItem(name=name, count=count) for name, count in counter.most_common(5))


def count_recent_entries(entries: Sequence[Entry], *, today: date, days: int) -> int:
    start_date = today - timedelta(days=days - 1)
    return sum(
        1
        for entry in entries
        if (entry_date := parse_entry_date(entry.created_at)) is not None
        and start_date <= entry_date <= today
    )


def parse_entry_date(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return parse_date(value[:10])


def parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def format_latest_reflection(reflections: Sequence[Reflection]) -> str | None:
    if not reflections:
        return None
    latest = max(reflections, key=lambda reflection: reflection.created_at)
    return f"{latest.period_type} {latest.period_start} to {latest.period_end}"


def format_count_items(items: Sequence[CountItem]) -> str:
    if not items:
        return "none"
    return ", ".join(f"{item.name} ({item.count})" for item in items)


def format_refs(refs: Sequence[str]) -> str:
    if not refs:
        return "none"
    return ", ".join(refs)
