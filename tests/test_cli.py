from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pytest import MonkeyPatch
from typer.testing import CliRunner

from waymark.cli import app
from waymark.storage import (
    add_reflection,
    get_entry_embedding,
    list_entries,
    list_sources,
    upsert_entry_embedding,
)


def write_ollama_embedding_config(home: Path) -> None:
    from waymark.config import (
        FeatureConfig,
        ModelConfig,
        PerformanceConfig,
        SetupConfig,
        WaymarkConfig,
        write_config,
    )

    write_config(
        home / "config.json",
        WaymarkConfig(
            performance=PerformanceConfig(
                mode="balanced",
                max_memory_gb=8,
                max_cpu_percent=60,
                pause_on_battery=True,
                background_indexing=False,
            ),
            models=ModelConfig(
                runtime="ollama",
                chat_model="qwen3:4b",
                embedding_model="nomic-embed-text",
            ),
            features=FeatureConfig(
                local_ai_chat=True,
                semantic_search=True,
                ocr="manual",
                background_indexing=False,
            ),
            setup=SetupConfig(completed=True, completed_at="2026-05-30T00:00:00Z"),
        ),
    )


def test_decision_cli_add_and_list(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    add_result = runner.invoke(
        app,
        [
            "decision",
            "add",
            "Build CLI first?",
            "--context",
            "The memory engine matters most.",
            "--option",
            "CLI first",
            "--option",
            "Desktop first",
            "--confidence",
            "4",
        ],
        env=env,
    )
    assert add_result.exit_code == 0
    assert "Saved decision #1" in add_result.output

    list_result = runner.invoke(app, ["decision", "list"], env=env)

    assert list_result.exit_code == 0
    assert "Build CLI first?" in list_result.output


def test_decision_cli_links_memories(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    capture_result = runner.invoke(
        app,
        ["capture", "--type", "project", "This memory informs a decision."],
        env=env,
    )
    assert capture_result.exit_code == 0

    add_result = runner.invoke(
        app,
        [
            "decision",
            "add",
            "Use linked memories?",
            "--context",
            "Decisions should keep their evidence trail.",
            "--memory",
            "1",
        ],
        env=env,
    )
    assert add_result.exit_code == 0

    list_result = runner.invoke(app, ["decision", "list"], env=env)
    assert list_result.exit_code == 0
    assert "#1" in list_result.output

    show_result = runner.invoke(app, ["decision", "show", "1"], env=env)
    assert show_result.exit_code == 0
    assert "Linked Memories" in show_result.output
    assert "This memory informs a decision." in show_result.output

    unlink_result = runner.invoke(app, ["decision", "unlink", "1", "1"], env=env)
    assert unlink_result.exit_code == 0
    link_result = runner.invoke(app, ["decision", "link", "1", "1"], env=env)
    assert link_result.exit_code == 0
    assert "Linked decision #1 to memory #1" in link_result.output

    memory_result = runner.invoke(app, ["memory", "show", "1"], env=env)
    assert memory_result.exit_code == 0
    assert "Linked Decisions" in memory_result.output
    assert "Use linked memories?" in memory_result.output


def test_decision_cli_finalize_and_outcome(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    runner.invoke(
        app,
        [
            "decision",
            "add",
            "Build CLI first?",
            "--context",
            "The memory engine matters most.",
        ],
        env=env,
    )

    finalize_result = runner.invoke(
        app,
        ["decision", "finalize", "1", "--choice", "CLI first", "--confidence", "5"],
        env=env,
    )
    assert finalize_result.exit_code == 0
    assert "Finalized decision #1" in finalize_result.output

    outcome_result = runner.invoke(
        app,
        [
            "decision",
            "outcome",
            "1",
            "--outcome",
            "The CLI foundation was the right first move.",
        ],
        env=env,
    )
    assert outcome_result.exit_code == 0
    assert "Recorded outcome for decision #1" in outcome_result.output

    list_result = runner.invoke(app, ["decision", "list", "--status", "reviewed"], env=env)
    assert list_result.exit_code == 0
    assert "reviewed" in list_result.output


def test_setup_apply_writes_config(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    result = runner.invoke(app, ["setup", "--apply"], env=env)

    assert result.exit_code == 0
    assert "No models were downloaded" in result.output
    assert "Wrote config" in result.output
    assert (tmp_path / "config.json").exists()


def test_setup_models_previews_manual_pull_commands(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from waymark import cli
    from waymark.runtime import ModelRuntimeStatus
    from waymark.system import CapabilityRecommendation, SystemProfile

    profile = SystemProfile(
        os_name="Windows",
        os_version="test",
        machine="AMD64",
        processor="test-cpu",
        cpu_count=8,
        total_ram_gb=16,
        disk_free_gb=20,
        recommendation=CapabilityRecommendation(
            mode="balanced",
            chat_model="qwen3:4b",
            embedding_model="nomic-embed-text",
            reason="test recommendation",
        ),
    )
    monkeypatch.setattr(cli, "collect_system_profile", lambda home: profile)
    monkeypatch.setattr(
        cli,
        "get_ollama_status",
        lambda: ModelRuntimeStatus(
            name="ollama",
            available=True,
            executable="ollama",
            models=("nomic-embed-text:latest",),
        ),
    )
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    result = runner.invoke(app, ["setup", "models"], env=env)

    assert result.exit_code == 0
    assert "Waymark Model Setup" in result.output
    assert "ollama pull qwen3:4b" in result.output
    assert "already present" in result.output
    assert "No models were downloaded" in result.output
    assert not (tmp_path / "config.json").exists()


def test_setup_models_apply_writes_config_without_downloading(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from waymark import cli
    from waymark.runtime import ModelRuntimeStatus
    from waymark.system import CapabilityRecommendation, SystemProfile

    profile = SystemProfile(
        os_name="Windows",
        os_version="test",
        machine="AMD64",
        processor="test-cpu",
        cpu_count=8,
        total_ram_gb=16,
        disk_free_gb=20,
        recommendation=CapabilityRecommendation(
            mode="balanced",
            chat_model="qwen3:4b",
            embedding_model="nomic-embed-text",
            reason="test recommendation",
        ),
    )
    monkeypatch.setattr(cli, "collect_system_profile", lambda home: profile)
    monkeypatch.setattr(
        cli,
        "get_ollama_status",
        lambda: ModelRuntimeStatus(
            name="ollama",
            available=False,
            executable=None,
            models=(),
            error="not found",
        ),
    )
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    result = runner.invoke(app, ["setup", "models", "--apply"], env=env)

    assert result.exit_code == 0
    assert "Wrote config" in result.output
    assert "No models were downloaded" in result.output
    assert (tmp_path / "config.json").exists()


def test_timeline_cli_shows_memory_ids(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    capture_result = runner.invoke(app, ["capture", "Timeline should show IDs."], env=env)
    assert capture_result.exit_code == 0

    timeline_result = runner.invoke(app, ["timeline"], env=env)

    assert timeline_result.exit_code == 0
    assert "ID" in timeline_result.output
    assert "1" in timeline_result.output
    assert "Timeline should show IDs." in timeline_result.output


def test_memory_edit_cli_updates_fields_and_tags(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    capture_result = runner.invoke(
        app,
        ["capture", "--type", "daily", "--tag", "old", "Original memory."],
        env=env,
    )
    assert capture_result.exit_code == 0

    edit_result = runner.invoke(
        app,
        [
            "memory",
            "edit",
            "1",
            "--text",
            "Updated memory.",
            "--title",
            "Updated title",
            "--summary",
            "Updated summary.",
            "--type",
            "project",
            "--tag",
            "new",
            "--tag",
            "edited",
        ],
        env=env,
    )

    assert edit_result.exit_code == 0
    assert "Updated Memory" in edit_result.output
    assert "Updated title" in edit_result.output
    assert "edited, new" in edit_result.output

    ask_result = runner.invoke(app, ["ask", "Updated"], env=env)
    assert ask_result.exit_code == 0
    assert "Grounded Answer" in ask_result.output
    assert "Updated summary." in ask_result.output
    assert "#1" in ask_result.output
    assert "Updated title" in ask_result.output


def test_memory_edit_cli_clears_tags(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    runner.invoke(app, ["capture", "--tag", "remove", "Tagged memory."], env=env)

    edit_result = runner.invoke(app, ["memory", "edit", "1", "--clear-tags"], env=env)
    show_result = runner.invoke(app, ["memory", "show", "1"], env=env)

    assert edit_result.exit_code == 0
    assert show_result.exit_code == 0
    assert "Tags: none" in show_result.output


def test_ask_uses_tag_matches(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    capture_result = runner.invoke(
        app,
        ["capture", "--tag", "local-first", "This body uses different words."],
        env=env,
    )
    assert capture_result.exit_code == 0

    ask_result = runner.invoke(app, ["ask", "local first"], env=env)

    assert ask_result.exit_code == 0
    assert "Grounded Answer" in ask_result.output
    assert "This body uses different words." in ask_result.output
    assert "#1" in ask_result.output


def test_journey_cli_shows_memory_health(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    capture_result = runner.invoke(
        app,
        ["capture", "--tag", "journey", "A journey map memory."],
        env=env,
    )
    assert capture_result.exit_code == 0
    decision_result = runner.invoke(
        app,
        [
            "decision",
            "add",
            "Review direction",
            "--context",
            "The project needs a direction check.",
            "--memory",
            "1",
        ],
        env=env,
    )
    assert decision_result.exit_code == 0

    result = runner.invoke(app, ["journey"], env=env)

    assert result.exit_code == 0
    assert "Journey Map" in result.output
    assert "Total memories: 1" in result.output
    assert "journey (1)" in result.output
    assert "Thin areas:" in result.output
    assert "Capture one" in result.output
    assert "Open: 1" in result.output
    assert "#1 Review direction" in result.output


def test_journey_prompts_cli_shows_capture_commands(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    capture_result = runner.invoke(
        app,
        ["capture", "--type", "project", "A project memory exists."],
        env=env,
    )
    assert capture_result.exit_code == 0

    result = runner.invoke(app, ["journey", "prompts"], env=env)

    assert result.exit_code == 0
    assert "Capture Prompts" in result.output
    assert "daily" in result.output
    assert 'waymark capture --type daily "Capture one ordinary detail' in result.output


def test_reflections_due_cli_lists_missing_windows(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    capture_result = runner.invoke(app, ["capture", "A reflection queue memory."], env=env)
    assert capture_result.exit_code == 0

    result = runner.invoke(app, ["reflections", "due"], env=env)

    assert result.exit_code == 0
    assert "Reflection Queue" in result.output
    assert "Reflection Windows" in result.output
    assert "waymark reflect --period" in result.output


def test_reflections_due_cli_shows_latest_saved_window(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    capture_result = runner.invoke(app, ["capture", "New reflection material."], env=env)
    assert capture_result.exit_code == 0
    add_reflection(
        tmp_path / "waymark.sqlite3",
        period_type="week",
        period_start="2000-01-01",
        period_end="2000-01-07",
        summary="Older saved week.",
    )

    result = runner.invoke(app, ["reflections", "due"], env=env)

    assert result.exit_code == 0
    assert "Latest saved:" in result.output
    assert "#1 2000-01-01 to 2000-01-07" in result.output


def test_reflections_compare_cli_compares_latest_saved_period(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    capture_result = runner.invoke(
        app,
        ["capture", "--type", "project", "Comparison source memory."],
        env=env,
    )
    assert capture_result.exit_code == 0
    add_reflection(
        tmp_path / "waymark.sqlite3",
        period_type="week",
        period_start="2000-01-01",
        period_end="2000-01-07",
        summary="Older saved week.",
        wins=("#99 Older win",),
    )

    result = runner.invoke(app, ["reflections", "compare", "--period", "week"], env=env)

    assert result.exit_code == 0
    assert "Reflection Comparison" in result.output
    assert "Latest saved: #1 2000-01-01 to 2000-01-07" in result.output
    assert "New source wins" in result.output


def test_reflections_trends_cli_summarizes_saved_reflections(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}
    db_path = tmp_path / "waymark.sqlite3"

    runner.invoke(app, ["capture", "Initialize database."], env=env)
    add_reflection(
        db_path,
        period_type="week",
        period_start="2026-05-17",
        period_end="2026-05-23",
        summary="Saved previous week.",
        patterns=("Most active memory types: project (2).",),
        suggestions=("Review the top theme.",),
    )
    add_reflection(
        db_path,
        period_type="week",
        period_start="2026-05-24",
        period_end="2026-05-30",
        summary="Saved current week.",
        patterns=("Most active memory types: project (2).",),
        suggestions=("Review the top theme.",),
    )

    result = runner.invoke(app, ["reflections", "trends", "--period", "week"], env=env)

    assert result.exit_code == 0
    assert "Reflection Trends" in result.output
    assert "Saved Reflection Trends (week)" in result.output
    assert "Saved reflections: 2" in result.output
    assert "Repeated patterns" in result.output


def test_reflections_trends_cli_filters_by_memory_scope(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}
    db_path = tmp_path / "waymark.sqlite3"
    today = datetime.now(UTC).date().isoformat()

    capture_result = runner.invoke(
        app,
        ["capture", "--type", "project", "--tag", "focus", "Scoped trend source."],
        env=env,
    )
    assert capture_result.exit_code == 0
    add_reflection(
        db_path,
        period_type="week",
        period_start=today,
        period_end=today,
        summary="Matching saved week.",
        patterns=("Scoped project pattern.",),
        suggestions=("Review scoped project.",),
    )
    add_reflection(
        db_path,
        period_type="week",
        period_start="2000-01-01",
        period_end="2000-01-07",
        summary="Old unrelated week.",
        patterns=("Old pattern.",),
        suggestions=("Review old week.",),
    )

    result = runner.invoke(
        app,
        ["reflections", "trends", "--period", "week", "--tag", "focus", "--type", "project"],
        env=env,
    )

    assert result.exit_code == 0
    assert "Memory scope: tags: focus; types: project" in result.output
    assert "Saved reflections: 1" in result.output
    assert "Matching saved week." in result.output
    assert "Old unrelated week." not in result.output


def test_reflections_due_generate_next_previews_without_saving(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    capture_result = runner.invoke(app, ["capture", "Generate next reflection."], env=env)
    assert capture_result.exit_code == 0

    result = runner.invoke(app, ["reflections", "due", "--generate-next"], env=env)

    assert result.exit_code == 0
    assert "Next Due Reflection" in result.output
    assert "No reflection was saved" in result.output
    assert runner.invoke(app, ["reflections", "list"], env=env).output.count("Saved") == 0


def test_reflections_due_save_next_saves_first_due_window(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    capture_result = runner.invoke(app, ["capture", "Save next reflection."], env=env)
    assert capture_result.exit_code == 0

    result = runner.invoke(app, ["reflections", "due", "--save-next"], env=env)
    list_result = runner.invoke(app, ["reflections", "list"], env=env)

    assert result.exit_code == 0
    assert "Saved reflection #1" in result.output
    assert list_result.exit_code == 0
    assert "today" in list_result.output


def test_decision_review_cli_lists_due_and_outcome_items(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    due_result = runner.invoke(
        app,
        [
            "decision",
            "add",
            "Due decision",
            "--context",
            "Needs review.",
            "--review-date",
            "2000-01-01",
            "--confidence",
            "3",
        ],
        env=env,
    )
    assert due_result.exit_code == 0
    waiting_result = runner.invoke(
        app,
        [
            "decision",
            "add",
            "Waiting decision",
            "--context",
            "Needs outcome.",
        ],
        env=env,
    )
    assert waiting_result.exit_code == 0
    finalize_result = runner.invoke(
        app,
        ["decision", "finalize", "2", "--choice", "Try it", "--confidence", "4"],
        env=env,
    )
    assert finalize_result.exit_code == 0

    result = runner.invoke(app, ["decision", "review"], env=env)

    assert result.exit_code == 0
    assert "Decision Review Queue" in result.output
    assert "#1 Due decision" in result.output
    assert "#2 Waiting decision" in result.output
    assert "choice: Try it" in result.output


def test_capture_local_ai_uses_configured_draft(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from waymark import cli
    from waymark.config import (
        FeatureConfig,
        ModelConfig,
        PerformanceConfig,
        SetupConfig,
        WaymarkConfig,
        write_config,
    )
    from waymark.memory import MemoryDraft
    from waymark.runtime import ModelRuntimeStatus

    config = WaymarkConfig(
        performance=PerformanceConfig(
            mode="balanced",
            max_memory_gb=8,
            max_cpu_percent=60,
            pause_on_battery=True,
            background_indexing=False,
        ),
        models=ModelConfig(
            runtime="ollama",
            chat_model="qwen3:4b",
            embedding_model="nomic-embed-text",
        ),
        features=FeatureConfig(
            local_ai_chat=True,
            semantic_search=True,
            ocr="manual",
            background_indexing=False,
        ),
        setup=SetupConfig(completed=True, completed_at="2026-05-30T00:00:00Z"),
    )
    write_config(tmp_path / "config.json", config)

    def fake_structure_memory_with_ollama(
        raw_text: str,
        *,
        memory_type: str,
        raw_tags: str,
        model: str,
    ) -> MemoryDraft:
        assert raw_text == "Raw memory for local AI."
        assert memory_type == "daily"
        assert raw_tags == "waymark"
        assert model == "qwen3:4b"
        return MemoryDraft(
            raw_text=raw_text,
            memory_type="project",
            title="AI drafted title",
            summary="AI drafted summary.",
            tags=("ai", "waymark"),
    )

    monkeypatch.setattr(cli, "structure_memory_with_ollama", fake_structure_memory_with_ollama)
    monkeypatch.setattr(
        cli,
        "get_ollama_status",
        lambda: ModelRuntimeStatus(
            name="ollama",
            available=True,
            executable="ollama",
            models=("qwen3:4b",),
        ),
    )
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    result = runner.invoke(
        app,
        ["capture", "--local-ai", "--yes", "--tag", "waymark", "Raw memory for local AI."],
        env=env,
    )

    assert result.exit_code == 0
    assert "AI drafted title" in result.output
    assert "draft: local-ai:qwen3:4b" in result.output
    entries = list_entries(tmp_path / "waymark.sqlite3")
    assert entries[0].title == "AI drafted title"
    assert entries[0].tags == ("ai", "waymark")


def test_capture_local_ai_requires_confirmation(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from waymark import cli
    from waymark.config import (
        FeatureConfig,
        ModelConfig,
        PerformanceConfig,
        SetupConfig,
        WaymarkConfig,
        write_config,
    )
    from waymark.memory import MemoryDraft
    from waymark.runtime import ModelRuntimeStatus

    write_config(
        tmp_path / "config.json",
        WaymarkConfig(
            performance=PerformanceConfig(
                mode="balanced",
                max_memory_gb=8,
                max_cpu_percent=60,
                pause_on_battery=True,
                background_indexing=False,
            ),
            models=ModelConfig(
                runtime="ollama",
                chat_model="qwen3:4b",
                embedding_model="nomic-embed-text",
            ),
            features=FeatureConfig(
                local_ai_chat=True,
                semantic_search=True,
                ocr="manual",
                background_indexing=False,
            ),
            setup=SetupConfig(completed=True, completed_at="2026-05-30T00:00:00Z"),
        ),
    )
    monkeypatch.setattr(
        cli,
        "get_ollama_status",
        lambda: ModelRuntimeStatus(
            name="ollama",
            available=True,
            executable="ollama",
            models=("qwen3:4b",),
        ),
    )
    monkeypatch.setattr(
        cli,
        "structure_memory_with_ollama",
        lambda raw_text, *, memory_type, raw_tags, model: MemoryDraft(
            raw_text=raw_text,
            memory_type="project",
            title="Needs confirmation",
            summary="Needs confirmation.",
            tags=("confirm",),
        ),
    )
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    result = runner.invoke(
        app,
        ["capture", "--local-ai", "Confirm this draft."],
        env=env,
        input="n\n",
    )

    assert result.exit_code == 0
    assert "Save this local-AI draft?" in result.output
    assert "No memory was saved" in result.output
    assert not (tmp_path / "waymark.sqlite3").exists()


def test_capture_preview_does_not_save_memory(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    result = runner.invoke(
        app,
        ["capture", "--preview", "--type", "project", "--tag", "preview", "Preview this."],
        env=env,
    )

    assert result.exit_code == 0
    assert "Draft Memory" in result.output
    assert "Preview this." in result.output
    assert "No memory was saved" in result.output
    assert not (tmp_path / "waymark.sqlite3").exists()


def test_capture_local_ai_preview_uses_draft_without_saving(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from waymark import cli
    from waymark.config import (
        FeatureConfig,
        ModelConfig,
        PerformanceConfig,
        SetupConfig,
        WaymarkConfig,
        write_config,
    )
    from waymark.memory import MemoryDraft
    from waymark.runtime import ModelRuntimeStatus

    write_config(
        tmp_path / "config.json",
        WaymarkConfig(
            performance=PerformanceConfig(
                mode="balanced",
                max_memory_gb=8,
                max_cpu_percent=60,
                pause_on_battery=True,
                background_indexing=False,
            ),
            models=ModelConfig(
                runtime="ollama",
                chat_model="qwen3:4b",
                embedding_model="nomic-embed-text",
            ),
            features=FeatureConfig(
                local_ai_chat=True,
                semantic_search=True,
                ocr="manual",
                background_indexing=False,
            ),
            setup=SetupConfig(completed=True, completed_at="2026-05-30T00:00:00Z"),
        ),
    )

    monkeypatch.setattr(
        cli,
        "get_ollama_status",
        lambda: ModelRuntimeStatus(
            name="ollama",
            available=True,
            executable="ollama",
            models=("qwen3:4b",),
        ),
    )
    monkeypatch.setattr(
        cli,
        "structure_memory_with_ollama",
        lambda raw_text, *, memory_type, raw_tags, model: MemoryDraft(
            raw_text=raw_text,
            memory_type="project",
            title="AI preview title",
            summary="AI preview summary.",
            tags=("preview",),
        ),
    )
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    result = runner.invoke(
        app,
        ["capture", "--local-ai", "--preview", "Preview with local AI."],
        env=env,
    )

    assert result.exit_code == 0
    assert "AI preview title" in result.output
    assert "draft: local-ai:qwen3:4b" in result.output
    assert "No memory was saved" in result.output
    assert not (tmp_path / "waymark.sqlite3").exists()


def test_capture_local_ai_falls_back_without_config(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from waymark import cli

    monkeypatch.setattr(
        cli,
        "get_ollama_status",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected Ollama check")),
    )
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    result = runner.invoke(
        app,
        ["capture", "--local-ai", "No config should still save."],
        env=env,
    )

    assert result.exit_code == 0
    assert "config is missing" in result.output
    assert "No config should still save." in result.output
    assert list_entries(tmp_path / "waymark.sqlite3")[0].title == "No config should still save."


def test_capture_local_ai_reports_missing_chat_model(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from waymark import cli
    from waymark.config import (
        FeatureConfig,
        ModelConfig,
        PerformanceConfig,
        SetupConfig,
        WaymarkConfig,
        write_config,
    )
    from waymark.runtime import ModelRuntimeStatus

    write_config(
        tmp_path / "config.json",
        WaymarkConfig(
            performance=PerformanceConfig(
                mode="balanced",
                max_memory_gb=8,
                max_cpu_percent=60,
                pause_on_battery=True,
                background_indexing=False,
            ),
            models=ModelConfig(
                runtime="ollama",
                chat_model="qwen3:4b",
                embedding_model="nomic-embed-text",
            ),
            features=FeatureConfig(
                local_ai_chat=True,
                semantic_search=True,
                ocr="manual",
                background_indexing=False,
            ),
            setup=SetupConfig(completed=True, completed_at="2026-05-30T00:00:00Z"),
        ),
    )
    monkeypatch.setattr(
        cli,
        "get_ollama_status",
        lambda: ModelRuntimeStatus(
            name="ollama",
            available=True,
            executable="ollama",
            models=("nomic-embed-text:latest",),
        ),
    )
    monkeypatch.setattr(
        cli,
        "structure_memory_with_ollama",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected model call")),
    )
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    result = runner.invoke(
        app,
        ["capture", "--local-ai", "Missing model should still save."],
        env=env,
    )

    assert result.exit_code == 0
    assert "ollama pull qwen3:4b" in result.output
    assert "draft: fallback" in result.output
    assert list_entries(tmp_path / "waymark.sqlite3")[0].title == "Missing model should still save."


def test_reflect_cli_generates_and_saves_reflection(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    capture_result = runner.invoke(
        app,
        [
            "capture",
            "--type",
            "project",
            "Built the reflection command.",
        ],
        env=env,
    )
    assert capture_result.exit_code == 0

    reflect_result = runner.invoke(app, ["reflect", "--period", "today", "--save"], env=env)

    assert reflect_result.exit_code == 0
    assert "Reflection" in reflect_result.output
    assert "Saved reflection #1" in reflect_result.output
    assert "#1 Built the reflection command." in reflect_result.output

    list_result = runner.invoke(app, ["reflections", "list"], env=env)
    assert list_result.exit_code == 0
    assert "Saved Reflections" in list_result.output

    show_result = runner.invoke(app, ["reflections", "show", "1"], env=env)
    assert show_result.exit_code == 0
    assert "Saved Reflection #1" in show_result.output
    assert "#1 Built the reflection command." in show_result.output


def test_reflect_cli_skips_duplicate_save_without_force(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    capture_result = runner.invoke(app, ["capture", "Duplicate reflection memory."], env=env)
    assert capture_result.exit_code == 0
    first_result = runner.invoke(app, ["reflect", "--period", "today", "--save"], env=env)
    second_result = runner.invoke(app, ["reflect", "--period", "today", "--save"], env=env)
    list_result = runner.invoke(app, ["reflections", "list"], env=env)

    assert first_result.exit_code == 0
    assert second_result.exit_code == 0
    assert "already saved as #1" in second_result.output
    assert list_result.output.count("today") == 1


def test_reflect_cli_force_allows_duplicate_save(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    capture_result = runner.invoke(app, ["capture", "Forced reflection memory."], env=env)
    assert capture_result.exit_code == 0
    first_result = runner.invoke(app, ["reflect", "--period", "today", "--save"], env=env)
    second_result = runner.invoke(
        app,
        ["reflect", "--period", "today", "--save", "--force"],
        env=env,
    )

    assert first_result.exit_code == 0
    assert second_result.exit_code == 0
    assert "Saved reflection #2" in second_result.output


def test_models_list_is_read_only_when_ollama_missing(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from waymark import runtime

    monkeypatch.setattr(runtime, "find_ollama_executable", lambda: None)
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    result = runner.invoke(app, ["models", "list"], env=env)

    assert result.exit_code == 0
    assert "not found" in result.output
    assert "No models were downloaded" in result.output


def test_models_check_reports_configured_model_statuses(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from waymark import cli
    from waymark.config import (
        FeatureConfig,
        ModelConfig,
        PerformanceConfig,
        SetupConfig,
        WaymarkConfig,
        write_config,
    )
    from waymark.runtime import ModelRuntimeStatus

    write_config(
        tmp_path / "config.json",
        WaymarkConfig(
            performance=PerformanceConfig(
                mode="balanced",
                max_memory_gb=8,
                max_cpu_percent=60,
                pause_on_battery=True,
                background_indexing=False,
            ),
            models=ModelConfig(
                runtime="ollama",
                chat_model="qwen3:4b",
                embedding_model="nomic-embed-text",
            ),
            features=FeatureConfig(
                local_ai_chat=True,
                semantic_search=True,
                ocr="manual",
                background_indexing=False,
            ),
            setup=SetupConfig(completed=True, completed_at="2026-05-30T00:00:00Z"),
        ),
    )
    monkeypatch.setattr(
        cli,
        "get_ollama_status",
        lambda: ModelRuntimeStatus(
            name="ollama",
            available=True,
            executable="ollama",
            models=("nomic-embed-text:latest",),
        ),
    )
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    result = runner.invoke(app, ["models", "check"], env=env)

    assert result.exit_code == 0
    assert "Configured Models" in result.output
    assert "ollama pull qwen3:4b" in result.output
    assert "already present" in result.output
    assert "No models were downloaded" in result.output


def test_models_check_reports_missing_config(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}

    result = runner.invoke(app, ["models", "check"], env=env)

    assert result.exit_code == 0
    assert "waymark setup --apply" in result.output
    assert "No models were downloaded" in result.output


def test_embeddings_backfill_previews_without_generating(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from waymark import cli
    from waymark.config import (
        FeatureConfig,
        ModelConfig,
        PerformanceConfig,
        SetupConfig,
        WaymarkConfig,
        write_config,
    )

    write_config(
        tmp_path / "config.json",
        WaymarkConfig(
            performance=PerformanceConfig(
                mode="balanced",
                max_memory_gb=8,
                max_cpu_percent=60,
                pause_on_battery=True,
                background_indexing=False,
            ),
            models=ModelConfig(
                runtime="ollama",
                chat_model="qwen3:4b",
                embedding_model="nomic-embed-text",
            ),
            features=FeatureConfig(
                local_ai_chat=True,
                semantic_search=True,
                ocr="manual",
                background_indexing=False,
            ),
            setup=SetupConfig(completed=True, completed_at="2026-05-30T00:00:00Z"),
        ),
    )
    monkeypatch.setattr(
        cli,
        "embed_text_with_ollama",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected embed call")),
    )
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}
    capture_result = runner.invoke(app, ["capture", "Needs an embedding."], env=env)
    assert capture_result.exit_code == 0

    result = runner.invoke(app, ["embeddings", "backfill"], env=env)

    assert result.exit_code == 0
    assert "Embedding Backfill" in result.output
    assert "Needs an embedding." in result.output
    assert "No embeddings were generated" in result.output
    assert (
        get_entry_embedding(
            tmp_path / "waymark.sqlite3",
            entry_id=1,
            model="nomic-embed-text",
        )
        is None
    )


def test_embeddings_backfill_apply_generates_vectors(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from waymark import cli
    from waymark.config import (
        FeatureConfig,
        ModelConfig,
        PerformanceConfig,
        SetupConfig,
        WaymarkConfig,
        write_config,
    )
    from waymark.runtime import ModelRuntimeStatus

    write_config(
        tmp_path / "config.json",
        WaymarkConfig(
            performance=PerformanceConfig(
                mode="balanced",
                max_memory_gb=8,
                max_cpu_percent=60,
                pause_on_battery=True,
                background_indexing=False,
            ),
            models=ModelConfig(
                runtime="ollama",
                chat_model="qwen3:4b",
                embedding_model="nomic-embed-text",
            ),
            features=FeatureConfig(
                local_ai_chat=True,
                semantic_search=True,
                ocr="manual",
                background_indexing=False,
            ),
            setup=SetupConfig(completed=True, completed_at="2026-05-30T00:00:00Z"),
        ),
    )
    monkeypatch.setattr(
        cli,
        "get_ollama_status",
        lambda: ModelRuntimeStatus(
            name="ollama",
            available=True,
            executable="ollama",
            models=("nomic-embed-text:latest",),
        ),
    )
    monkeypatch.setattr(cli, "embed_text_with_ollama", lambda text, *, model: (0.1, 0.2))
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}
    capture_result = runner.invoke(app, ["capture", "Generate an embedding."], env=env)
    assert capture_result.exit_code == 0

    result = runner.invoke(app, ["embeddings", "backfill", "--apply"], env=env)

    assert result.exit_code == 0
    assert "Generated 1 embedding" in result.output
    embedding = get_entry_embedding(
        tmp_path / "waymark.sqlite3",
        entry_id=1,
        model="nomic-embed-text",
    )
    assert embedding is not None
    assert embedding.vector == (0.1, 0.2)


def test_ask_semantic_uses_generated_embeddings(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from waymark import cli
    from waymark.runtime import ModelRuntimeStatus

    write_ollama_embedding_config(tmp_path)
    monkeypatch.setattr(
        cli,
        "get_ollama_status",
        lambda: ModelRuntimeStatus(
            name="ollama",
            available=True,
            executable="ollama",
            models=("nomic-embed-text:latest",),
        ),
    )
    monkeypatch.setattr(cli, "embed_text_with_ollama", lambda text, *, model: (1.0, 0.0))
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}
    capture_result = runner.invoke(
        app,
        ["capture", "Semantic retrieval should cite local project memory."],
        env=env,
    )
    assert capture_result.exit_code == 0
    db_path = tmp_path / "waymark.sqlite3"
    assert upsert_entry_embedding(
        db_path,
        entry_id=1,
        model="nomic-embed-text",
        vector=(0.95, 0.05),
    )

    result = runner.invoke(app, ["ask", "how should retrieval work?", "--semantic"], env=env)

    assert result.exit_code == 0
    assert "Grounded Answer" in result.output
    assert "Semantic source matches" in result.output
    assert "Semantic retrieval should cite local project memory." in result.output
    assert "keyword" in result.output
    assert "semantic" in result.output
    assert "score" in result.output


def test_ask_semantic_without_embeddings_points_to_backfill(tmp_path: Path) -> None:
    write_ollama_embedding_config(tmp_path)
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path)}
    capture_result = runner.invoke(app, ["capture", "No vector has been generated."], env=env)
    assert capture_result.exit_code == 0

    result = runner.invoke(app, ["ask", "anything", "--semantic"], env=env)

    assert result.exit_code == 0
    assert "No semantic matches found" in result.output
    assert "waymark embeddings backfill --apply" in result.output


def test_import_markdown_cli_imports_one_file(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path / "home")}
    markdown_path = tmp_path / "note.md"
    markdown_path.write_text(
        "# CLI Import\n\nImported through the command line.",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["import", "markdown", str(markdown_path)], env=env)

    assert result.exit_code == 0
    assert "Imported Markdown" in result.output
    assert "CLI Import" in result.output

    sources_result = runner.invoke(app, ["sources", "list"], env=env)
    assert sources_result.exit_code == 0
    assert "note.md" in sources_result.output

    ask_result = runner.invoke(app, ["ask", "command line"], env=env)
    assert ask_result.exit_code == 0
    assert "markdown: note.md" in ask_result.output


def test_import_markdown_cli_skips_duplicate_without_force(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path / "home")}
    markdown_path = tmp_path / "note.md"
    markdown_path.write_text("# CLI Import\n\nImport once.", encoding="utf-8")

    first_result = runner.invoke(app, ["import", "markdown", str(markdown_path)], env=env)
    second_result = runner.invoke(app, ["import", "markdown", str(markdown_path)], env=env)
    forced_result = runner.invoke(
        app,
        ["import", "markdown", str(markdown_path), "--force"],
        env=env,
    )

    assert first_result.exit_code == 0
    assert second_result.exit_code == 0
    assert "already imported" in second_result.output
    assert forced_result.exit_code == 0

    sources = list_sources(tmp_path / "home" / "waymark.sqlite3", limit=10)
    assert len(sources) == 2


def test_import_text_cli_imports_one_file_and_skips_duplicates(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path / "home")}
    text_path = tmp_path / "note.txt"
    text_path.write_text(
        "CLI text import\n\nImported through the text command.",
        encoding="utf-8",
    )

    first_result = runner.invoke(app, ["import", "text", str(text_path)], env=env)
    second_result = runner.invoke(app, ["import", "text", str(text_path)], env=env)

    assert first_result.exit_code == 0
    assert "Imported Text" in first_result.output
    assert "CLI text import" in first_result.output
    assert second_result.exit_code == 0
    assert "already imported" in second_result.output

    sources_result = runner.invoke(app, ["sources", "list"], env=env)
    assert sources_result.exit_code == 0
    assert "text" in sources_result.output
    assert "note.txt" in sources_result.output


def test_import_docx_cli_imports_one_file_and_skips_duplicates(
    tmp_path: Path, make_docx: Callable[[Path, list[str]], Path]
) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path / "home")}
    docx_path = make_docx(
        tmp_path / "note.docx",
        ["CLI docx import", "Imported through the docx command."],
    )

    first_result = runner.invoke(app, ["import", "docx", str(docx_path)], env=env)
    second_result = runner.invoke(app, ["import", "docx", str(docx_path)], env=env)

    assert first_result.exit_code == 0
    assert "Imported DOCX" in first_result.output
    assert "CLI docx import" in first_result.output
    assert second_result.exit_code == 0
    assert "already imported" in second_result.output

    sources_result = runner.invoke(app, ["sources", "list"], env=env)
    assert sources_result.exit_code == 0
    assert "docx" in sources_result.output
    assert "note.docx" in sources_result.output


def test_import_pdf_cli_preview_does_not_save(
    tmp_path: Path, make_minimal_pdf: Callable[[Path, str], Path]
) -> None:
    pytest.importorskip("pypdf")
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path / "home")}
    pdf_path = make_minimal_pdf(tmp_path / "note.pdf", "Hello Waymark")

    result = runner.invoke(app, ["import", "pdf", str(pdf_path), "--preview"], env=env)

    assert result.exit_code == 0
    assert "PDF Preview" in result.output
    assert "not saved" in result.output

    sources_result = runner.invoke(app, ["sources", "list"], env=env)
    assert sources_result.exit_code == 0
    assert "No imported sources yet" in sources_result.output


def test_import_pdf_cli_imports_one_file(
    tmp_path: Path, make_minimal_pdf: Callable[[Path, str], Path]
) -> None:
    pytest.importorskip("pypdf")
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path / "home")}
    pdf_path = make_minimal_pdf(tmp_path / "note.pdf", "Hello Waymark")

    result = runner.invoke(app, ["import", "pdf", str(pdf_path)], env=env)

    assert result.exit_code == 0
    assert "Imported PDF" in result.output

    sources_result = runner.invoke(app, ["sources", "list"], env=env)
    assert sources_result.exit_code == 0
    assert "pdf" in sources_result.output
    assert "note.pdf" in sources_result.output


def test_import_markdown_folder_cli_previews_without_importing(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path / "home")}
    notes_path = tmp_path / "notes"
    notes_path.mkdir()
    (notes_path / "alpha.md").write_text("# Alpha\n\nPreview-only note.", encoding="utf-8")

    result = runner.invoke(app, ["import", "markdown-folder", str(notes_path)], env=env)

    assert result.exit_code == 0
    assert "Markdown Folder Preview" in result.output
    assert "Alpha" in result.output
    assert "No files were imported" in result.output

    sources_result = runner.invoke(app, ["sources", "list"], env=env)
    assert sources_result.exit_code == 0
    assert "No imported sources yet" in sources_result.output


def test_import_markdown_folder_cli_applies_explicitly(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path / "home")}
    notes_path = tmp_path / "notes"
    notes_path.mkdir()
    (notes_path / "alpha.md").write_text("# Alpha\n\nFirst imported note.", encoding="utf-8")
    (notes_path / "beta.markdown").write_text("# Beta\n\nSecond imported note.", encoding="utf-8")

    result = runner.invoke(
        app,
        ["import", "markdown-folder", str(notes_path), "--apply"],
        env=env,
    )

    assert result.exit_code == 0
    assert "Imported 2 Markdown file" in result.output

    sources_result = runner.invoke(app, ["sources", "list"], env=env)
    assert sources_result.exit_code == 0
    assert "alpha.md" in sources_result.output
    assert "beta.markdown" in sources_result.output

    ask_result = runner.invoke(app, ["ask", "First imported"], env=env)
    assert ask_result.exit_code == 0
    assert "markdown: alpha.md" in ask_result.output


def test_import_markdown_folder_cli_skips_duplicates(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path / "home")}
    notes_path = tmp_path / "notes"
    notes_path.mkdir()
    (notes_path / "alpha.md").write_text("# Alpha\n\nFirst imported note.", encoding="utf-8")

    first_result = runner.invoke(
        app,
        ["import", "markdown-folder", str(notes_path), "--apply"],
        env=env,
    )
    second_result = runner.invoke(
        app,
        ["import", "markdown-folder", str(notes_path), "--apply"],
        env=env,
    )

    assert first_result.exit_code == 0
    assert "Imported 1 Markdown file" in first_result.output
    assert second_result.exit_code == 0
    assert "Imported 0 Markdown file" in second_result.output
    assert "already imported" in second_result.output


def test_import_folder_cli_previews_without_importing(
    tmp_path: Path, make_docx: Callable[[Path, list[str]], Path]
) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path / "home")}
    folder = tmp_path / "mixed"
    folder.mkdir()
    (folder / "a-note.md").write_text("# Alpha\n\nPreview note.", encoding="utf-8")
    make_docx(folder / "b-note.docx", ["BetaDoc", "Doc body."])

    result = runner.invoke(app, ["import", "folder", str(folder)], env=env)

    assert result.exit_code == 0
    assert "Folder Preview" in result.output
    assert "Alpha" in result.output
    assert "BetaDoc" in result.output
    assert "No files were imported" in result.output

    sources_result = runner.invoke(app, ["sources", "list"], env=env)
    assert sources_result.exit_code == 0
    assert "No imported sources yet" in sources_result.output


def test_import_folder_cli_applies_all_supported_types(
    tmp_path: Path, make_docx: Callable[[Path, list[str]], Path]
) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path / "home")}
    folder = tmp_path / "mixed"
    folder.mkdir()
    (folder / "a-note.md").write_text("# Alpha\n\nApplied note.", encoding="utf-8")
    (folder / "b-note.txt").write_text("Bravo\n\nApplied text.", encoding="utf-8")
    make_docx(folder / "c-note.docx", ["CharlieDoc", "Applied doc."])

    result = runner.invoke(app, ["import", "folder", str(folder), "--apply"], env=env)

    assert result.exit_code == 0
    assert "Imported Folder" in result.output
    assert "Imported 3 file(s)." in result.output

    sources_result = runner.invoke(app, ["sources", "list"], env=env)
    assert sources_result.exit_code == 0
    for source_type in ("markdown", "text", "docx"):
        assert source_type in sources_result.output


def test_backup_cli_create_info_and_restore_roundtrip(tmp_path: Path) -> None:
    runner = CliRunner()
    env_a = {"WAYMARK_HOME": str(tmp_path / "home-a")}
    note = tmp_path / "note.txt"
    note.write_text("Backup me\n\nThis memory should survive a backup.", encoding="utf-8")
    assert runner.invoke(app, ["import", "text", str(note)], env=env_a).exit_code == 0

    backup_file = tmp_path / "waymark-backup.json"
    create = runner.invoke(app, ["backup", "create", str(backup_file)], env=env_a)
    assert create.exit_code == 0
    assert "Backup created" in create.output
    assert backup_file.exists()

    info = runner.invoke(app, ["backup", "info", str(backup_file)], env=env_a)
    assert info.exit_code == 0
    assert "Backup contents" in info.output

    env_b = {"WAYMARK_HOME": str(tmp_path / "home-b")}
    restore = runner.invoke(app, ["backup", "restore", str(backup_file)], env=env_b)
    assert restore.exit_code == 0
    assert "Restored" in restore.output

    timeline = runner.invoke(app, ["timeline"], env=env_b)
    assert timeline.exit_code == 0
    assert "Backup me" in timeline.output


def test_backup_restore_cli_refuses_existing_home_without_force(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path / "home")}
    note = tmp_path / "note.txt"
    note.write_text("First memory\n\nBody text.", encoding="utf-8")
    runner.invoke(app, ["import", "text", str(note)], env=env)

    backup_file = tmp_path / "backup.json"
    runner.invoke(app, ["backup", "create", str(backup_file)], env=env)

    blocked = runner.invoke(app, ["backup", "restore", str(backup_file)], env=env)
    assert blocked.exit_code == 1
    assert "already holds" in blocked.output

    forced = runner.invoke(app, ["backup", "restore", str(backup_file), "--force"], env=env)
    assert forced.exit_code == 0
    assert "Restored" in forced.output


def test_export_memory_cli_writes_markdown_and_refuses_overwrite(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path / "home")}
    output_path = tmp_path / "memory.md"

    capture_result = runner.invoke(
        app,
        ["capture", "--type", "project", "--tag", "export", "Export this memory."],
        env=env,
    )
    assert capture_result.exit_code == 0

    export_result = runner.invoke(
        app,
        ["export", "memory", "1", str(output_path)],
        env=env,
    )

    assert export_result.exit_code == 0
    assert "Wrote Markdown export" in export_result.output
    content = output_path.read_text(encoding="utf-8")
    assert "# Export this memory." in content
    assert "- Type: project" in content
    assert "- Tags: export" in content

    overwrite_result = runner.invoke(
        app,
        ["export", "memory", "1", str(output_path)],
        env=env,
    )
    assert overwrite_result.exit_code == 1
    assert "already exists" in overwrite_result.output

    force_result = runner.invoke(
        app,
        ["export", "memory", "1", str(output_path), "--force"],
        env=env,
    )
    assert force_result.exit_code == 0


def test_export_timeline_cli_writes_recent_memories(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WAYMARK_HOME": str(tmp_path / "home")}
    output_path = tmp_path / "timeline.md"

    first_result = runner.invoke(app, ["capture", "First exportable memory."], env=env)
    second_result = runner.invoke(app, ["capture", "Second exportable memory."], env=env)
    assert first_result.exit_code == 0
    assert second_result.exit_code == 0

    export_result = runner.invoke(
        app,
        ["export", "timeline", str(output_path), "--limit", "10"],
        env=env,
    )

    assert export_result.exit_code == 0
    assert "Wrote Markdown timeline" in export_result.output
    content = output_path.read_text(encoding="utf-8")
    assert "# Waymark Timeline" in content
    assert "First exportable memory." in content
    assert "Second exportable memory." in content


def test_export_reflection_cli_writes_saved_reflection(tmp_path: Path) -> None:
    runner = CliRunner()
    home = tmp_path / "home"
    env = {"WAYMARK_HOME": str(home)}
    output_path = tmp_path / "reflection.md"

    init_result = runner.invoke(app, ["capture", "Initialize reflection export."], env=env)
    assert init_result.exit_code == 0
    reflection_id = add_reflection(
        home / "waymark.sqlite3",
        period_type="week",
        period_start="2026-05-24",
        period_end="2026-05-30",
        summary="A saved reflection worth exporting.",
        wins=("#1 Captured export context.",),
        patterns=("Export work is recurring.",),
        suggestions=("Review the exported summary.",),
    )

    export_result = runner.invoke(
        app,
        ["export", "reflection", str(reflection_id), str(output_path)],
        env=env,
    )

    assert export_result.exit_code == 0
    assert "Wrote Markdown reflection" in export_result.output
    content = output_path.read_text(encoding="utf-8")
    assert "# Saved Reflection #1" in content
    assert "- Period: week" in content
    assert "A saved reflection worth exporting." in content
    assert "- #1 Captured export context." in content


def test_export_reflection_trends_cli_writes_trend_summary(tmp_path: Path) -> None:
    runner = CliRunner()
    home = tmp_path / "home"
    env = {"WAYMARK_HOME": str(home)}
    output_path = tmp_path / "reflection-trends.md"

    init_result = runner.invoke(app, ["capture", "Initialize trend export."], env=env)
    assert init_result.exit_code == 0
    add_reflection(
        home / "waymark.sqlite3",
        period_type="week",
        period_start="2026-05-17",
        period_end="2026-05-23",
        summary="Previous saved week.",
        patterns=("Project captures repeated.",),
        suggestions=("Review the top project theme.",),
    )
    add_reflection(
        home / "waymark.sqlite3",
        period_type="week",
        period_start="2026-05-24",
        period_end="2026-05-30",
        summary="Current saved week.",
        patterns=("Project captures repeated.",),
        suggestions=("Review the top project theme.",),
    )

    export_result = runner.invoke(
        app,
        ["export", "reflection-trends", str(output_path), "--period", "week"],
        env=env,
    )

    assert export_result.exit_code == 0
    assert "Wrote Markdown reflection trends" in export_result.output
    content = output_path.read_text(encoding="utf-8")
    assert "# Waymark Reflection Trends" in content
    assert "Saved Reflection Trends (week)" in content
    assert "Saved reflections: 2" in content
    assert "- Project captures repeated. (2)" in content


def test_export_reflection_trends_cli_supports_memory_scope(tmp_path: Path) -> None:
    runner = CliRunner()
    home = tmp_path / "home"
    env = {"WAYMARK_HOME": str(home)}
    output_path = tmp_path / "scoped-reflection-trends.md"
    today = datetime.now(UTC).date().isoformat()

    capture_result = runner.invoke(
        app,
        ["capture", "--type", "project", "--tag", "focus", "Scoped export trend source."],
        env=env,
    )
    assert capture_result.exit_code == 0
    add_reflection(
        home / "waymark.sqlite3",
        period_type="week",
        period_start=today,
        period_end=today,
        summary="Matching exported week.",
        patterns=("Scoped export pattern.",),
        suggestions=("Review scoped export.",),
    )
    add_reflection(
        home / "waymark.sqlite3",
        period_type="week",
        period_start="2000-01-01",
        period_end="2000-01-07",
        summary="Unmatched exported week.",
        patterns=("Unmatched pattern.",),
        suggestions=("Review unmatched export.",),
    )

    export_result = runner.invoke(
        app,
        [
            "export",
            "reflection-trends",
            str(output_path),
            "--period",
            "week",
            "--tag",
            "focus",
            "--type",
            "project",
        ],
        env=env,
    )

    assert export_result.exit_code == 0
    content = output_path.read_text(encoding="utf-8")
    assert "Memory scope: tags: focus; types: project" in content
    assert "Matching exported week." in content
    assert "Unmatched exported week." not in content
