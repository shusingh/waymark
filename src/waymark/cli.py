"""Command line interface for Waymark."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from waymark import __version__
from waymark.ai import LocalAiError, embed_text_with_ollama, structure_memory_with_ollama
from waymark.backup import (
    BACKUP_TABLES,
    BackupError,
    read_backup,
    restore_backup,
    write_backup,
    write_portable_bundle,
)
from waymark.config import build_recommended_config, read_config, write_config
from waymark.diagnostics import collect_database_health, format_database_health
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
    MissingImportDependencyError,
    import_docx_file,
    import_folder,
    import_markdown_file,
    import_markdown_folder,
    import_pdf_file,
    import_text_file,
    preview_docx_file,
    preview_import_folder,
    preview_markdown_folder,
    preview_pdf_file,
)
from waymark.journey import (
    JourneyMap,
    build_decision_review_queue,
    build_journey_map,
    format_decision_review_queue,
    format_journey_map,
)
from waymark.memory import MemoryDraft
from waymark.model_setup import ModelSetupPlan, build_model_setup_plan, is_model_installed
from waymark.paths import config_path, database_path, ensure_waymark_home
from waymark.reflection import (
    ReflectionQueue,
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
from waymark.runtime import ModelRuntimeStatus, get_ollama_status
from waymark.storage import (
    Decision,
    Entry,
    add_decision,
    add_entry,
    add_reflection,
    count_entries_missing_embeddings,
    count_entry_embeddings,
    finalize_decision,
    get_decision,
    get_entry,
    get_reflection,
    get_source,
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
    unlink_decision_entry,
    update_entry,
    upsert_entry_embedding,
)
from waymark.system import SystemProfile, collect_system_profile
from waymark.today import build_today_brief, format_today_brief, parse_today_date
from waymark.tui import run_tui

console = Console()
app = typer.Typer(
    help="Waymark: your private memory trail, searchable from the terminal.",
    no_args_is_help=False,
)
journey_app = typer.Typer(help="Inspect journey map signals and capture prompts.")
decision_app = typer.Typer(help="Track decisions and review judgment over time.")
setup_app = typer.Typer(help="Preview and save first-run setup recommendations.")
models_app = typer.Typer(help="Inspect local model runtime state without downloads.")
import_app = typer.Typer(help="Import explicit user-selected files.")
sources_app = typer.Typer(help="Inspect imported source metadata.")
export_app = typer.Typer(help="Export memories and reflections to explicit Markdown files.")
reflections_app = typer.Typer(help="Inspect saved reflections.")
memory_app = typer.Typer(help="Inspect saved memories.")
embeddings_app = typer.Typer(help="Build explicit local embedding indexes.")
backup_app = typer.Typer(help="Create and restore full local backups of your Waymark home.")
app.add_typer(journey_app, name="journey")
app.add_typer(decision_app, name="decision")
app.add_typer(setup_app, name="setup")
app.add_typer(models_app, name="models")
app.add_typer(import_app, name="import")
app.add_typer(sources_app, name="sources")
app.add_typer(export_app, name="export")
app.add_typer(reflections_app, name="reflections")
app.add_typer(memory_app, name="memory")
app.add_typer(embeddings_app, name="embeddings")
app.add_typer(backup_app, name="backup")


def show_main_menu() -> None:
    console.print(
        Panel.fit(
            "\n".join(
                [
                    "[bold yellow3]Waymark[/bold yellow3]",
                    "Your private memory trail, searchable from the terminal.",
                    "",
                    "[1] Capture a Moment        [dim]waymark capture[/dim]",
                    "[2] Ask Waymark             [dim]waymark ask QUERY[/dim]",
                    "[3] Timeline                [dim]waymark timeline[/dim]",
                    "[4] Reflect                 [dim]waymark reflect[/dim]",
                    "[5] Decisions               [dim]waymark decision list[/dim]",
                    "[6] Import My World         [dim]waymark import markdown FILE[/dim]",
                    "[7] Export Markdown         [dim]waymark export timeline FILE[/dim]",
                    "[8] Journey Map             [dim]waymark journey[/dim]",
                    "[9] Setup / Doctor          [dim]waymark doctor[/dim]",
                    "",
                    "[dim]Decision review queue: waymark decision review[/dim]",
                    "",
                    "[dim]Use waymark tui to launch the guided Textual interface.[/dim]",
                ]
            ),
            title="Welcome",
            border_style="yellow3",
        )
    )


def format_gb(value: float | None) -> str:
    return f"{value:.1f} GB" if value is not None else "unknown"


def add_profile_rows(table: Table, profile: SystemProfile) -> None:
    table.add_row("OS", "ok", f"{profile.os_name} {profile.machine}")
    table.add_row("CPU", "ok", f"{profile.processor} ({profile.cpu_count or 'unknown'} cores)")
    table.add_row("Memory", "ok", format_gb(profile.total_ram_gb))
    table.add_row("Disk free", "ok", f"{profile.disk_free_gb:.1f} GB")
    table.add_row("Recommended mode", "ok", profile.recommendation.mode)


def add_runtime_rows(table: Table, status: ModelRuntimeStatus) -> None:
    table.add_row(
        "Ollama",
        "detected" if status.available else "optional",
        status.executable or "not found",
    )
    table.add_row("Installed models", "ok", str(len(status.models)))
    if status.error:
        table.add_row("Runtime note", "info", status.error)


def show_setup_preview(*, apply: bool) -> None:
    home = ensure_waymark_home()
    profile = collect_system_profile(home)
    recommendation = profile.recommendation
    recommended_config = build_recommended_config(profile)

    table = Table(title="Waymark Setup Preview", show_header=True, header_style="bold yellow3")
    table.add_column("Item")
    table.add_column("Value")
    table.add_row("OS", f"{profile.os_name} {profile.machine}")
    table.add_row("CPU cores", str(profile.cpu_count or "unknown"))
    table.add_row("Memory", format_gb(profile.total_ram_gb))
    table.add_row("Disk free", f"{profile.disk_free_gb:.1f} GB")
    table.add_row("Recommended mode", recommendation.mode)
    table.add_row("Chat model", recommendation.chat_model or "skip for now")
    table.add_row("Embedding model", recommendation.embedding_model or "skip for now")

    console.print(table)
    console.print(f"[dim]{recommendation.reason}[/dim]")
    console.print("[bold]No models were downloaded. No files were scanned.[/bold]")
    if apply:
        write_config(config_path(), recommended_config)
        console.print(f"[green]Wrote config:[/green] {config_path()}")
    else:
        console.print("[dim]Run waymark setup --apply to save these safe defaults.[/dim]")
        console.print("[dim]Run waymark setup models to inspect recommended local models.[/dim]")


def show_model_setup_plan(plan: ModelSetupPlan, *, apply: bool) -> None:
    table = Table(title="Waymark Model Setup", show_header=True, header_style="bold yellow3")
    table.add_column("Purpose")
    table.add_column("Model")
    table.add_column("Status")
    table.add_column("Manual command")

    if plan.items:
        for item in plan.items:
            table.add_row(
                item.purpose,
                item.model,
                "installed" if item.installed else "missing",
                "already present" if item.installed else item.command,
            )
    else:
        table.add_row("Local AI", "none", "app-only", "no model pull recommended")

    console.print(table)
    console.print(f"[dim]Recommended mode: {plan.mode}. {plan.reason}[/dim]")
    if not plan.runtime_available:
        console.print("[yellow]Ollama was not found on PATH.[/yellow]")
        if plan.runtime_error:
            console.print(f"[dim]{plan.runtime_error}[/dim]")
    elif plan.runtime_error:
        console.print(f"[yellow]{plan.runtime_error}[/yellow]")

    missing_items = [item for item in plan.items if not item.installed]
    if missing_items:
        console.print("[dim]Run the listed commands yourself when you want local AI models.[/dim]")
    console.print("[bold]No models were downloaded. No files were scanned.[/bold]")
    if apply:
        console.print(f"[green]Wrote config:[/green] {config_path()}")


def memory_refs(entry_ids: tuple[int, ...]) -> str:
    return ", ".join(f"#{entry_id}" for entry_id in entry_ids) if entry_ids else ""


def format_decision_detail(decision: Decision, linked_entries: list[Entry]) -> str:
    options = "\n".join(f"- {option}" for option in decision.options) or "- No options captured"
    confidence = f"{decision.confidence}/5" if decision.confidence else "not set"
    review = decision.review_date or "not set"
    final_choice = decision.final_choice or "not set"
    linked = "\n".join(
        f"- #{entry.id} {entry.title}: {entry.summary}" for entry in linked_entries
    )
    if not linked:
        linked = "- No linked memories yet"
    outcome = f"\n\nOutcome\n{decision.outcome}" if decision.outcome else ""
    return (
        f"#{decision.id}  {decision.status.upper()}  {decision.title}\n"
        f"{decision.context}\n\n"
        f"Options\n{options}\n\n"
        f"Linked Memories\n{linked}\n\n"
        f"Final choice: {final_choice}\n"
        f"Confidence: {confidence}  Review: {review}"
        f"{outcome}"
    )


def format_memory_detail(entry: Entry, linked_decisions: list[Decision]) -> str:
    tags = ", ".join(entry.tags) if entry.tags else "none"
    source_id = source_id_from_entry(entry)
    source_text = (
        source_label(get_source(database_path(), source_id)) if source_id else entry.source
    )
    decisions = "\n".join(
        f"- #{decision.id} {decision.status.upper()} {decision.title}"
        for decision in linked_decisions
    )
    if not decisions:
        decisions = "- No linked decisions yet"
    return (
        f"#{entry.id}  {entry.type.upper()}  {entry.title}\n"
        f"Created: {entry.created_at}\n"
        f"Tags: {tags}\n"
        f"Source: {source_text}\n\n"
        f"Summary\n{entry.summary}\n\n"
        f"Memory\n{entry.raw_text.strip()}\n\n"
        f"Linked Decisions\n{decisions}"
    )


def format_capture_draft(
    draft: MemoryDraft,
    *,
    draft_source: str,
    entry_id: int | None = None,
) -> str:
    tags = ", ".join(draft.tags) if draft.tags else "none"
    id_text = f"id: {entry_id} - " if entry_id is not None else ""
    return (
        f"[bold]{draft.title}[/bold]\n\n"
        f"{draft.summary}\n\n"
        f"[dim]{id_text}type: {draft.memory_type} - tags: {tags} - "
        f"draft: {draft_source}[/dim]"
    )


def embedding_text(entry: Entry) -> str:
    tags = ", ".join(entry.tags) if entry.tags else "none"
    return "\n".join(
        [
            f"Title: {entry.title}",
            f"Type: {entry.type}",
            f"Tags: {tags}",
            f"Summary: {entry.summary}",
            "",
            entry.raw_text.strip(),
        ]
    )


def configured_embedding_model() -> str | None:
    config = read_config(config_path())
    if config is None:
        return None
    if config.models.runtime != "ollama":
        return None
    return config.models.embedding_model


def embedding_runtime_note(model: str, status: ModelRuntimeStatus) -> str | None:
    if not status.available:
        return "Ollama was not found. Run waymark setup models for manual setup commands."
    if status.error:
        return f"Ollama model check failed: {status.error}"
    if not is_model_installed(model, status.models):
        return f"Configured embedding model {model} is not installed. Run: ollama pull {model}."
    return None


def source_text_for_entry(entry: Entry) -> str:
    source_id = source_id_from_entry(entry)
    return source_label(get_source(database_path(), source_id)) if source_id else entry.source


def render_entry_source(entry: Entry, *, title: str, border_style: str = "cyan") -> None:
    console.print(
        Panel(
            (
                f"[bold]{entry.title}[/bold]\n{entry.summary}\n\n"
                f"[dim]{entry.created_at} - {entry.type} - {source_text_for_entry(entry)}[/dim]"
            ),
            title=title,
            border_style=border_style,
        )
    )


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option("--version", help="Show the installed Waymark version."),
    ] = False,
    plain: Annotated[
        bool,
        typer.Option("--plain", help="Show the plain non-interactive menu."),
    ] = False,
) -> None:
    if version:
        console.print(f"waymark {__version__}")
        raise typer.Exit

    if ctx.invoked_subcommand is None:
        init_database(database_path())
        if plain:
            show_main_menu()
            return
        run_tui(database_path())


@app.command()
def tui() -> None:
    """Launch the guided terminal interface."""

    init_database(database_path())
    run_tui(database_path())


@app.command()
def doctor() -> None:
    """Check local Waymark setup and runtime availability."""

    home = ensure_waymark_home()
    db_path = database_path()
    init_database(db_path)
    profile = collect_system_profile(home)
    config = read_config(config_path())
    runtime_status = get_ollama_status()
    database_health = collect_database_health(db_path)

    table = Table(title="Waymark Doctor", show_header=True, header_style="bold yellow3")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Details")

    table.add_row("App", "ok", f"version {__version__}")
    table.add_row("Home", "ok", str(home))
    table.add_row("Database", "ok", str(db_path))
    table.add_row(
        "Database health",
        "ok" if database_health.ok else "needs attention",
        format_database_health(database_health),
    )
    table.add_row(
        "Config",
        "ok" if config else "not set",
        str(config_path()) if config else "run waymark setup --apply",
    )
    add_profile_rows(table, profile)
    add_runtime_rows(table, runtime_status)
    table.add_row("AI setup", "manual", "No models are downloaded without approval.")

    console.print(table)


@setup_app.callback(invoke_without_command=True)
def setup_main(
    ctx: typer.Context,
    apply: Annotated[
        bool,
        typer.Option(
            "--apply",
            help="Write the recommended local config without downloading models.",
        ),
    ] = False,
) -> None:
    """Preview first-run setup recommendations without downloading models."""

    if ctx.invoked_subcommand is not None:
        return

    show_setup_preview(apply=apply)


@setup_app.command("models")
def setup_models(
    apply: Annotated[
        bool,
        typer.Option(
            "--apply",
            help="Write the recommended local config while leaving model downloads manual.",
        ),
    ] = False,
) -> None:
    """Inspect recommended local models and exact manual pull commands."""

    home = ensure_waymark_home()
    profile = collect_system_profile(home)
    runtime_status = get_ollama_status()
    plan = build_model_setup_plan(profile, runtime_status)
    if apply:
        write_config(config_path(), build_recommended_config(profile))
    show_model_setup_plan(plan, apply=apply)


@app.command()
def capture(
    text: Annotated[
        str | None,
        typer.Argument(help="Memory text. If omitted, Waymark will prompt for it."),
    ] = None,
    memory_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Memory type such as daily, project, work, health."),
    ] = "daily",
    tag: Annotated[
        list[str] | None,
        typer.Option("--tag", help="Tag for this memory. Can be repeated."),
    ] = None,
    local_ai: Annotated[
        bool,
        typer.Option(
            "--local-ai",
            "--ai",
            help="Use the configured local Ollama chat model to draft memory fields.",
        ),
    ] = False,
    preview: Annotated[
        bool,
        typer.Option(
            "--preview",
            "--dry-run",
            help="Show the drafted memory card without saving it.",
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Save a local-AI draft without an interactive confirmation prompt.",
        ),
    ] = False,
) -> None:
    """Capture a manual memory in local SQLite storage."""

    raw_text = text or typer.prompt("Capture a moment")
    raw_text = raw_text.strip()

    if not raw_text:
        console.print("[red]Nothing to save.[/red]")
        raise typer.Exit(code=1)

    raw_tags = ",".join(tag or ())
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
    if draft_result.note:
        console.print(f"[yellow]{draft_result.note}[/yellow]")
        if local_ai and "config is missing" in draft_result.note:
            console.print("[dim]Run waymark setup --apply first.[/dim]")
    draft = draft_result.draft
    if preview:
        console.print(
            Panel(
                format_capture_draft(draft, draft_source=draft_result.source),
                title="Draft Memory",
                border_style="yellow3",
            )
        )
        console.print("[bold]No memory was saved.[/bold]")
        return

    if draft_result.source.startswith("local-ai:") and not yes:
        console.print(
            Panel(
                format_capture_draft(draft, draft_source=draft_result.source),
                title="Draft Memory",
                border_style="yellow3",
            )
        )
        if not typer.confirm("Save this local-AI draft?", default=False):
            console.print("[bold]No memory was saved.[/bold]")
            return

    init_database(database_path())
    entry_id = add_entry(
        database_path(),
        raw_text=draft.raw_text,
        memory_type=draft.memory_type,
        title=draft.title,
        summary=draft.summary,
        tags=draft.tags,
    )

    console.print(
        Panel(
            format_capture_draft(
                draft,
                draft_source=draft_result.source,
                entry_id=entry_id,
            ),
            title="Saved Memory",
            border_style="green",
        )
    )


@app.command()
def timeline(
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of memories to show.")] = 20,
) -> None:
    """Show recent memories in reverse chronological order."""

    init_database(database_path())
    entries = list_entries(database_path(), limit=limit)

    if not entries:
        console.print(
            '[dim]No memories yet. Try: waymark capture "Started shaping Waymark."[/dim]'
        )
        return

    table = Table(title="Timeline", show_header=True, header_style="bold yellow3")
    table.add_column("ID")
    table.add_column("When")
    table.add_column("Type")
    table.add_column("Title")
    table.add_column("Tags")

    for entry in entries:
        table.add_row(
            str(entry.id),
            entry.created_at,
            entry.type,
            entry.title,
            ", ".join(entry.tags),
        )

    console.print(table)


def current_journey_map() -> JourneyMap:
    init_database(database_path())
    return build_journey_map(
        entries=list_entries(database_path(), limit=1000),
        decisions=list_decisions(database_path(), limit=1000),
        reflections=list_reflections(database_path(), limit=1000),
    )


@journey_app.callback(invoke_without_command=True)
def journey_main(ctx: typer.Context) -> None:
    """Show an app-only memory health and journey map summary."""

    if ctx.invoked_subcommand is not None:
        return

    journey_map = current_journey_map()
    console.print(
        Panel(
            format_journey_map(journey_map),
            title="Journey Map",
            border_style="yellow3",
        )
    )


@journey_app.command("prompts")
def journey_prompts() -> None:
    """Show copyable capture commands for thin memory areas."""

    journey_map = current_journey_map()
    if not journey_map.capture_prompts:
        console.print("[green]No thin-area capture prompts right now.[/green]")
        return

    table = Table(title="Capture Prompts", show_header=True, header_style="bold yellow3")
    table.add_column("Area")
    table.add_column("Prompt")
    table.add_column("Command")
    for area, prompt in zip(
        journey_map.thin_memory_areas,
        journey_map.capture_prompts,
        strict=False,
    ):
        table.add_row(area, prompt, capture_prompt_command(area, prompt))
    console.print(table)
    console.print("[bold]Commands:[/bold]")
    for area, prompt in zip(
        journey_map.thin_memory_areas,
        journey_map.capture_prompts,
        strict=False,
    ):
        console.print(capture_prompt_command(area, prompt))


def capture_prompt_command(memory_type: str, prompt: str) -> str:
    escaped_prompt = prompt.replace('"', '\\"')
    return f'waymark capture --type {memory_type} "{escaped_prompt}"'


@app.command("today")
def today_command(
    for_date: Annotated[
        str | None,
        typer.Option("--date", help="Date to inspect in YYYY-MM-DD format."),
    ] = None,
) -> None:
    """Show today's captures, due reflections, decisions, and next commands."""

    try:
        current_date = parse_today_date(for_date)
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    init_database(database_path())
    entries = list_entries(database_path(), limit=1000)
    brief = build_today_brief(
        entries=entries,
        entries_today=list_entries_between(
            database_path(),
            period_start=current_date.isoformat(),
            period_end=current_date.isoformat(),
            limit=100,
        ),
        decisions=list_decisions(database_path(), limit=1000),
        reflections=list_reflections(database_path(), limit=1000),
        today=current_date,
    )
    console.print(
        Panel(
            format_today_brief(brief),
            title="Today",
            border_style="yellow3",
        )
    )


@app.command()
def ask(
    query: Annotated[str, typer.Argument(help="Keyword query for the current app-only search.")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of source memories.")] = 5,
    semantic: Annotated[
        bool,
        typer.Option("--semantic", help="Use explicitly generated local embedding vectors."),
    ] = False,
) -> None:
    """Search saved memories with keyword FTS or explicit local embeddings."""

    init_database(database_path())
    if semantic:
        show_semantic_sources(query=query, limit=limit)
        return

    keyword_entries = search_entries(database_path(), query=query, limit=limit)
    tag_entries = search_entries_by_tags(database_path(), query=query, limit=limit)
    ranked_entries = rank_retrieved_entries(
        keyword_entries=keyword_entries,
        tag_entries=tag_entries,
        semantic_entries=(),
        limit=limit,
    )
    entries = [ranked.entry for ranked in ranked_entries]

    if not entries:
        console.print("[dim]No matching memories found.[/dim]")
        return

    console.print(
        Panel(
            compose_source_answer(query, entries),
            title="Grounded Answer",
            border_style="green",
        )
    )
    console.print(
        "[bold yellow3]Based on saved memories, these sources look relevant:[/bold yellow3]"
    )
    for entry in entries:
        render_entry_source(entry, title=f"Source #{entry.id}")


def show_semantic_sources(*, query: str, limit: int) -> None:
    model = configured_embedding_model()
    if model is None:
        console.print("[red]No embedding model is configured. Run waymark setup --apply.[/red]")
        raise typer.Exit(code=1)

    if count_entry_embeddings(database_path(), model=model) == 0:
        console.print(
            "[dim]No semantic matches found. Run waymark embeddings backfill --apply after "
            "capturing memories.[/dim]"
        )
        return

    status = get_ollama_status()
    readiness_note = embedding_runtime_note(model, status)
    if readiness_note is not None:
        console.print(f"[red]{readiness_note}[/red]")
        raise typer.Exit(code=1)

    try:
        query_vector = embed_text_with_ollama(query, model=model)
    except LocalAiError as error:
        console.print(f"[red]Semantic search failed: {error}[/red]")
        raise typer.Exit(code=1) from error

    keyword_entries = search_entries(database_path(), query=query, limit=limit)
    tag_entries = search_entries_by_tags(database_path(), query=query, limit=limit)
    scored_entries = search_entries_by_embedding(
        database_path(),
        model=model,
        query_vector=query_vector,
        limit=limit,
    )
    ranked_entries = rank_retrieved_entries(
        keyword_entries=keyword_entries,
        tag_entries=tag_entries,
        semantic_entries=scored_entries,
        limit=limit,
    )
    if not ranked_entries:
        console.print("[dim]No semantic matches found.[/dim]")
        return

    entries = [ranked.entry for ranked in ranked_entries]
    console.print(
        Panel(
            compose_source_answer(query, entries),
            title="Grounded Answer",
            border_style="green",
        )
    )
    console.print("[bold yellow3]Semantic source matches:[/bold yellow3]")
    for ranked in ranked_entries:
        reasons = ", ".join(ranked.reasons)
        render_entry_source(
            ranked.entry,
            title=f"Source #{ranked.entry.id}  score {ranked.score:.3f}  {reasons}",
            border_style="yellow3",
        )


@memory_app.command("show")
def memory_show(
    entry_id: Annotated[int, typer.Argument(help="Memory entry id.")],
) -> None:
    """Show one memory card with source and linked decisions."""

    init_database(database_path())
    entry = get_entry(database_path(), entry_id)
    if entry is None:
        console.print(f"[red]Memory #{entry_id} was not found.[/red]")
        raise typer.Exit(code=1)

    linked_decisions = list_entry_decisions(database_path(), entry_id=entry_id)
    console.print(
        Panel(
            format_memory_detail(entry, linked_decisions),
            title="Memory",
            border_style="cyan",
        )
    )


@memory_app.command("edit")
def memory_edit(
    entry_id: Annotated[int, typer.Argument(help="Memory entry id.")],
    text: Annotated[
        str | None,
        typer.Option("--text", help="Replace the raw memory text."),
    ] = None,
    title: Annotated[
        str | None,
        typer.Option("--title", help="Replace the memory title."),
    ] = None,
    summary: Annotated[
        str | None,
        typer.Option("--summary", help="Replace the memory summary."),
    ] = None,
    memory_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="Replace the memory type."),
    ] = None,
    tag: Annotated[
        list[str] | None,
        typer.Option("--tag", help="Replace tags. Can be repeated."),
    ] = None,
    clear_tags: Annotated[
        bool,
        typer.Option("--clear-tags", help="Remove all tags from this memory."),
    ] = False,
) -> None:
    """Edit selected fields on a saved memory."""

    init_database(database_path())
    if tag and clear_tags:
        console.print("[red]Use either --tag or --clear-tags, not both.[/red]")
        raise typer.Exit(code=1)
    if not any([text, title, summary, memory_type, tag, clear_tags]):
        console.print("[dim]No changes requested.[/dim]")
        return

    replacement_tags = () if clear_tags else tag
    try:
        updated = update_entry(
            database_path(),
            entry_id=entry_id,
            raw_text=text,
            memory_type=memory_type,
            title=title,
            summary=summary,
            tags=replacement_tags,
        )
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    if not updated:
        console.print(f"[red]Memory #{entry_id} was not found.[/red]")
        raise typer.Exit(code=1)

    entry = get_entry(database_path(), entry_id)
    if entry is None:
        console.print(f"[red]Memory #{entry_id} was not found after update.[/red]")
        raise typer.Exit(code=1)

    linked_decisions = list_entry_decisions(database_path(), entry_id=entry_id)
    console.print(
        Panel(
            format_memory_detail(entry, linked_decisions),
            title="Updated Memory",
            border_style="green",
        )
    )


@app.command()
def reflect(
    period: Annotated[
        str,
        typer.Option("--period", "-p", help="Reflection period: today, week, or month."),
    ] = "week",
    save: Annotated[
        bool,
        typer.Option("--save", help="Save the generated reflection locally."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Save even if this reflection window already exists."),
    ] = False,
) -> None:
    """Generate an app-only reflection from saved memories."""

    init_database(database_path())
    period_start, period_end = reflection_window(period)
    entries = list_entries_between(
        database_path(),
        period_start=period_start,
        period_end=period_end,
    )
    draft = generate_reflection(
        entries,
        period_type=period,
        period_start=period_start,
        period_end=period_end,
    )

    console.print(Panel(format_reflection(draft), title="Reflection", border_style="yellow3"))
    if save:
        existing = saved_reflection_for_window(
            list_reflections(database_path(), limit=1000),
            period_type=draft.period_type,
            period_start=draft.period_start,
            period_end=draft.period_end,
        )
        if existing is not None and not force:
            console.print(
                f"[yellow]Reflection window already saved as #{existing.id}.[/yellow]"
            )
            console.print("[dim]Use --force to save another copy.[/dim]")
            return
        reflection_id = add_reflection(
            database_path(),
            period_type=draft.period_type,
            period_start=draft.period_start,
            period_end=draft.period_end,
            summary=draft.summary,
            wins=draft.wins,
            patterns=draft.patterns,
            suggestions=draft.suggestions,
        )
        console.print(f"[green]Saved reflection #{reflection_id}[/green]")


@reflections_app.command("list")
def reflections_list(
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of reflections.")] = 20,
) -> None:
    """List saved reflections."""

    init_database(database_path())
    reflections = list_reflections(database_path(), limit=limit)
    if not reflections:
        console.print("[dim]No saved reflections yet. Try: waymark reflect --save[/dim]")
        return

    table = Table(title="Saved Reflections", show_header=True, header_style="bold yellow3")
    table.add_column("ID")
    table.add_column("Period")
    table.add_column("Window")
    table.add_column("Summary")

    for reflection in reflections:
        table.add_row(
            str(reflection.id),
            reflection.period_type,
            f"{reflection.period_start} to {reflection.period_end}",
            reflection.summary,
        )

    console.print(table)


@reflections_app.command("due")
def reflections_due(
    generate_next: Annotated[
        bool,
        typer.Option("--generate-next", help="Generate the first due reflection without saving."),
    ] = False,
    save_next: Annotated[
        bool,
        typer.Option("--save-next", help="Generate and save the first due reflection."),
    ] = False,
) -> None:
    """Show reflection windows with memories but no saved reflection."""

    init_database(database_path())
    queue = build_reflection_queue(
        entries=list_entries(database_path(), limit=1000),
        reflections=list_reflections(database_path(), limit=1000),
    )
    if generate_next and save_next:
        console.print("[red]Use either --generate-next or --save-next, not both.[/red]")
        raise typer.Exit(code=1)
    if generate_next or save_next:
        show_or_save_next_due_reflection(queue, save=save_next)
        return

    console.print(
        Panel(
            format_reflection_queue(queue),
            title="Reflection Queue",
            border_style="yellow3",
        )
    )


def show_or_save_next_due_reflection(queue: ReflectionQueue, *, save: bool) -> None:
    next_item = first_reflection_queue_item(queue)
    if next_item is None:
        console.print("[green]No reflection windows need attention right now.[/green]")
        return

    entries = list_entries_between(
        database_path(),
        period_start=next_item.period_start,
        period_end=next_item.period_end,
    )
    draft = generate_reflection(
        entries,
        period_type=next_item.period_type,
        period_start=next_item.period_start,
        period_end=next_item.period_end,
    )
    console.print(
        Panel(
            format_reflection(draft),
            title="Next Due Reflection",
            border_style="yellow3",
        )
    )
    if not save:
        console.print("[bold]No reflection was saved.[/bold]")
        console.print("[dim]Run again with --save-next to save this due reflection.[/dim]")
        return

    reflection_id = add_reflection(
        database_path(),
        period_type=draft.period_type,
        period_start=draft.period_start,
        period_end=draft.period_end,
        summary=draft.summary,
        wins=draft.wins,
        patterns=draft.patterns,
        suggestions=draft.suggestions,
    )
    console.print(f"[green]Saved reflection #{reflection_id}[/green]")


@reflections_app.command("compare")
def reflections_compare(
    period: Annotated[
        str,
        typer.Option("--period", "-p", help="Reflection period: today, week, or month."),
    ] = "week",
) -> None:
    """Compare a current generated reflection with the latest saved period."""

    init_database(database_path())
    period_start, period_end = reflection_window(period)
    entries = list_entries_between(
        database_path(),
        period_start=period_start,
        period_end=period_end,
    )
    comparison = build_reflection_comparison(
        entries=entries,
        reflections=list_reflections(database_path(), limit=1000),
        period_type=period,
        period_start=period_start,
        period_end=period_end,
    )
    console.print(
        Panel(
            format_reflection_comparison(comparison),
            title="Reflection Comparison",
            border_style="yellow3",
        )
    )


@reflections_app.command("trends")
def reflections_trends(
    period: Annotated[
        str | None,
        typer.Option("--period", "-p", help="Optional period: today, week, or month."),
    ] = None,
    tag: Annotated[
        list[str] | None,
        typer.Option("--tag", help="Only include saved windows containing this tag."),
    ] = None,
    memory_type: Annotated[
        list[str] | None,
        typer.Option(
            "--type",
            "-t",
            help="Only include saved windows containing this memory type.",
        ),
    ] = None,
) -> None:
    """Summarize trends across saved reflections."""

    init_database(database_path())
    scoped_entries = list_entries(database_path(), limit=10000) if tag or memory_type else None
    trend = build_reflection_trend(
        list_reflections(database_path(), limit=1000),
        period_type=period,
        entries=scoped_entries,
        tags=tag or (),
        memory_types=memory_type or (),
    )
    console.print(
        Panel(
            format_reflection_trend(trend),
            title="Reflection Trends",
            border_style="yellow3",
        )
    )


@reflections_app.command("show")
def reflections_show(
    reflection_id: Annotated[int, typer.Argument(help="Saved reflection id.")],
) -> None:
    """Show one saved reflection."""

    init_database(database_path())
    reflection = get_reflection(database_path(), reflection_id)
    if reflection is None:
        console.print(f"[red]Reflection #{reflection_id} was not found.[/red]")
        raise typer.Exit(code=1)

    console.print(
        Panel(format_saved_reflection(reflection), title="Saved Reflection", border_style="yellow3")
    )


@export_app.command("memory")
def export_memory(
    entry_id: Annotated[int, typer.Argument(help="Memory entry id to export.")],
    output: Annotated[Path, typer.Argument(help="Markdown file to write.")],
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite the output file if it already exists."),
    ] = False,
) -> None:
    """Export one saved memory to Markdown."""

    init_database(database_path())
    entry = get_entry(database_path(), entry_id)
    if entry is None:
        console.print(f"[red]Memory #{entry_id} was not found.[/red]")
        raise typer.Exit(code=1)

    content = format_entry_markdown(database_path(), entry)
    try:
        exported_path = write_markdown_export(output, content, force=force)
    except (FileExistsError, OSError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    console.print(f"[green]Wrote Markdown export:[/green] {exported_path}")


@export_app.command("timeline")
def export_timeline(
    output: Annotated[Path, typer.Argument(help="Markdown file to write.")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of memories.")] = 20,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite the output file if it already exists."),
    ] = False,
) -> None:
    """Export recent memories to one Markdown timeline."""

    init_database(database_path())
    entries = list_entries(database_path(), limit=limit)
    if not entries:
        console.print("[dim]No memories to export yet.[/dim]")
        return

    content = format_timeline_markdown(database_path(), entries)
    try:
        exported_path = write_markdown_export(output, content, force=force)
    except (FileExistsError, OSError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    console.print(
        f"[green]Wrote Markdown timeline:[/green] {exported_path} "
        f"[dim]({len(entries)} memories)[/dim]"
    )


@export_app.command("reflection")
def export_reflection(
    reflection_id: Annotated[int, typer.Argument(help="Saved reflection id to export.")],
    output: Annotated[Path, typer.Argument(help="Markdown file to write.")],
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite the output file if it already exists."),
    ] = False,
) -> None:
    """Export one saved reflection to Markdown."""

    init_database(database_path())
    reflection = get_reflection(database_path(), reflection_id)
    if reflection is None:
        console.print(f"[red]Reflection #{reflection_id} was not found.[/red]")
        raise typer.Exit(code=1)

    content = format_reflection_markdown(reflection)
    try:
        exported_path = write_markdown_export(output, content, force=force)
    except (FileExistsError, OSError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    console.print(f"[green]Wrote Markdown reflection:[/green] {exported_path}")


@export_app.command("reflection-trends")
def export_reflection_trends(
    output: Annotated[Path, typer.Argument(help="Markdown file to write.")],
    period: Annotated[
        str | None,
        typer.Option("--period", "-p", help="Optional period: today, week, or month."),
    ] = None,
    tag: Annotated[
        list[str] | None,
        typer.Option("--tag", help="Only include saved windows containing this tag."),
    ] = None,
    memory_type: Annotated[
        list[str] | None,
        typer.Option(
            "--type",
            "-t",
            help="Only include saved windows containing this memory type.",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite the output file if it already exists."),
    ] = False,
) -> None:
    """Export saved reflection trend summaries to Markdown."""

    init_database(database_path())
    scoped_entries = list_entries(database_path(), limit=10000) if tag or memory_type else None
    trend = build_reflection_trend(
        list_reflections(database_path(), limit=1000),
        period_type=period,
        entries=scoped_entries,
        tags=tag or (),
        memory_types=memory_type or (),
    )
    content = format_reflection_trend_markdown(trend)
    try:
        exported_path = write_markdown_export(output, content, force=force)
    except (FileExistsError, OSError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    console.print(f"[green]Wrote Markdown reflection trends:[/green] {exported_path}")


@models_app.command("list")
def models_list() -> None:
    """List locally installed Ollama models without downloading anything."""

    status = get_ollama_status()
    table = Table(title="Local Models", show_header=True, header_style="bold yellow3")
    table.add_column("Runtime")
    table.add_column("Status")
    table.add_column("Model")

    if not status.available:
        table.add_row(status.name, "not found", status.error or "not installed")
        console.print(table)
        console.print("[dim]No models were downloaded.[/dim]")
        return

    if not status.models:
        table.add_row(status.name, "available", status.error or "no installed models found")
    else:
        for model in status.models:
            table.add_row(status.name, "available", model)

    console.print(table)
    console.print("[dim]Read-only check. No models were downloaded.[/dim]")


@models_app.command("check")
def models_check() -> None:
    """Check configured local AI models against installed Ollama models."""

    config = read_config(config_path())
    status = get_ollama_status()
    table = Table(title="Configured Models", show_header=True, header_style="bold yellow3")
    table.add_column("Purpose")
    table.add_column("Configured model")
    table.add_column("Status")
    table.add_column("Manual command")

    if config is None:
        table.add_row("Config", "not set", "missing", "waymark setup --apply")
        console.print(table)
        console.print("[bold]No models were downloaded. No files were scanned.[/bold]")
        return

    configured_models = (
        ("Chat", config.models.chat_model),
        ("Embeddings", config.models.embedding_model),
    )
    for purpose, model in configured_models:
        if model is None:
            table.add_row(purpose, "not configured", "skipped", "none")
            continue
        if not status.available:
            table.add_row(purpose, model, "ollama not found", f"ollama pull {model}")
            continue
        if status.error:
            table.add_row(purpose, model, "check failed", f"ollama pull {model}")
            continue
        if is_model_installed(model, status.models):
            table.add_row(purpose, model, "installed", "already present")
        else:
            table.add_row(purpose, model, "missing", f"ollama pull {model}")

    console.print(table)
    if status.error:
        console.print(f"[yellow]{status.error}[/yellow]")
    console.print("[bold]No models were downloaded. No files were scanned.[/bold]")


@embeddings_app.command("status")
def embeddings_status() -> None:
    """Show explicit local embedding index readiness."""

    db_path = database_path()
    model = configured_embedding_model()
    table = Table(title="Embedding Status", show_header=True, header_style="bold yellow3")
    table.add_column("Item")
    table.add_column("Value")

    if model is None:
        table.add_row("Embedding model", "not configured")
        table.add_row("Next step", "waymark setup --apply")
        console.print(table)
        console.print("[bold]No embeddings were generated.[/bold]")
        return

    if not db_path.exists():
        table.add_row("Embedding model", model)
        table.add_row("Database", "not found")
        table.add_row("Missing entries", "0")
        console.print(table)
        console.print("[bold]No embeddings were generated.[/bold]")
        return

    init_database(db_path)
    generated_count = count_entry_embeddings(db_path, model=model)
    missing_count = count_entries_missing_embeddings(db_path, model=model)
    table.add_row("Embedding model", model)
    table.add_row("Database", str(db_path))
    table.add_row("Generated vectors", str(generated_count))
    table.add_row("Missing entries", str(missing_count))
    console.print(table)
    console.print("[bold]No embeddings were generated.[/bold]")


@embeddings_app.command("backfill")
def embeddings_backfill(
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Generate embeddings for the previewed entries."),
    ] = False,
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, max=100, help="Maximum entries to preview or embed."),
    ] = 10,
) -> None:
    """Preview or explicitly generate missing entry embeddings."""

    init_database(database_path())
    model = configured_embedding_model()
    if model is None:
        console.print("[red]No embedding model is configured. Run waymark setup --apply.[/red]")
        raise typer.Exit(code=1)

    entries = list_entries_missing_embeddings(database_path(), model=model, limit=limit)
    table = Table(title="Embedding Backfill", show_header=True, header_style="bold yellow3")
    table.add_column("ID")
    table.add_column("Title")
    table.add_column("Model")
    for entry in entries:
        table.add_row(str(entry.id), entry.title, model)
    console.print(table)

    if not entries:
        console.print("[green]All current entries already have embeddings for this model.[/green]")
        return

    if not apply:
        console.print("[bold]No embeddings were generated.[/bold]")
        console.print("[dim]Run again with --apply to generate these vectors locally.[/dim]")
        return

    status = get_ollama_status()
    readiness_note = embedding_runtime_note(model, status)
    if readiness_note is not None:
        console.print(f"[red]{readiness_note}[/red]")
        raise typer.Exit(code=1)

    embedded_count = 0
    for entry in entries:
        try:
            vector = embed_text_with_ollama(embedding_text(entry), model=model)
        except LocalAiError as error:
            console.print(f"[red]Embedding failed for memory #{entry.id}: {error}[/red]")
            raise typer.Exit(code=1) from error
        upsert_entry_embedding(
            database_path(),
            entry_id=entry.id,
            model=model,
            vector=vector,
        )
        embedded_count += 1

    console.print(f"[green]Generated {embedded_count} embedding(s) with {model}.[/green]")
    console.print("[bold]No files were scanned. No models were downloaded.[/bold]")


@import_app.command("markdown")
def import_markdown(
    path: Annotated[Path, typer.Argument(help="Path to one Markdown file.")],
    force: Annotated[
        bool,
        typer.Option("--force", help="Import even if this exact file path was imported before."),
    ] = False,
) -> None:
    """Import one explicit Markdown file as a memory entry."""

    init_database(database_path())
    try:
        result = import_markdown_file(database_path(), path, force=force)
    except DuplicateMarkdownImportError as error:
        console.print(f"[yellow]{error}[/yellow]")
        console.print("[dim]Use --force to import another copy.[/dim]")
        return
    except (FileNotFoundError, ValueError, UnicodeDecodeError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    console.print(
        Panel(
            (
                f"[bold]{result.title}[/bold]\n\n{result.summary}\n\n"
                f"[dim]entry: {result.entry_id} - source: {result.source_id}[/dim]"
            ),
            title="Imported Markdown",
            border_style="green",
        )
    )


@import_app.command("text")
def import_text(
    path: Annotated[Path, typer.Argument(help="Path to one .txt or .text file.")],
    force: Annotated[
        bool,
        typer.Option("--force", help="Import even if this exact file path was imported before."),
    ] = False,
) -> None:
    """Import one explicit plain text file as a memory entry."""

    init_database(database_path())
    try:
        result = import_text_file(database_path(), path, force=force)
    except DuplicateTextImportError as error:
        console.print(f"[yellow]{error}[/yellow]")
        console.print("[dim]Use --force to import another copy.[/dim]")
        return
    except (FileNotFoundError, ValueError, UnicodeDecodeError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    console.print(
        Panel(
            (
                f"[bold]{result.title}[/bold]\n\n{result.summary}\n\n"
                f"[dim]entry: {result.entry_id} - source: {result.source_id}[/dim]"
            ),
            title="Imported Text",
            border_style="green",
        )
    )


@import_app.command("pdf")
def import_pdf(
    path: Annotated[Path, typer.Argument(help="Path to one .pdf file.")],
    preview: Annotated[
        bool,
        typer.Option("--preview", "--dry-run", help="Show extracted card without saving."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Import even if this exact file path was imported before."),
    ] = False,
) -> None:
    """Import one explicit PDF file as a memory entry.

    Extracts only the existing text layer. Scanned or image-only PDFs are not
    OCR'd. Requires the optional ``pypdf`` package (pip install waymark[pdf]).
    """

    try:
        if preview:
            draft = preview_pdf_file(path)
            console.print(
                Panel(
                    (
                        f"[bold]{draft.title}[/bold]\n\n{draft.summary}\n\n"
                        f"[dim]{len(draft.raw_text)} characters extracted - not saved[/dim]"
                    ),
                    title="PDF Preview",
                    border_style="yellow3",
                )
            )
            return

        init_database(database_path())
        result = import_pdf_file(database_path(), path, force=force)
    except DuplicatePdfImportError as error:
        console.print(f"[yellow]{error}[/yellow]")
        console.print("[dim]Use --force to import another copy.[/dim]")
        return
    except MissingImportDependencyError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error
    except (FileNotFoundError, ValueError, UnicodeDecodeError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    console.print(
        Panel(
            (
                f"[bold]{result.title}[/bold]\n\n{result.summary}\n\n"
                f"[dim]entry: {result.entry_id} - source: {result.source_id}[/dim]"
            ),
            title="Imported PDF",
            border_style="green",
        )
    )


@import_app.command("docx")
def import_docx(
    path: Annotated[Path, typer.Argument(help="Path to one .docx file.")],
    preview: Annotated[
        bool,
        typer.Option("--preview", "--dry-run", help="Show extracted card without saving."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Import even if this exact file path was imported before."),
    ] = False,
) -> None:
    """Import one explicit Word .docx file as a memory entry.

    Extracts paragraph text only. Styles, images, and embedded objects are not
    imported.
    """

    try:
        if preview:
            draft = preview_docx_file(path)
            console.print(
                Panel(
                    (
                        f"[bold]{draft.title}[/bold]\n\n{draft.summary}\n\n"
                        f"[dim]{len(draft.raw_text)} characters extracted - not saved[/dim]"
                    ),
                    title="DOCX Preview",
                    border_style="yellow3",
                )
            )
            return

        init_database(database_path())
        result = import_docx_file(database_path(), path, force=force)
    except DuplicateDocxImportError as error:
        console.print(f"[yellow]{error}[/yellow]")
        console.print("[dim]Use --force to import another copy.[/dim]")
        return
    except (FileNotFoundError, ValueError, UnicodeDecodeError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    console.print(
        Panel(
            (
                f"[bold]{result.title}[/bold]\n\n{result.summary}\n\n"
                f"[dim]entry: {result.entry_id} - source: {result.source_id}[/dim]"
            ),
            title="Imported DOCX",
            border_style="green",
        )
    )


@import_app.command("markdown-folder")
def import_markdown_folder_command(
    path: Annotated[Path, typer.Argument(help="Path to a folder of Markdown files.")],
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Actually import the previewed files."),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option("--recursive", help="Include nested folders."),
    ] = False,
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, max=500, help="Maximum Markdown files to preview/import."),
    ] = 25,
    force: Annotated[
        bool,
        typer.Option("--force", help="Import files even if their paths were imported before."),
    ] = False,
) -> None:
    """Legacy Markdown-only folder importer. Prefer `waymark import folder`."""

    console.print(
        "[yellow]Legacy command:[/yellow] prefer [bold]waymark import folder[/bold] "
        "for Markdown, text, PDF, and DOCX batches."
    )

    try:
        if apply:
            init_database(database_path())
            result = import_markdown_folder(
                database_path(),
                path,
                recursive=recursive,
                limit=limit,
                force=force,
            )
        else:
            preview = preview_markdown_folder(path, recursive=recursive, limit=limit)
    except (FileNotFoundError, OSError, ValueError, UnicodeDecodeError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    if apply:
        table = Table(
            title="Imported Markdown Folder",
            show_header=True,
            header_style="bold yellow3",
        )
        table.add_column("Entry")
        table.add_column("Source")
        table.add_column("Title")
        table.add_column("Summary")
        for imported_item in result.imported:
            table.add_row(
                str(imported_item.entry_id),
                str(imported_item.source_id),
                imported_item.title,
                imported_item.summary,
            )

        console.print(table)
        console.print(f"[green]Imported {len(result.imported)} Markdown file(s).[/green]")
        if result.truncated:
            console.print(f"[yellow]Import stopped at --limit {limit}.[/yellow]")
            console.print("[dim]Increase the limit to import more.[/dim]")
        if result.skipped:
            console.print("[yellow]Some files were skipped:[/yellow]")
            for skipped in result.skipped:
                console.print(f"[dim]- {skipped}[/dim]")
        return

    table = Table(
        title="Markdown Folder Preview",
        show_header=True,
        header_style="bold yellow3",
    )
    table.add_column("#")
    table.add_column("Title")
    table.add_column("File")
    table.add_column("Summary")
    for index, preview_item in enumerate(preview.files, start=1):
        table.add_row(
            str(index),
            preview_item.title,
            preview_item.path.relative_to(preview.root).as_posix(),
            preview_item.summary,
        )

    console.print(table)
    if preview.truncated:
        console.print(
            f"[yellow]Preview stopped at --limit {limit}. Increase the limit to see more.[/yellow]"
        )
    if preview.skipped:
        console.print("[yellow]Some files were skipped:[/yellow]")
        for skipped in preview.skipped:
            console.print(f"[dim]- {skipped}[/dim]")
    console.print("[bold]No files were imported.[/bold]")
    console.print("[dim]Run again with --apply to import the previewed files.[/dim]")


@import_app.command("folder")
def import_folder_command(
    path: Annotated[Path, typer.Argument(help="Path to a folder of supported files.")],
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Actually import the previewed files."),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option("--recursive", help="Include nested folders."),
    ] = False,
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, max=500, help="Maximum files to preview/import."),
    ] = 25,
    force: Annotated[
        bool,
        typer.Option("--force", help="Import files even if their paths were imported before."),
    ] = False,
) -> None:
    """Preview or import all supported files (.md, .txt, .pdf, .docx) from one folder."""

    try:
        if apply:
            init_database(database_path())
            result = import_folder(
                database_path(),
                path,
                recursive=recursive,
                limit=limit,
                force=force,
            )
        else:
            preview = preview_import_folder(path, recursive=recursive, limit=limit)
    except (FileNotFoundError, OSError, ValueError, UnicodeDecodeError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    if apply:
        table = Table(
            title="Imported Folder",
            show_header=True,
            header_style="bold yellow3",
        )
        table.add_column("Entry")
        table.add_column("Source")
        table.add_column("Type")
        table.add_column("Title")
        for imported_item in result.imported:
            table.add_row(
                str(imported_item.entry_id),
                str(imported_item.source_id),
                imported_item.source_type,
                imported_item.title,
            )

        console.print(table)
        console.print(f"[green]Imported {len(result.imported)} file(s).[/green]")
        if result.duplicates:
            console.print(
                f"[yellow]{len(result.duplicates)} file(s) were already imported "
                f"(use --force to re-import):[/yellow]"
            )
            for duplicate in result.duplicates:
                console.print(f"[dim]- {duplicate}[/dim]")
        if result.truncated:
            console.print(f"[yellow]Import stopped at --limit {limit}.[/yellow]")
            console.print("[dim]Increase the limit to import more.[/dim]")
        if result.skipped:
            console.print("[yellow]Some files were skipped:[/yellow]")
            for skipped in result.skipped:
                console.print(f"[dim]- {skipped}[/dim]")
        return

    table = Table(
        title="Folder Preview",
        show_header=True,
        header_style="bold yellow3",
    )
    table.add_column("#")
    table.add_column("Type")
    table.add_column("Title")
    table.add_column("File")
    table.add_column("Summary")
    for index, preview_item in enumerate(preview.files, start=1):
        table.add_row(
            str(index),
            preview_item.source_type,
            preview_item.title,
            preview_item.path.relative_to(preview.root).as_posix(),
            preview_item.summary,
        )

    console.print(table)
    if preview.truncated:
        console.print(
            f"[yellow]Preview stopped at --limit {limit}. Increase the limit to see more.[/yellow]"
        )
    if preview.skipped:
        console.print("[yellow]Some files were skipped:[/yellow]")
        for skipped in preview.skipped:
            console.print(f"[dim]- {skipped}[/dim]")
    console.print("[bold]No files were imported.[/bold]")
    console.print("[dim]Run again with --apply to import the previewed files.[/dim]")


@sources_app.command("list")
def sources_list(
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of sources.")] = 20,
) -> None:
    """List imported sources."""

    init_database(database_path())
    sources = list_sources(database_path(), limit=limit)
    if not sources:
        console.print("[dim]No imported sources yet.[/dim]")
        return

    table = Table(title="Sources", show_header=True, header_style="bold yellow3")
    table.add_column("ID")
    table.add_column("Type")
    table.add_column("Name")
    table.add_column("Path")

    for source in sources:
        table.add_row(
            str(source.id),
            source.type,
            source.original_filename or "",
            source.path or "",
        )

    console.print(table)


def _print_backup_counts(title: str, counts: dict[str, int], total: int) -> None:
    table = Table(title=title, show_header=True, header_style="bold yellow3")
    table.add_column("Table")
    table.add_column("Rows", justify="right")
    for name, count in counts.items():
        table.add_row(name, str(count))
    table.add_row("[bold]total[/bold]", f"[bold]{total}[/bold]")
    console.print(table)


@backup_app.command("create")
def backup_create(
    path: Annotated[Path, typer.Argument(help="Output .json backup file path.")],
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite an existing backup file."),
    ] = False,
) -> None:
    """Write a full JSON backup of your Waymark home to one explicit file."""

    try:
        summary = write_backup(database_path(), path, force=force)
    except BackupError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    _print_backup_counts("Backup created", summary.table_counts, summary.total_rows)
    console.print(f"[green]Wrote {summary.total_rows} row(s) to {summary.path}.[/green]")


@backup_app.command("info")
def backup_info(
    path: Annotated[Path, typer.Argument(help="Backup .json file to inspect.")],
) -> None:
    """Show what a backup file contains without restoring it."""

    try:
        backup = read_backup(path)
    except BackupError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    tables = backup["tables"]
    counts = {table: len(tables.get(table, [])) for table in BACKUP_TABLES}
    created = backup.get("created_at", "unknown")
    console.print(f"[dim]Backup created at: {created}[/dim]")
    _print_backup_counts("Backup contents", counts, sum(counts.values()))


@backup_app.command("restore")
def backup_restore(
    path: Annotated[Path, typer.Argument(help="Backup .json file to restore from.")],
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite the current home if it already has memories."),
    ] = False,
) -> None:
    """Rebuild your Waymark home from a backup file.

    Refuses to overwrite a home that already holds memories unless --force is
    passed, in which case existing data is cleared first.
    """

    try:
        backup = read_backup(path)
        summary = restore_backup(backup, database_path(), force=force)
    except BackupError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    action = "Restored (overwrote existing home)" if summary.overwrote else "Restored"
    _print_backup_counts(action, summary.table_counts, summary.total_rows)
    console.print(
        f"[green]Restored {summary.total_rows} row(s) into {database_path()}.[/green]"
    )


@backup_app.command("bundle")
def backup_bundle(
    path: Annotated[Path, typer.Argument(help="Output folder for the portable bundle.")],
    force: Annotated[
        bool,
        typer.Option("--force", help="Write into an existing non-empty bundle folder."),
    ] = False,
) -> None:
    """Write a restore-ready backup plus readable Markdown exports to one folder."""

    try:
        summary = write_portable_bundle(database_path(), path, force=force)
    except BackupError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    _print_backup_counts("Portable bundle created", summary.table_counts, summary.total_rows)
    console.print(f"[green]Wrote {len(summary.files)} file(s) to {summary.path}.[/green]")
    console.print(
        f"[dim]{summary.memory_count} memories, {summary.reflection_count} reflections, "
        f"{summary.source_count} sources[/dim]"
    )


@decision_app.command("add")
def decision_add(
    title: Annotated[str, typer.Argument(help="Decision title.")],
    context: Annotated[str, typer.Option("--context", "-c", help="Decision context.")],
    option: Annotated[
        list[str] | None,
        typer.Option("--option", "-o", help="Decision option. Can be repeated."),
    ] = None,
    confidence: Annotated[
        int | None,
        typer.Option("--confidence", min=1, max=5, help="Confidence from 1 to 5."),
    ] = None,
    review_date: Annotated[
        str | None,
        typer.Option("--review-date", help="Optional review date, such as 2026-06-12."),
    ] = None,
    memory: Annotated[
        list[int] | None,
        typer.Option("--memory", "-m", help="Memory entry id to link. Can be repeated."),
    ] = None,
) -> None:
    """Add an open decision."""

    init_database(database_path())
    decision_id = add_decision(
        database_path(),
        title=title,
        context=context,
        options=option or (),
        confidence=confidence,
        review_date=review_date,
    )
    for entry_id in memory or ():
        linked = link_decision_entry(database_path(), decision_id=decision_id, entry_id=entry_id)
        if not linked:
            console.print(f"[yellow]Memory #{entry_id} was not found; link skipped.[/yellow]")
    console.print(f"[green]Saved decision #{decision_id}[/green] {title}")


@decision_app.command("list")
def decision_list(
    status: Annotated[
        str | None,
        typer.Option("--status", help="Filter by status, such as open or done."),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of decisions.")] = 20,
) -> None:
    """List tracked decisions."""

    init_database(database_path())
    decisions = list_decisions(database_path(), status=status, limit=limit)
    if not decisions:
        console.print("[dim]No decisions yet. Try: waymark decision add ...[/dim]")
        return

    table = Table(title="Decisions", show_header=True, header_style="bold yellow3")
    table.add_column("ID")
    table.add_column("Status")
    table.add_column("Title")
    table.add_column("Confidence")
    table.add_column("Review")
    table.add_column("Memories")

    for decision in decisions:
        table.add_row(
            str(decision.id),
            decision.status,
            decision.title,
            str(decision.confidence or ""),
            decision.review_date or "",
            memory_refs(decision.entry_ids),
        )

    console.print(table)


@decision_app.command("review")
def decision_review(
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Number of decisions to inspect."),
    ] = 100,
) -> None:
    """Show decisions due for review or waiting for outcomes."""

    init_database(database_path())
    decisions = list_decisions(database_path(), limit=limit)
    queue = build_decision_review_queue(decisions)
    console.print(
        Panel(
            format_decision_review_queue(queue),
            title="Decision Review Queue",
            border_style="yellow3",
        )
    )


@decision_app.command("show")
def decision_show(
    decision_id: Annotated[int, typer.Argument(help="Decision id.")],
) -> None:
    """Show a decision with linked memory context."""

    init_database(database_path())
    decision = get_decision(database_path(), decision_id)
    if decision is None:
        console.print(f"[red]Decision #{decision_id} was not found.[/red]")
        raise typer.Exit(code=1)

    linked_entries = list_decision_entries(database_path(), decision_id=decision_id)
    console.print(
        Panel(
            format_decision_detail(decision, linked_entries),
            title="Decision",
            border_style="yellow3",
        )
    )


@decision_app.command("link")
def decision_link(
    decision_id: Annotated[int, typer.Argument(help="Decision id.")],
    entry_id: Annotated[int, typer.Argument(help="Memory entry id to link.")],
) -> None:
    """Link a decision to a saved memory."""

    init_database(database_path())
    if get_decision(database_path(), decision_id) is None:
        console.print(f"[red]Decision #{decision_id} was not found.[/red]")
        raise typer.Exit(code=1)
    if get_entry(database_path(), entry_id) is None:
        console.print(f"[red]Memory #{entry_id} was not found.[/red]")
        raise typer.Exit(code=1)

    link_decision_entry(database_path(), decision_id=decision_id, entry_id=entry_id)
    console.print(f"[green]Linked decision #{decision_id} to memory #{entry_id}[/green]")


@decision_app.command("unlink")
def decision_unlink(
    decision_id: Annotated[int, typer.Argument(help="Decision id.")],
    entry_id: Annotated[int, typer.Argument(help="Memory entry id to unlink.")],
) -> None:
    """Remove a memory link from a decision."""

    init_database(database_path())
    unlinked = unlink_decision_entry(database_path(), decision_id=decision_id, entry_id=entry_id)
    if not unlinked:
        console.print(f"[red]Decision #{decision_id} is not linked to memory #{entry_id}.[/red]")
        raise typer.Exit(code=1)

    console.print(f"[green]Unlinked decision #{decision_id} from memory #{entry_id}[/green]")


@decision_app.command("finalize")
def decision_finalize(
    decision_id: Annotated[int, typer.Argument(help="Decision id.")],
    choice: Annotated[str, typer.Option("--choice", "-c", help="Final choice.")],
    confidence: Annotated[
        int | None,
        typer.Option("--confidence", min=1, max=5, help="Updated confidence from 1 to 5."),
    ] = None,
) -> None:
    """Mark a decision as decided."""

    init_database(database_path())
    updated = finalize_decision(
        database_path(),
        decision_id=decision_id,
        final_choice=choice,
        confidence=confidence,
    )
    if not updated:
        console.print(f"[red]Decision #{decision_id} was not found.[/red]")
        raise typer.Exit(code=1)

    console.print(f"[green]Finalized decision #{decision_id}[/green] {choice}")


@decision_app.command("outcome")
def decision_outcome(
    decision_id: Annotated[int, typer.Argument(help="Decision id.")],
    outcome: Annotated[str, typer.Option("--outcome", "-o", help="Observed outcome.")],
) -> None:
    """Record an outcome after reviewing a past decision."""

    init_database(database_path())
    updated = record_decision_outcome(database_path(), decision_id=decision_id, outcome=outcome)
    if not updated:
        console.print(f"[red]Decision #{decision_id} was not found.[/red]")
        raise typer.Exit(code=1)

    console.print(f"[green]Recorded outcome for decision #{decision_id}[/green]")
