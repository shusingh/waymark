"""Textual guided interface for Waymark."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Static, TextArea

from waymark.ai import structure_memory_with_ollama
from waymark.config import build_recommended_config, read_config, write_config
from waymark.drafting import build_capture_draft
from waymark.exports import (
    format_entry_markdown,
    format_reflection_markdown,
    format_reflection_trend_markdown,
    format_timeline_markdown,
    write_markdown_export,
)
from waymark.imports import (
    DuplicateDocxImportError,
    DuplicateMarkdownImportError,
    DuplicatePdfImportError,
    DuplicateTextImportError,
    MarkdownFolderPreview,
    MissingImportDependencyError,
    import_docx_file,
    import_markdown_file,
    import_markdown_preview,
    import_pdf_file,
    import_text_file,
    preview_markdown_folder,
)
from waymark.journey import (
    build_decision_review_queue,
    build_journey_map,
    format_decision_review_queue,
    format_journey_map,
)
from waymark.memory import MemoryDraft
from waymark.model_setup import ModelSetupPlan, build_model_setup_plan
from waymark.paths import config_path, database_path
from waymark.reflection import (
    ReflectionDraft,
    build_reflection_comparison,
    build_reflection_queue,
    build_reflection_trend,
    first_reflection_queue_item,
    format_reflection,
    format_reflection_comparison,
    format_reflection_queue,
    format_reflection_trend,
    format_saved_reflection,
    generate_reflection,
    reflection_window,
    saved_reflection_for_window,
)
from waymark.retrieval import compose_source_answer, rank_retrieved_entries
from waymark.runtime import get_ollama_status
from waymark.storage import (
    Decision,
    Entry,
    add_decision,
    add_entry,
    add_reflection,
    finalize_decision,
    get_entry,
    get_reflection,
    get_source,
    init_database,
    link_decision_entry,
    list_decisions,
    list_entries,
    list_entries_between,
    list_entry_decisions,
    list_reflections,
    record_decision_outcome,
    search_entries,
    search_entries_by_tags,
    source_id_from_entry,
    source_label,
    update_entry,
)
from waymark.system import collect_system_profile

MEMORY_TYPES = ("daily", "project", "work", "career", "health", "decision", "learning", "personal")


def format_entry(entry: Entry, *, source_note: str | None = None) -> str:
    tags = f"  tags: {', '.join(entry.tags)}" if entry.tags else ""
    source = f"\nsource: {source_note}" if source_note else ""
    return (
        f"{entry.created_at}\n"
        f"#{entry.id}  {entry.type.upper()}  {entry.title}\n"
        f"{entry.summary}{tags}{source}"
    )


def format_entry_with_source(db_path: Path, entry: Entry) -> str:
    source_id = source_id_from_entry(entry)
    source_note = source_label(get_source(db_path, source_id)) if source_id else entry.source
    return format_entry(entry, source_note=source_note)


def format_memory_refs(entry_ids: tuple[int, ...]) -> str:
    return ", ".join(f"#{entry_id}" for entry_id in entry_ids) or "none"


def parse_comma_values(raw_value: str) -> tuple[str, ...]:
    return tuple(value.strip() for value in raw_value.split(",") if value.strip())


def format_decision(decision: Decision) -> str:
    options = "\n".join(f"- {option}" for option in decision.options) or "- No options captured yet"
    confidence = f"{decision.confidence}/5" if decision.confidence else "not set"
    review = decision.review_date or "not set"
    final_choice = decision.final_choice or "not set"
    linked_memories = format_memory_refs(decision.entry_ids)
    outcome = f"\n\nOutcome\n{decision.outcome}" if decision.outcome else ""
    return (
        f"#{decision.id}  {decision.status.upper()}  {decision.title}\n"
        f"{decision.context}\n\n"
        f"Options\n{options}\n\n"
        f"Linked memories: {linked_memories}\n"
        f"Final choice: {final_choice}\n"
        f"Confidence: {confidence}  Review: {review}"
        f"{outcome}"
    )


def format_memory_detail(db_path: Path, entry: Entry) -> str:
    tags = ", ".join(entry.tags) if entry.tags else "none"
    source_id = source_id_from_entry(entry)
    source = source_label(get_source(db_path, source_id)) if source_id else entry.source
    decisions = list_entry_decisions(db_path, entry_id=entry.id)
    linked_decisions = "\n".join(
        f"- #{decision.id} {decision.status.upper()} {decision.title}" for decision in decisions
    )
    if not linked_decisions:
        linked_decisions = "- No linked decisions yet"
    return (
        f"#{entry.id}  {entry.type.upper()}  {entry.title}\n"
        f"Created: {entry.created_at}\n"
        f"Tags: {tags}\n"
        f"Source: {source}\n\n"
        f"Summary\n{entry.summary}\n\n"
        f"Memory\n{entry.raw_text.strip()}\n\n"
        f"Linked Decisions\n{linked_decisions}"
    )


def format_model_setup_plan(plan: ModelSetupPlan) -> str:
    lines = [f"Recommended mode: {plan.mode}", plan.reason, ""]
    if not plan.runtime_available:
        lines.append("Ollama: not found")
        if plan.runtime_error:
            lines.append(plan.runtime_error)
        lines.append("")
    elif plan.runtime_error:
        lines.append(f"Ollama: detected with warning: {plan.runtime_error}")
        lines.append("")
    else:
        lines.append("Ollama: detected")
        lines.append("")

    if not plan.items:
        lines.append("No local AI models are recommended for this machine yet.")
    else:
        lines.append("Recommended models")
        for item in plan.items:
            status = "installed" if item.installed else "missing"
            command = "already present" if item.installed else item.command
            lines.append(f"- {item.purpose}: {item.model} ({status})")
            lines.append(f"  {command}")

    lines.append("")
    lines.append("No models are downloaded here. No files are scanned.")
    return "\n".join(lines)


def reflection_period_from_command(command: str) -> str:
    parts = command.split()
    if "--period" not in parts:
        return "week"
    index = parts.index("--period") + 1
    if index >= len(parts):
        return "week"
    period = parts[index].strip().lower()
    return period if period in {"today", "week", "month"} else "week"


class WaymarkScreen(Screen[None]):
    """Common screen behavior."""

    BINDINGS = [
        Binding("m", "show_menu", "Menu"),
        Binding("c", "show_capture", "Capture"),
        Binding("t", "show_timeline", "Timeline"),
        Binding("r", "show_reflect", "Reflect"),
        Binding("d", "show_decisions", "Decisions"),
        Binding("i", "show_import", "Import"),
        Binding("x", "show_export", "Export"),
        Binding("a", "show_ask", "Ask"),
        Binding("v", "show_memory", "Memory"),
        Binding("j", "show_journey", "Journey"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self.db_path = db_path

    async def action_show_menu(self) -> None:
        await self.app.push_screen(MainMenuScreen(self.db_path))

    async def action_show_capture(self) -> None:
        await self.app.push_screen(CaptureScreen(self.db_path))

    async def action_show_timeline(self) -> None:
        await self.app.push_screen(TimelineScreen(self.db_path))

    async def action_show_ask(self) -> None:
        await self.app.push_screen(AskScreen(self.db_path))

    async def action_show_decisions(self) -> None:
        await self.app.push_screen(DecisionsScreen(self.db_path))

    async def action_show_reflect(self) -> None:
        await self.app.push_screen(ReflectScreen(self.db_path))

    async def action_show_import(self) -> None:
        await self.app.push_screen(ImportScreen(self.db_path))

    async def action_show_export(self) -> None:
        await self.app.push_screen(ExportScreen(self.db_path))

    async def action_show_memory(self) -> None:
        await self.app.push_screen(MemoryScreen(self.db_path))

    async def action_show_journey(self) -> None:
        await self.app.push_screen(JourneyScreen(self.db_path))


class MainMenuScreen(WaymarkScreen):
    """The guided Waymark hub."""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="shell"):
            yield Static("WAYMARK", id="brand")
            yield Static("Your private memory trail, searchable from the terminal.", id="tagline")
            with Vertical(id="menu-panel"):
                yield Button("[1] Capture a Moment", id="capture", variant="primary")
                yield Button("[2] Ask Waymark", id="ask")
                yield Button("[3] Timeline", id="timeline")
                yield Button("[4] Memory Detail", id="memory")
                yield Button("[5] Reflect", id="reflect")
                yield Button("[6] Decisions", id="decisions")
                yield Button("[7] Import My World", id="import")
                yield Button("[8] Export Markdown", id="export")
                yield Button("[9] Journey Map", id="journey")
                yield Button("[10] Doctor", id="doctor")
            yield Static(
                "Local AI is optional. Setup shows recommendations before anything is installed.",
                classes="note",
            )
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "capture":
            await self.action_show_capture()
        elif button_id == "ask":
            await self.action_show_ask()
        elif button_id == "timeline":
            await self.action_show_timeline()
        elif button_id == "memory":
            await self.action_show_memory()
        elif button_id == "reflect":
            await self.action_show_reflect()
        elif button_id == "decisions":
            await self.action_show_decisions()
        elif button_id == "import":
            await self.action_show_import()
        elif button_id == "export":
            await self.action_show_export()
        elif button_id == "journey":
            await self.action_show_journey()
        elif button_id == "doctor":
            await self.app.push_screen(DoctorScreen(self.db_path))


class CaptureScreen(WaymarkScreen):
    """Manual capture with a structured memory-card preview."""

    def __init__(
        self,
        db_path: Path,
        *,
        initial_memory_type: str = "daily",
        initial_text: str = "",
    ) -> None:
        super().__init__(db_path)
        self.current_draft: MemoryDraft | None = None
        self.initial_memory_type = initial_memory_type
        self.initial_text = initial_text

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="shell"):
            yield Static("Capture a Moment", classes="screen-title")
            yield Static(
                "Write the raw thought first. Waymark drafts a memory card before saving.",
                classes="subtle",
            )
            with Horizontal(id="capture-grid"):
                with Vertical(classes="panel"):
                    yield Static("Memory type", classes="label")
                    yield Input(
                        value=self.initial_memory_type,
                        placeholder=", ".join(MEMORY_TYPES),
                        id="memory-type",
                    )
                    yield Static("Tags", classes="label")
                    yield Input(placeholder="project, local-first, terminal", id="memory-tags")
                    yield Static("Local AI", classes="label")
                    yield Input(value="no", placeholder="yes/no", id="capture-local-ai")
                with Vertical(classes="panel"):
                    yield Static("Raw thought", classes="label")
                    yield TextArea(
                        self.initial_text,
                        id="memory-text",
                        show_line_numbers=False,
                        placeholder="What should future-you be able to remember?",
                    )
                    yield Button("Draft Memory", id="draft", variant="primary")
                with Vertical(classes="panel", id="draft-panel"):
                    yield Static("Draft preview", classes="label")
                    yield Static("No draft yet.", id="draft-preview", classes="memory-card")
                    with Horizontal(id="draft-actions"):
                        yield Button("Save", id="save", variant="success", disabled=True)
                        yield Button("Edit", id="edit", disabled=True)
                        yield Button("Discard", id="discard", variant="error", disabled=True)
            yield Static("Nothing saved yet.", id="capture-status", classes="note")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#memory-text", TextArea).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "draft":
            self.prepare_draft()
        elif event.button.id == "save":
            self.save_draft()
        elif event.button.id == "edit":
            self.edit_draft()
        elif event.button.id == "discard":
            self.clear_draft("Draft discarded.")

    def prepare_draft(self) -> None:
        raw_text = self.query_one("#memory-text", TextArea).text
        if not raw_text.strip():
            self.query_one("#capture-status", Static).update("Write a memory before saving.")
            return

        memory_type = self.query_one("#memory-type", Input).value
        raw_tags = self.query_one("#memory-tags", Input).value
        local_ai = self.parse_local_ai_flag()
        if local_ai is None:
            return

        config = read_config(config_path())
        should_check_runtime = (
            local_ai
            and config is not None
            and config.models.runtime == "ollama"
            and config.models.chat_model is not None
        )
        runtime_status = get_ollama_status() if should_check_runtime else None
        draft_result = build_capture_draft(
            raw_text,
            memory_type=memory_type,
            raw_tags=raw_tags,
            local_ai=local_ai,
            config=config,
            runtime_status=runtime_status,
            structure_memory=structure_memory_with_ollama,
        )
        self.current_draft = draft_result.draft
        self.query_one("#draft-preview", Static).update(self.format_draft(self.current_draft))
        self.set_draft_actions(enabled=True)
        status = "Draft ready. Save it, edit the raw thought, or discard it."
        if draft_result.note:
            status = f"{draft_result.note}\n{status}"
        elif local_ai:
            status = f"Drafted with {draft_result.source}.\n{status}"
        self.query_one("#capture-status", Static).update(status)

    def save_draft(self) -> None:
        draft = self.current_draft
        if draft is None:
            self.prepare_draft()
            draft = self.current_draft
            if draft is None:
                return

        entry_id = add_entry(
            self.db_path,
            raw_text=draft.raw_text,
            memory_type=draft.memory_type,
            title=draft.title,
            summary=draft.summary,
            tags=draft.tags,
        )

        self.query_one("#capture-status", Static).update(
            f"Saved #{entry_id}: {draft.title}\n"
            f"Type: {draft.memory_type}\n"
            f"Tags: {', '.join(draft.tags) if draft.tags else 'none'}"
        )
        self.query_one("#memory-text", TextArea).text = ""
        self.clear_draft()

    def edit_draft(self) -> None:
        self.set_draft_actions(enabled=False)
        self.query_one("#capture-status", Static).update(
            "Edit the raw thought, then draft it again before saving."
        )
        self.query_one("#memory-text", TextArea).focus()

    def clear_draft(self, status: str | None = None) -> None:
        self.current_draft = None
        self.query_one("#draft-preview", Static).update("No draft yet.")
        self.set_draft_actions(enabled=False)
        if status is not None:
            self.query_one("#capture-status", Static).update(status)

    def set_draft_actions(self, *, enabled: bool) -> None:
        self.query_one("#save", Button).disabled = not enabled
        self.query_one("#edit", Button).disabled = not enabled
        self.query_one("#discard", Button).disabled = not enabled

    def parse_local_ai_flag(self) -> bool | None:
        raw_flag = self.query_one("#capture-local-ai", Input).value.strip().lower()
        if raw_flag in {"", "0", "false", "n", "no"}:
            return False
        if raw_flag in {"1", "ai", "local-ai", "true", "y", "yes"}:
            return True
        self.query_one("#capture-status", Static).update("Local AI must be yes or no.")
        return None

    def format_draft(self, draft: MemoryDraft) -> str:
        tags = ", ".join(draft.tags) if draft.tags else "none"
        return (
            f"Title\n{draft.title}\n\n"
            f"Summary\n{draft.summary}\n\n"
            f"Type\n{draft.memory_type}\n\n"
            f"Tags\n{tags}"
        )


class TimelineScreen(WaymarkScreen):
    """Chronological memory view."""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="shell"):
            yield Static("Timeline", classes="screen-title")
            yield Static("Recent saved memories, newest first.", classes="subtle")
            yield VerticalScroll(id="timeline-list")
        yield Footer()

    async def on_mount(self) -> None:
        await self.refresh_timeline()

    async def refresh_timeline(self) -> None:
        entries = list_entries(self.db_path, limit=30)
        timeline = self.query_one("#timeline-list", VerticalScroll)
        await timeline.remove_children()

        if not entries:
            await timeline.mount(Static("No memories yet. Press c to capture your first moment."))
            return

        for entry in entries:
            await timeline.mount(
                Static(format_entry_with_source(self.db_path, entry), classes="memory-card")
            )


class JourneyScreen(WaymarkScreen):
    """Memory health and journey map view."""

    def __init__(self, db_path: Path) -> None:
        super().__init__(db_path)
        self.current_journey_map = build_journey_map(
            entries=list_entries(self.db_path, limit=1000),
            decisions=list_decisions(self.db_path, limit=1000),
            reflections=list_reflections(self.db_path, limit=1000),
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="shell"):
            yield Static("Journey Map", classes="screen-title")
            yield Static(
                "A local memory-health snapshot from saved memories, decisions, and reflections.",
                classes="subtle",
            )
            yield Button("Refresh", id="refresh-journey", variant="primary")
            with Horizontal(id="journey-prompt-actions"):
                for index, area in enumerate(self.current_journey_map.thin_memory_areas[:3]):
                    yield Button(f"Capture {area.title()}", id=f"journey-capture-{index}")
            with Horizontal(id="journey-reflection-actions"):
                for index, command in enumerate(self.current_journey_map.reflection_commands[:3]):
                    yield Button(
                        f"Reflect {reflection_period_from_command(command).title()}",
                        id=f"journey-reflect-{index}",
                    )
            yield VerticalScroll(Static(self.render_journey_map(), id="journey-map"))
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh-journey":
            self.query_one("#journey-map", Static).update(self.render_journey_map())
        elif event.button.id and event.button.id.startswith("journey-capture-"):
            await self.open_capture_prompt(event.button.id)
        elif event.button.id and event.button.id.startswith("journey-reflect-"):
            await self.open_reflection_prompt(event.button.id)

    async def open_capture_prompt(self, button_id: str) -> None:
        try:
            prompt_index = int(button_id.removeprefix("journey-capture-"))
        except ValueError:
            return
        if prompt_index >= len(self.current_journey_map.capture_prompts):
            return

        area = self.current_journey_map.thin_memory_areas[prompt_index]
        prompt = self.current_journey_map.capture_prompts[prompt_index]
        await self.app.push_screen(
            CaptureScreen(
                self.db_path,
                initial_memory_type=area,
                initial_text=prompt,
            )
        )

    async def open_reflection_prompt(self, button_id: str) -> None:
        try:
            prompt_index = int(button_id.removeprefix("journey-reflect-"))
        except ValueError:
            return
        if prompt_index >= len(self.current_journey_map.reflection_commands):
            return

        command = self.current_journey_map.reflection_commands[prompt_index]
        await self.app.push_screen(
            ReflectScreen(
                self.db_path,
                initial_period=reflection_period_from_command(command),
            )
        )

    def render_journey_map(self) -> str:
        self.current_journey_map = build_journey_map(
            entries=list_entries(self.db_path, limit=1000),
            decisions=list_decisions(self.db_path, limit=1000),
            reflections=list_reflections(self.db_path, limit=1000),
        )
        return format_journey_map(self.current_journey_map)


class AskScreen(WaymarkScreen):
    """Keyword-backed Ask Waymark screen for app-only mode."""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="shell"):
            yield Static("Ask Waymark", classes="screen-title")
            yield Static(
                "App-only mode uses saved memories, keyword matches, and tags.",
                classes="subtle",
            )
            with Horizontal(id="ask-row"):
                yield Input(placeholder="What do you want to find?", id="ask-query")
                yield Button("Search", id="search", variant="primary")
            yield VerticalScroll(Static("Search results will appear here.", id="ask-results"))
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#ask-query", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "search":
            self.run_search()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "ask-query":
            self.run_search()

    def run_search(self) -> None:
        query = self.query_one("#ask-query", Input).value.strip()
        results = self.query_one("#ask-results", Static)
        if not query:
            results.update("Ask a keyword question first.")
            return

        keyword_entries = search_entries(self.db_path, query=query, limit=5)
        tag_entries = search_entries_by_tags(self.db_path, query=query, limit=5)
        ranked_entries = rank_retrieved_entries(
            keyword_entries=keyword_entries,
            tag_entries=tag_entries,
            semantic_entries=(),
            limit=5,
        )
        entries = [ranked.entry for ranked in ranked_entries]
        if not entries:
            results.update("No matching saved memories found.")
            return

        source_text = "\n\n".join(
            format_entry_with_source(self.db_path, entry) for entry in entries
        )
        answer = compose_source_answer(query, entries)
        results.update(f"Grounded answer\n\n{answer}\n\nSources\n\n{source_text}")


class MemoryScreen(WaymarkScreen):
    """Memory detail view."""

    def __init__(self, db_path: Path) -> None:
        super().__init__(db_path)
        self.current_entry_id: int | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="shell"):
            yield Static("Memory Detail", classes="screen-title")
            with Horizontal(id="memory-detail-controls"):
                yield Input(placeholder="Memory ID", id="memory-detail-id")
                yield Button("Show Memory", id="show-memory", variant="primary")
                yield Button("Save Edits", id="save-memory-edits", variant="success")
            with Horizontal(id="memory-edit-fields"):
                yield Input(placeholder="Title", id="memory-edit-title")
                yield Input(placeholder="Type", id="memory-edit-type")
                yield Input(placeholder="tag one, tag two", id="memory-edit-tags")
            yield Input(placeholder="Summary", id="memory-edit-summary")
            yield TextArea(
                "",
                id="memory-edit-text",
                show_line_numbers=False,
                placeholder="Raw memory text",
            )
            yield Static("Enter a memory ID.", id="memory-detail-status", classes="memory-card")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#memory-detail-id", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "show-memory":
            self.show_memory_from_form()
        elif event.button.id == "save-memory-edits":
            self.save_memory_edits()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "memory-detail-id":
            self.show_memory_from_form()

    def show_memory_from_form(self) -> None:
        raw_id = self.query_one("#memory-detail-id", Input).value.strip()
        if not raw_id:
            self.query_one("#memory-detail-status", Static).update("Enter a memory ID.")
            return
        try:
            entry_id = int(raw_id)
        except ValueError:
            self.query_one("#memory-detail-status", Static).update("Memory ID must be a number.")
            return

        entry = get_entry(self.db_path, entry_id)
        if entry is None:
            self.query_one("#memory-detail-status", Static).update(
                f"Memory #{entry_id} was not found."
            )
            return

        self.query_one("#memory-detail-status", Static).update(
            format_memory_detail(self.db_path, entry)
        )
        self.populate_edit_fields(entry)

    def populate_edit_fields(self, entry: Entry) -> None:
        self.current_entry_id = entry.id
        self.query_one("#memory-edit-title", Input).value = entry.title
        self.query_one("#memory-edit-type", Input).value = entry.type
        self.query_one("#memory-edit-tags", Input).value = ", ".join(entry.tags)
        self.query_one("#memory-edit-summary", Input).value = entry.summary
        self.query_one("#memory-edit-text", TextArea).text = entry.raw_text

    def save_memory_edits(self) -> None:
        entry_id = self.current_entry_id
        if entry_id is None:
            self.query_one("#memory-detail-status", Static).update(
                "Show a memory before saving edits."
            )
            return

        raw_tags = self.query_one("#memory-edit-tags", Input).value
        tags = tuple(tag.strip() for tag in raw_tags.split(",") if tag.strip())
        try:
            updated = update_entry(
                self.db_path,
                entry_id=entry_id,
                raw_text=self.query_one("#memory-edit-text", TextArea).text,
                memory_type=self.query_one("#memory-edit-type", Input).value,
                title=self.query_one("#memory-edit-title", Input).value,
                summary=self.query_one("#memory-edit-summary", Input).value,
                tags=tags,
            )
        except ValueError as error:
            self.query_one("#memory-detail-status", Static).update(str(error))
            return
        if not updated:
            self.query_one("#memory-detail-status", Static).update(
                f"Memory #{entry_id} was not found."
            )
            return

        entry = get_entry(self.db_path, entry_id)
        if entry is None:
            self.query_one("#memory-detail-status", Static).update(
                f"Memory #{entry_id} was not found after update."
            )
            return
        self.populate_edit_fields(entry)
        self.query_one("#memory-detail-status", Static).update(
            f"Saved edits.\n\n{format_memory_detail(self.db_path, entry)}"
        )


class ReflectScreen(WaymarkScreen):
    """App-only reflection view."""

    def __init__(self, db_path: Path, *, initial_period: str = "week") -> None:
        super().__init__(db_path)
        self.current_reflection: ReflectionDraft | None = None
        self.initial_period = initial_period

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="shell"):
            yield Static("Reflect", classes="screen-title")
            yield Static(
                (
                    "Generate a grounded reflection from saved memories. "
                    "App-only mode uses counts and tags."
                ),
                classes="subtle",
            )
            with Horizontal(id="reflect-controls"):
                yield Input(
                    value=self.initial_period,
                    placeholder="today, week, month",
                    id="reflect-period",
                )
                yield Button("Generate", id="generate-reflection", variant="primary")
                yield Button("Save", id="save-reflection", variant="success", disabled=True)
            with Horizontal(id="reflection-trend-scope"):
                yield Input(placeholder="Trend tags", id="reflection-trend-tags")
                yield Input(placeholder="Trend types", id="reflection-trend-types")
            with Horizontal(id="reflection-history-controls"):
                yield Input(placeholder="Saved reflection ID", id="saved-reflection-id")
                yield Button("Due Windows", id="reflection-due")
                yield Button("Generate Due", id="generate-due-reflection")
                yield Button("Compare", id="compare-reflection")
                yield Button("Trends", id="reflection-trends")
                yield Button("History", id="reflection-history")
                yield Button("Show Saved", id="show-saved-reflection")
            yield Static("Generate a reflection to preview it here.", id="reflection-preview")
            yield Static("", id="reflection-status", classes="note")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#reflect-period", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "generate-reflection":
            self.generate_current_reflection()
        elif event.button.id == "save-reflection":
            self.save_current_reflection()
        elif event.button.id == "reflection-due":
            self.show_reflection_queue()
        elif event.button.id == "generate-due-reflection":
            self.generate_due_reflection()
        elif event.button.id == "compare-reflection":
            self.compare_current_reflection()
        elif event.button.id == "reflection-trends":
            self.show_reflection_trends()
        elif event.button.id == "reflection-history":
            self.show_reflection_history()
        elif event.button.id == "show-saved-reflection":
            self.show_saved_reflection()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "reflect-period":
            self.generate_current_reflection()

    def generate_current_reflection(self) -> None:
        period = self.query_one("#reflect-period", Input).value
        try:
            period_start, period_end = reflection_window(period)
        except ValueError as error:
            self.query_one("#reflection-status", Static).update(str(error))
            return

        entries = list_entries_between(
            self.db_path,
            period_start=period_start,
            period_end=period_end,
        )
        self.current_reflection = generate_reflection(
            entries,
            period_type=period,
            period_start=period_start,
            period_end=period_end,
        )
        self.query_one("#reflection-preview", Static).update(
            format_reflection(self.current_reflection)
        )
        self.query_one("#save-reflection", Button).disabled = False
        self.query_one("#reflection-status", Static).update("Reflection generated.")

    def save_current_reflection(self) -> None:
        draft = self.current_reflection
        if draft is None:
            self.generate_current_reflection()
            draft = self.current_reflection
            if draft is None:
                return

        existing = saved_reflection_for_window(
            list_reflections(self.db_path, limit=1000),
            period_type=draft.period_type,
            period_start=draft.period_start,
            period_end=draft.period_end,
        )
        if existing is not None:
            self.query_one("#reflection-status", Static).update(
                f"Reflection window already saved as #{existing.id}."
            )
            self.current_reflection = None
            self.query_one("#save-reflection", Button).disabled = True
            return

        reflection_id = add_reflection(
            self.db_path,
            period_type=draft.period_type,
            period_start=draft.period_start,
            period_end=draft.period_end,
            summary=draft.summary,
            wins=draft.wins,
            patterns=draft.patterns,
            suggestions=draft.suggestions,
        )
        self.query_one("#reflection-status", Static).update(
            f"Saved reflection #{reflection_id}."
        )
        self.current_reflection = None
        self.query_one("#save-reflection", Button).disabled = True

    def show_reflection_queue(self) -> None:
        queue = build_reflection_queue(
            entries=list_entries(self.db_path, limit=1000),
            reflections=list_reflections(self.db_path, limit=1000),
        )
        self.query_one("#reflection-preview", Static).update(format_reflection_queue(queue))
        status = "Loaded reflection queue."
        if queue.items:
            self.query_one("#reflect-period", Input).value = queue.items[0].period_type
            status = f"{status} Period set to {queue.items[0].period_type}."
        self.query_one("#reflection-status", Static).update(status)

    def generate_due_reflection(self) -> None:
        queue = build_reflection_queue(
            entries=list_entries(self.db_path, limit=1000),
            reflections=list_reflections(self.db_path, limit=1000),
        )
        next_item = first_reflection_queue_item(queue)
        if next_item is None:
            self.query_one("#reflection-preview", Static).update(
                format_reflection_queue(queue)
            )
            self.query_one("#reflection-status", Static).update(
                "No reflection windows need attention right now."
            )
            return

        self.query_one("#reflect-period", Input).value = next_item.period_type
        self.generate_current_reflection()
        self.query_one("#reflection-status", Static).update(
            f"Generated first due reflection: {next_item.period_type}."
        )

    def compare_current_reflection(self) -> None:
        period = self.query_one("#reflect-period", Input).value
        try:
            period_start, period_end = reflection_window(period)
        except ValueError as error:
            self.query_one("#reflection-status", Static).update(str(error))
            return

        comparison = build_reflection_comparison(
            entries=list_entries_between(
                self.db_path,
                period_start=period_start,
                period_end=period_end,
            ),
            reflections=list_reflections(self.db_path, limit=1000),
            period_type=period,
            period_start=period_start,
            period_end=period_end,
        )
        self.query_one("#reflection-preview", Static).update(
            format_reflection_comparison(comparison)
        )
        self.query_one("#reflection-status", Static).update("Reflection comparison loaded.")

    def show_reflection_trends(self) -> None:
        raw_period = self.query_one("#reflect-period", Input).value.strip()
        period = raw_period or None
        tags = parse_comma_values(self.query_one("#reflection-trend-tags", Input).value)
        memory_types = parse_comma_values(
            self.query_one("#reflection-trend-types", Input).value
        )
        scoped_entries = list_entries(self.db_path, limit=10000) if tags or memory_types else None
        trend = build_reflection_trend(
            list_reflections(self.db_path, limit=1000),
            period_type=period,
            entries=scoped_entries,
            tags=tags,
            memory_types=memory_types,
        )
        self.query_one("#reflection-preview", Static).update(format_reflection_trend(trend))
        self.query_one("#reflection-status", Static).update("Reflection trends loaded.")

    def show_reflection_history(self) -> None:
        reflections = list_reflections(self.db_path, limit=10)
        if not reflections:
            self.query_one("#reflection-preview", Static).update("No saved reflections yet.")
            self.query_one("#reflection-status", Static).update("")
            return

        lines = ["Saved Reflections"]
        for reflection in reflections:
            lines.append(
                
                    f"#{reflection.id} {reflection.period_type} "
                    f"({reflection.period_start} to {reflection.period_end})"
                
            )
            lines.append(f"  {reflection.summary}")
        self.query_one("#reflection-preview", Static).update("\n".join(lines))
        self.query_one("#reflection-status", Static).update("Saved reflection history loaded.")

    def show_saved_reflection(self) -> None:
        raw_id = self.query_one("#saved-reflection-id", Input).value.strip()
        if not raw_id:
            self.query_one("#reflection-status", Static).update("Enter a saved reflection ID.")
            return
        try:
            reflection_id = int(raw_id)
        except ValueError:
            self.query_one("#reflection-status", Static).update(
                "Saved reflection ID must be a number."
            )
            return

        reflection = get_reflection(self.db_path, reflection_id)
        if reflection is None:
            self.query_one("#reflection-status", Static).update(
                f"Reflection #{reflection_id} was not found."
            )
            return

        self.query_one("#reflection-preview", Static).update(format_saved_reflection(reflection))
        self.query_one("#reflection-status", Static).update(f"Showing reflection #{reflection_id}.")


class DecisionsScreen(WaymarkScreen):
    """Decision tracking view."""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="shell"):
            yield Static("Decisions", classes="screen-title")
            yield Static("Track choices, options, confidence, and review dates.", classes="subtle")
            yield Static("", id="decision-status", classes="note")
            with Horizontal(id="decision-grid"):
                with Vertical(classes="panel decision-panel", id="decision-add-panel"):
                    yield Static("Title", classes="label")
                    yield Input(
                        placeholder="Should I build CLI first or desktop first?",
                        id="decision-title",
                    )
                    yield Static("Context", classes="label")
                    yield TextArea(
                        "",
                        id="decision-context",
                        show_line_numbers=False,
                        placeholder="What makes this decision important?",
                    )
                    yield Static("Options", classes="label")
                    yield Input(placeholder="CLI first, desktop first", id="decision-options")
                    yield Static("Linked memory IDs", classes="label")
                    yield Input(placeholder="1, 2, 3", id="decision-memory-ids")
                    yield Static("Confidence", classes="label")
                    yield Input(placeholder="1-5", id="decision-confidence")
                    yield Static("Review date", classes="label")
                    yield Input(placeholder="2026-06-12", id="decision-review")
                    yield Button("Add Decision", id="add-decision", variant="primary")
                with Vertical(classes="panel decision-panel", id="decision-update-panel"):
                    yield Static("Update existing", classes="label")
                    yield Input(placeholder="Decision ID", id="decision-update-id")
                    yield Input(placeholder="Memory ID", id="decision-link-entry-id")
                    yield Button("Link Memory", id="link-decision-memory")
                    yield Input(placeholder="Final choice", id="decision-final-choice")
                    yield Button("Finalize Decision", id="finalize-decision")
                    yield TextArea(
                        "",
                        id="decision-outcome",
                        show_line_numbers=False,
                        placeholder="Outcome after review",
                    )
                    yield Button("Record Outcome", id="record-outcome")
                    yield Button("Review Queue", id="decision-review-queue")
                with VerticalScroll(id="decision-list"):
                    yield Static("No decisions loaded yet.")
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one("#decision-title", Input).focus()
        await self.refresh_decisions()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-decision":
            await self.add_decision_from_form()
        elif event.button.id == "link-decision-memory":
            await self.link_memory_from_form()
        elif event.button.id == "finalize-decision":
            await self.finalize_decision_from_form()
        elif event.button.id == "record-outcome":
            await self.record_outcome_from_form()
        elif event.button.id == "decision-review-queue":
            await self.show_review_queue()

    async def add_decision_from_form(self) -> None:
        title = self.query_one("#decision-title", Input).value.strip()
        context = self.query_one("#decision-context", TextArea).text.strip()
        if not title or not context:
            self.query_one("#decision-status", Static).update("Title and context are required.")
            return

        raw_options = self.query_one("#decision-options", Input).value
        options = [option.strip() for option in raw_options.split(",") if option.strip()]
        confidence = self.parse_confidence(self.query_one("#decision-confidence", Input).value)
        review_date = self.query_one("#decision-review", Input).value.strip() or None

        decision_id = add_decision(
            self.db_path,
            title=title,
            context=context,
            options=options,
            confidence=confidence,
            review_date=review_date,
        )
        linked, skipped = self.link_memory_ids(decision_id, self.parse_memory_ids())
        status = f"Saved decision #{decision_id}: {title}"
        if linked:
            status += f"\nLinked memories: {format_memory_refs(tuple(linked))}"
        if skipped:
            status += f"\nSkipped missing memories: {format_memory_refs(tuple(skipped))}"
        self.query_one("#decision-status", Static).update(status)
        self.clear_form()
        await self.refresh_decisions()

    async def link_memory_from_form(self) -> None:
        decision_id = self.parse_decision_id()
        raw_entry_id = self.query_one("#decision-link-entry-id", Input).value.strip()
        if decision_id is None or not raw_entry_id:
            self.query_one("#decision-status", Static).update(
                "Decision ID and memory ID are required."
            )
            return
        try:
            entry_id = int(raw_entry_id)
        except ValueError:
            self.query_one("#decision-status", Static).update("Memory ID must be a number.")
            return

        linked = link_decision_entry(self.db_path, decision_id=decision_id, entry_id=entry_id)
        if not linked:
            self.query_one("#decision-status", Static).update(
                f"Decision #{decision_id} or memory #{entry_id} was not found."
            )
            return

        self.query_one("#decision-status", Static).update(
            f"Linked decision #{decision_id} to memory #{entry_id}."
        )
        await self.refresh_decisions()

    async def finalize_decision_from_form(self) -> None:
        decision_id = self.parse_decision_id()
        final_choice = self.query_one("#decision-final-choice", Input).value.strip()
        if decision_id is None or not final_choice:
            self.query_one("#decision-status", Static).update(
                "Decision ID and final choice are required."
            )
            return

        confidence = self.parse_confidence(self.query_one("#decision-confidence", Input).value)
        updated = finalize_decision(
            self.db_path,
            decision_id=decision_id,
            final_choice=final_choice,
            confidence=confidence,
        )
        if not updated:
            self.query_one("#decision-status", Static).update(f"Decision #{decision_id} not found.")
            return

        self.query_one("#decision-status", Static).update(
            f"Finalized decision #{decision_id}: {final_choice}"
        )
        await self.refresh_decisions()

    async def record_outcome_from_form(self) -> None:
        decision_id = self.parse_decision_id()
        outcome = self.query_one("#decision-outcome", TextArea).text.strip()
        if decision_id is None or not outcome:
            self.query_one("#decision-status", Static).update(
                "Decision ID and outcome are required."
            )
            return

        updated = record_decision_outcome(self.db_path, decision_id=decision_id, outcome=outcome)
        if not updated:
            self.query_one("#decision-status", Static).update(f"Decision #{decision_id} not found.")
            return

        self.query_one("#decision-status", Static).update(
            f"Recorded outcome for decision #{decision_id}."
        )
        await self.refresh_decisions()

    async def show_review_queue(self) -> None:
        decision_list = self.query_one("#decision-list", VerticalScroll)
        await decision_list.remove_children()
        queue = build_decision_review_queue(list_decisions(self.db_path, limit=100))
        await decision_list.mount(
            Static(format_decision_review_queue(queue), classes="memory-card")
        )
        self.query_one("#decision-status", Static).update("Loaded decision review queue.")

    def parse_confidence(self, raw_value: str) -> int | None:
        if not raw_value.strip():
            return None
        try:
            confidence = int(raw_value)
        except ValueError:
            return None
        if confidence < 1 or confidence > 5:
            return None
        return confidence

    def parse_decision_id(self) -> int | None:
        raw_value = self.query_one("#decision-update-id", Input).value.strip()
        if not raw_value:
            return None
        try:
            return int(raw_value)
        except ValueError:
            return None

    def parse_memory_ids(self) -> list[int]:
        raw_value = self.query_one("#decision-memory-ids", Input).value
        memory_ids: list[int] = []
        for part in raw_value.split(","):
            stripped = part.strip()
            if not stripped:
                continue
            try:
                memory_ids.append(int(stripped))
            except ValueError:
                continue
        return memory_ids

    def link_memory_ids(
        self,
        decision_id: int,
        memory_ids: list[int],
    ) -> tuple[list[int], list[int]]:
        linked: list[int] = []
        skipped: list[int] = []
        for entry_id in memory_ids:
            if link_decision_entry(self.db_path, decision_id=decision_id, entry_id=entry_id):
                linked.append(entry_id)
            else:
                skipped.append(entry_id)
        return linked, skipped

    def clear_form(self) -> None:
        self.query_one("#decision-title", Input).value = ""
        self.query_one("#decision-context", TextArea).text = ""
        self.query_one("#decision-options", Input).value = ""
        self.query_one("#decision-memory-ids", Input).value = ""
        self.query_one("#decision-confidence", Input).value = ""
        self.query_one("#decision-review", Input).value = ""

    async def refresh_decisions(self) -> None:
        decision_list = self.query_one("#decision-list", VerticalScroll)
        await decision_list.remove_children()
        decisions = list_decisions(self.db_path, limit=20)
        if not decisions:
            await decision_list.mount(Static("No open decisions yet."))
            return

        for decision in decisions:
            await decision_list.mount(Static(format_decision(decision), classes="memory-card"))


class ImportScreen(WaymarkScreen):
    """Explicit import view."""

    def __init__(self, db_path: Path) -> None:
        super().__init__(db_path)
        self.current_folder_preview: MarkdownFolderPreview | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="shell"):
            yield Static("Import My World", classes="screen-title")
            yield Static(
                "Import one Markdown, text, PDF, or Word file, or preview one explicit "
                "folder before applying.",
                classes="subtle",
            )
            with Horizontal(id="import-controls"):
                yield Input(
                    placeholder="C:\\path\\to\\note.md, .txt, .pdf, .docx, or folder",
                    id="import-path",
                )
                yield Button("Import Markdown", id="import-markdown", variant="primary")
                yield Button("Import Text", id="import-text")
            with Horizontal(id="import-file-buttons"):
                yield Button("Import PDF", id="import-pdf")
                yield Button("Import DOCX", id="import-docx")
            with Horizontal(id="import-folder-options"):
                yield Input(value="25", placeholder="limit", id="import-limit")
                yield Input(value="no", placeholder="recursive? yes/no", id="import-recursive")
                yield Button("Preview Folder", id="preview-folder")
                yield Button("Apply Preview", id="apply-folder", variant="success", disabled=True)
            yield Static(
                "Choose a .md, .markdown, .txt, .text, .pdf, .docx, or folder path.",
                id="import-status",
            )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#import-path", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "import-markdown":
            self.import_markdown_from_form()
        elif event.button.id == "import-text":
            self.import_text_from_form()
        elif event.button.id == "import-pdf":
            self.import_pdf_from_form()
        elif event.button.id == "import-docx":
            self.import_docx_from_form()
        elif event.button.id == "preview-folder":
            self.preview_folder_from_form()
        elif event.button.id == "apply-folder":
            self.apply_folder_preview()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "import-path":
            self.import_markdown_from_form()

    def import_markdown_from_form(self) -> None:
        raw_path = self.query_one("#import-path", Input).value.strip()
        if not raw_path:
            self.query_one("#import-status", Static).update("Enter one Markdown file path.")
            return

        try:
            result = import_markdown_file(self.db_path, Path(raw_path))
        except (FileNotFoundError, ValueError, UnicodeDecodeError) as error:
            self.query_one("#import-status", Static).update(str(error))
            return

        self.query_one("#import-status", Static).update(
            f"Imported #{result.entry_id}: {result.title}\n"
            f"Source #{result.source_id}\n\n{result.summary}"
        )
        self.query_one("#import-path", Input).value = ""
        self.clear_folder_preview()

    def import_text_from_form(self) -> None:
        raw_path = self.query_one("#import-path", Input).value.strip()
        if not raw_path:
            self.query_one("#import-status", Static).update("Enter one text file path.")
            return

        try:
            result = import_text_file(self.db_path, Path(raw_path))
        except (
            DuplicateTextImportError,
            FileNotFoundError,
            ValueError,
            UnicodeDecodeError,
        ) as error:
            self.query_one("#import-status", Static).update(str(error))
            return

        self.query_one("#import-status", Static).update(
            f"Imported #{result.entry_id}: {result.title}\n"
            f"Source #{result.source_id}\n\n{result.summary}"
        )
        self.query_one("#import-path", Input).value = ""
        self.clear_folder_preview()

    def import_pdf_from_form(self) -> None:
        raw_path = self.query_one("#import-path", Input).value.strip()
        if not raw_path:
            self.query_one("#import-status", Static).update("Enter one PDF file path.")
            return

        try:
            result = import_pdf_file(self.db_path, Path(raw_path))
        except (
            DuplicatePdfImportError,
            MissingImportDependencyError,
            FileNotFoundError,
            ValueError,
            UnicodeDecodeError,
        ) as error:
            self.query_one("#import-status", Static).update(str(error))
            return

        self.query_one("#import-status", Static).update(
            f"Imported #{result.entry_id}: {result.title}\n"
            f"Source #{result.source_id}\n\n{result.summary}"
        )
        self.query_one("#import-path", Input).value = ""
        self.clear_folder_preview()

    def import_docx_from_form(self) -> None:
        raw_path = self.query_one("#import-path", Input).value.strip()
        if not raw_path:
            self.query_one("#import-status", Static).update("Enter one DOCX file path.")
            return

        try:
            result = import_docx_file(self.db_path, Path(raw_path))
        except (
            DuplicateDocxImportError,
            FileNotFoundError,
            ValueError,
            UnicodeDecodeError,
        ) as error:
            self.query_one("#import-status", Static).update(str(error))
            return

        self.query_one("#import-status", Static).update(
            f"Imported #{result.entry_id}: {result.title}\n"
            f"Source #{result.source_id}\n\n{result.summary}"
        )
        self.query_one("#import-path", Input).value = ""
        self.clear_folder_preview()

    def preview_folder_from_form(self) -> None:
        raw_path = self.query_one("#import-path", Input).value.strip()
        if not raw_path:
            self.query_one("#import-status", Static).update("Enter one folder path.")
            return

        limit = self.parse_folder_limit()
        recursive = self.parse_recursive_flag()
        if limit is None or recursive is None:
            return

        try:
            preview = preview_markdown_folder(Path(raw_path), recursive=recursive, limit=limit)
        except (FileNotFoundError, OSError, ValueError, UnicodeDecodeError) as error:
            self.query_one("#import-status", Static).update(str(error))
            self.clear_folder_preview()
            return

        self.current_folder_preview = preview
        self.query_one("#apply-folder", Button).disabled = not preview.files
        self.query_one("#import-status", Static).update(self.format_folder_preview(preview))

    def apply_folder_preview(self) -> None:
        preview = self.current_folder_preview
        if preview is None:
            self.query_one("#import-status", Static).update("Preview a folder before applying.")
            return
        if not preview.files:
            self.query_one("#import-status", Static).update(
                "No previewed Markdown files to import."
            )
            return

        imported = []
        skipped = []
        for preview_item in preview.files:
            try:
                imported.append(import_markdown_preview(self.db_path, preview_item))
            except DuplicateMarkdownImportError as error:
                skipped.append(str(error))
            except (FileNotFoundError, OSError, ValueError, UnicodeDecodeError) as error:
                self.query_one("#import-status", Static).update(str(error))
                return

        lines = [f"Imported {len(imported)} Markdown file(s)."]
        lines.extend(
            f"#{result.entry_id} {result.title} (source #{result.source_id})"
            for result in imported
        )
        if skipped:
            lines.append("")
            lines.append("Skipped")
            lines.extend(f"- {item}" for item in skipped)
        self.query_one("#import-status", Static).update("\n".join(lines))
        self.clear_folder_preview()

    def clear_folder_preview(self) -> None:
        self.current_folder_preview = None
        self.query_one("#apply-folder", Button).disabled = True

    def parse_folder_limit(self) -> int | None:
        raw_limit = self.query_one("#import-limit", Input).value.strip()
        try:
            limit = int(raw_limit)
        except ValueError:
            self.query_one("#import-status", Static).update("Folder limit must be a number.")
            return None
        if limit < 1 or limit > 500:
            self.query_one("#import-status", Static).update("Folder limit must be 1-500.")
            return None
        return limit

    def parse_recursive_flag(self) -> bool | None:
        raw_flag = self.query_one("#import-recursive", Input).value.strip().lower()
        if raw_flag in {"", "0", "false", "n", "no", "top", "top-level"}:
            return False
        if raw_flag in {"1", "recursive", "true", "y", "yes"}:
            return True
        self.query_one("#import-status", Static).update("Recursive must be yes or no.")
        return None

    def format_folder_preview(self, preview: MarkdownFolderPreview) -> str:
        mode = "recursive" if preview.recursive else "top-level only"
        lines = [
            f"Folder preview: {preview.root}",
            f"Mode: {mode}",
            "",
        ]
        if preview.files:
            lines.append("Files")
            for index, preview_item in enumerate(preview.files, start=1):
                relative_path = preview_item.path.relative_to(preview.root).as_posix()
                lines.append(f"{index}. {relative_path} - {preview_item.title}")
                lines.append(f"   {preview_item.summary}")
        else:
            lines.append("No Markdown files found.")

        if preview.truncated:
            lines.append("")
            lines.append("Preview stopped at the current limit.")
        if preview.skipped:
            lines.append("")
            lines.append("Skipped")
            lines.extend(f"- {skipped}" for skipped in preview.skipped)
        lines.append("")
        lines.append("Nothing imported yet. Apply Preview to save these files.")
        return "\n".join(lines)


class ExportScreen(WaymarkScreen):
    """Explicit Markdown export view."""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="shell"):
            yield Static("Export Markdown", classes="screen-title")
            yield Static(
                "Write Markdown to one explicit output path. Existing files need overwrite=yes.",
                classes="subtle",
            )
            with Horizontal(id="export-path-row"):
                yield Input(placeholder="C:\\path\\to\\waymark-export.md", id="export-path")
                yield Input(value="no", placeholder="overwrite? yes/no", id="export-force")
            with Horizontal(id="export-action-row"):
                yield Input(placeholder="Memory ID", id="export-memory-id")
                yield Button("Export Memory", id="export-memory", variant="primary")
                yield Input(value="20", placeholder="timeline limit", id="export-timeline-limit")
                yield Button("Export Timeline", id="export-timeline")
            with Horizontal(id="export-reflection-row"):
                yield Input(placeholder="Reflection ID", id="export-reflection-id")
                yield Button("Export Reflection", id="export-reflection")
                yield Input(value="week", placeholder="trend period", id="export-trend-period")
                yield Button("Export Reflection Trends", id="export-reflection-trends")
            with Horizontal(id="export-trend-scope-row"):
                yield Input(placeholder="Trend tags", id="export-trend-tags")
                yield Input(placeholder="Trend types", id="export-trend-types")
            yield Static(
                "Choose an output path, then export selected Markdown.",
                id="export-status",
            )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#export-path", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "export-memory":
            self.export_memory_from_form()
        elif event.button.id == "export-timeline":
            self.export_timeline_from_form()
        elif event.button.id == "export-reflection":
            self.export_reflection_from_form()
        elif event.button.id == "export-reflection-trends":
            self.export_reflection_trends_from_form()

    def export_memory_from_form(self) -> None:
        output_path = self.parse_output_path()
        force = self.parse_force()
        entry_id = self.parse_entry_id()
        if output_path is None or force is None or entry_id is None:
            return

        entry = get_entry(self.db_path, entry_id)
        if entry is None:
            self.query_one("#export-status", Static).update(f"Memory #{entry_id} was not found.")
            return

        try:
            exported_path = write_markdown_export(
                output_path,
                format_entry_markdown(self.db_path, entry),
                force=force,
            )
        except (FileExistsError, OSError, ValueError) as error:
            self.query_one("#export-status", Static).update(str(error))
            return

        self.query_one("#export-status", Static).update(
            f"Exported memory #{entry.id}: {entry.title}\n{exported_path}"
        )

    def export_timeline_from_form(self) -> None:
        output_path = self.parse_output_path()
        force = self.parse_force()
        limit = self.parse_timeline_limit()
        if output_path is None or force is None or limit is None:
            return

        entries = list_entries(self.db_path, limit=limit)
        if not entries:
            self.query_one("#export-status", Static).update("No memories to export yet.")
            return

        try:
            exported_path = write_markdown_export(
                output_path,
                format_timeline_markdown(self.db_path, entries),
                force=force,
            )
        except (FileExistsError, OSError, ValueError) as error:
            self.query_one("#export-status", Static).update(str(error))
            return

        self.query_one("#export-status", Static).update(
            f"Exported {len(entries)} memories.\n{exported_path}"
        )

    def export_reflection_from_form(self) -> None:
        output_path = self.parse_output_path()
        force = self.parse_force()
        reflection_id = self.parse_reflection_id()
        if output_path is None or force is None or reflection_id is None:
            return

        reflection = get_reflection(self.db_path, reflection_id)
        if reflection is None:
            self.query_one("#export-status", Static).update(
                f"Reflection #{reflection_id} was not found."
            )
            return

        try:
            exported_path = write_markdown_export(
                output_path,
                format_reflection_markdown(reflection),
                force=force,
            )
        except (FileExistsError, OSError, ValueError) as error:
            self.query_one("#export-status", Static).update(str(error))
            return

        self.query_one("#export-status", Static).update(
            f"Exported reflection #{reflection.id}.\n{exported_path}"
        )

    def export_reflection_trends_from_form(self) -> None:
        output_path = self.parse_output_path()
        force = self.parse_force()
        if output_path is None or force is None:
            return

        tags = parse_comma_values(self.query_one("#export-trend-tags", Input).value)
        memory_types = parse_comma_values(self.query_one("#export-trend-types", Input).value)
        scoped_entries = list_entries(self.db_path, limit=10000) if tags or memory_types else None
        period = self.query_one("#export-trend-period", Input).value.strip() or None
        trend = build_reflection_trend(
            list_reflections(self.db_path, limit=1000),
            period_type=period,
            entries=scoped_entries,
            tags=tags,
            memory_types=memory_types,
        )

        try:
            exported_path = write_markdown_export(
                output_path,
                format_reflection_trend_markdown(trend),
                force=force,
            )
        except (FileExistsError, OSError, ValueError) as error:
            self.query_one("#export-status", Static).update(str(error))
            return

        self.query_one("#export-status", Static).update(
            f"Exported reflection trends.\n{exported_path}"
        )

    def parse_output_path(self) -> Path | None:
        raw_path = self.query_one("#export-path", Input).value.strip()
        if not raw_path:
            self.query_one("#export-status", Static).update("Enter an output Markdown path.")
            return None
        return Path(raw_path)

    def parse_entry_id(self) -> int | None:
        raw_value = self.query_one("#export-memory-id", Input).value.strip()
        if not raw_value:
            self.query_one("#export-status", Static).update("Enter a memory ID.")
            return None
        try:
            return int(raw_value)
        except ValueError:
            self.query_one("#export-status", Static).update("Memory ID must be a number.")
            return None

    def parse_reflection_id(self) -> int | None:
        raw_value = self.query_one("#export-reflection-id", Input).value.strip()
        if not raw_value:
            self.query_one("#export-status", Static).update("Enter a reflection ID.")
            return None
        try:
            return int(raw_value)
        except ValueError:
            self.query_one("#export-status", Static).update("Reflection ID must be a number.")
            return None

    def parse_timeline_limit(self) -> int | None:
        raw_value = self.query_one("#export-timeline-limit", Input).value.strip()
        try:
            limit = int(raw_value)
        except ValueError:
            self.query_one("#export-status", Static).update("Timeline limit must be a number.")
            return None
        if limit < 1 or limit > 500:
            self.query_one("#export-status", Static).update("Timeline limit must be 1-500.")
            return None
        return limit

    def parse_force(self) -> bool | None:
        raw_flag = self.query_one("#export-force", Input).value.strip().lower()
        if raw_flag in {"", "0", "false", "n", "no"}:
            return False
        if raw_flag in {"1", "force", "overwrite", "true", "y", "yes"}:
            return True
        self.query_one("#export-status", Static).update("Overwrite must be yes or no.")
        return None


class DoctorScreen(WaymarkScreen):
    """In-app setup summary."""

    def compose(self) -> ComposeResult:
        profile = collect_system_profile(self.db_path.parent)
        recommendation = profile.recommendation
        config = read_config(config_path())
        runtime_status = get_ollama_status()
        model_plan = build_model_setup_plan(profile, runtime_status)
        yield Header(show_clock=True)
        with Container(id="shell"):
            yield Static("Doctor", classes="screen-title")
            yield Static(
                (
                    f"Config: {'configured' if config else 'not set'}\n"
                    f"Path: {config_path()}"
                ),
                classes="memory-card",
            )
            yield Static(f"Recommended mode: {recommendation.mode}", classes="memory-card")
            yield Static(
                (
                    f"Ollama: {'detected' if runtime_status.available else 'not found'}\n"
                    f"Installed models: {len(runtime_status.models)}"
                ),
                classes="memory-card",
            )
            yield Static(
                (
                    f"OS: {profile.os_name} {profile.machine}\n"
                    f"CPU cores: {profile.cpu_count or 'unknown'}\n"
                    f"Memory: {profile.total_ram_gb or 'unknown'} GB\n"
                    f"Disk free: {profile.disk_free_gb:.1f} GB"
                ),
                classes="memory-card",
            )
            with Horizontal(id="doctor-actions"):
                yield Button("Save Safe Config", id="save-config", variant="primary")
            yield Static(
                format_model_setup_plan(model_plan),
                id="doctor-model-setup",
                classes="memory-card",
            )
            yield Static(f"Database: {self.db_path}", classes="memory-card")
            yield Static("No config saved this session.", id="doctor-status", classes="note")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-config":
            profile = collect_system_profile(self.db_path.parent)
            write_config(config_path(), build_recommended_config(profile))
            self.query_one("#doctor-status", Static).update(f"Saved config: {config_path()}")


class WaymarkApp(App[None]):
    """Waymark Textual app."""

    CSS = """
    Screen {
        background: #14110e;
        color: #e8dcc6;
    }

    Header, Footer {
        background: #211c18;
        color: #e8dcc6;
    }

    #shell {
        padding: 2 4;
        width: 100%;
        height: 100%;
    }

    #brand {
        color: #f4c378;
        text-style: bold;
        text-align: center;
        margin-top: 1;
    }

    #tagline, .subtle, .note {
        color: #9a8d77;
    }

    #menu-panel {
        width: 60;
        align-horizontal: center;
        margin-top: 2;
    }

    Button {
        width: 100%;
        margin: 1 0;
    }

    .screen-title {
        color: #f4c378;
        text-style: bold;
        margin-bottom: 1;
    }

    .panel {
        border: solid #3a3128;
        padding: 1 2;
        margin: 1;
        width: 1fr;
        height: auto;
    }

    #capture-grid {
        height: 1fr;
    }

    #draft-panel {
        min-width: 36;
    }

    #draft-actions {
        height: 5;
    }

    #draft-actions Button {
        width: 12;
        margin: 1 1 0 0;
    }

    TextArea {
        height: 12;
        border: solid #3a3128;
    }

    Input {
        border: solid #3a3128;
        margin-bottom: 1;
    }

    .label {
        color: #e7ad5c;
        text-style: bold;
    }

    .memory-card {
        border: solid #3a3128;
        background: #1b1714;
        padding: 1 2;
        margin: 1 0;
    }

    #timeline-list {
        height: 1fr;
    }

    #memory-detail-controls {
        height: 5;
        margin: 1 0;
    }

    #memory-detail-controls Input {
        width: 24;
    }

    #memory-detail-controls Button {
        width: 18;
        margin: 0 1;
    }

    #memory-edit-fields {
        height: 4;
    }

    #memory-edit-fields Input {
        width: 1fr;
        margin: 0 1 0 0;
    }

    #memory-edit-summary {
        margin-bottom: 1;
    }

    #memory-edit-text {
        height: 7;
    }

    #memory-detail-status {
        height: 1fr;
    }

    #ask-row {
        height: 3;
        margin: 1 0;
    }

    #reflect-controls {
        height: 5;
        margin: 1 0;
    }

    #reflect-controls Input {
        width: 24;
    }

    #reflect-controls Button {
        width: 16;
        margin: 0 1;
    }

    #reflection-trend-scope {
        height: 3;
        margin: 0 0 1 0;
    }

    #reflection-trend-scope Input {
        width: 32;
        margin: 0 1 0 0;
    }

    #reflection-history-controls {
        height: 5;
        margin: 0 0 1 0;
    }

    #reflection-history-controls Input {
        width: 28;
    }

    #reflection-history-controls Button {
        width: 16;
        margin: 0 1;
    }

    #reflection-preview {
        border: solid #3a3128;
        background: #1b1714;
        padding: 1 2;
        height: 1fr;
    }

    #decision-grid {
        height: 1fr;
    }

    .decision-panel {
        width: 1fr;
    }

    .decision-panel Input {
        margin-bottom: 0;
    }

    #decision-context {
        height: 5;
    }

    #decision-outcome {
        height: 5;
    }

    #decision-list {
        width: 1fr;
        height: 1fr;
        margin: 1;
    }

    #import-controls {
        height: 5;
        margin: 1 0;
    }

    #import-controls Input {
        width: 1fr;
    }

    #import-controls Button {
        width: 22;
        margin: 0 1;
    }

    #import-file-buttons {
        height: 5;
        margin: 1 0;
    }

    #import-file-buttons Button {
        width: 22;
        margin: 0 1;
    }

    #import-folder-options {
        height: 5;
        margin: 1 0;
    }

    #import-folder-options Input {
        width: 18;
    }

    #import-folder-options Button {
        width: 18;
        margin: 0 1;
    }

    #import-status {
        border: solid #3a3128;
        background: #1b1714;
        padding: 1 2;
        height: 1fr;
    }

    #export-path-row {
        height: 5;
        margin: 1 0;
    }

    #export-path-row #export-path {
        width: 1fr;
    }

    #export-path-row #export-force {
        width: 24;
    }

    #export-action-row {
        height: 5;
        margin: 1 0;
    }

    #export-action-row Input {
        width: 18;
    }

    #export-action-row Button {
        width: 18;
        margin: 0 1;
    }

    #export-reflection-row {
        height: 5;
        margin: 1 0;
    }

    #export-reflection-row Input {
        width: 20;
    }

    #export-reflection-row Button {
        width: 26;
        margin: 0 1;
    }

    #export-trend-scope-row {
        height: 3;
        margin: 0 0 1 0;
    }

    #export-trend-scope-row Input {
        width: 32;
        margin: 0 1 0 0;
    }

    #export-status {
        border: solid #3a3128;
        background: #1b1714;
        padding: 1 2;
        height: 1fr;
    }

    #doctor-actions {
        height: 5;
        margin: 1 0;
    }

    #doctor-actions Button {
        width: 24;
    }
    """

    TITLE = "Waymark"

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self.db_path = db_path or database_path()

    async def on_mount(self) -> None:
        init_database(self.db_path)
        await self.push_screen(MainMenuScreen(self.db_path))


def run_tui(db_path: Path | None = None) -> None:
    WaymarkApp(db_path=db_path).run()
