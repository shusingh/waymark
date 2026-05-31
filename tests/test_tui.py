from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pytest import MonkeyPatch
from textual.widgets import Button, Input, Static, TextArea

from waymark.runtime import ModelRuntimeStatus
from waymark.storage import (
    add_decision,
    add_entry,
    add_reflection,
    init_database,
    link_decision_entry,
    list_decisions,
    list_entries,
    list_reflections,
)
from waymark.system import CapabilityRecommendation, SystemProfile
from waymark.tui import WaymarkApp


def test_tui_capture_flow_saves_memory(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#capture"))
            await pilot.pause(0.2)
            app.screen.query_one("#memory-type", Input).value = "project"
            app.screen.query_one("#memory-tags", Input).value = "project, tui"
            app.screen.query_one("#memory-text", TextArea).text = (
                "Captured a memory from the Textual pilot."
            )
            await pilot.click(app.screen.query_one("#draft"))
            await pilot.pause(0.2)
            assert app.screen.query_one("#save", Button).disabled is False
            await pilot.click(app.screen.query_one("#save"))
            await pilot.pause(0.2)

        entries = list_entries(db_path)
        assert len(entries) == 1
        assert entries[0].title == "Captured a memory from the Textual pilot."
        assert entries[0].tags == ("project", "tui")

    asyncio.run(run_flow())


def test_tui_capture_discard_does_not_save(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#capture"))
            await pilot.pause(0.2)
            app.screen.query_one("#memory-type", Input).value = "project"
            app.screen.query_one("#memory-text", TextArea).text = "Discard this draft."
            await pilot.click(app.screen.query_one("#draft"))
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#discard"))
            await pilot.pause(0.2)

        assert list_entries(db_path) == []

    asyncio.run(run_flow())


def test_tui_ask_uses_grounded_answer_and_tags(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        init_database(db_path)
        add_entry(
            db_path,
            raw_text="This guided result uses different words.",
            memory_type="project",
            title="Tagged guided memory",
            summary="A guided memory found through its tag.",
            tags=("local-first",),
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#ask"))
            await pilot.pause(0.2)
            app.screen.query_one("#ask-query", Input).value = "local first"
            await pilot.press("enter")
            await pilot.pause(0.2)

            result_text = str(app.screen.query_one("#ask-results", Static).content)
            assert "Grounded answer" in result_text
            assert "A guided memory found through its tag." in result_text
            assert "#1" in result_text

    asyncio.run(run_flow())


def test_tui_journey_map_shows_memory_health(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        init_database(db_path)
        add_entry(
            db_path,
            raw_text="A guided journey memory.",
            memory_type="project",
            title="Journey memory",
            summary="A journey map source memory.",
            tags=("journey",),
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("j")
            await pilot.pause(0.2)

            journey_text = str(app.screen.query_one("#journey-map", Static).content)
            assert "Memory Health" in journey_text
            assert "Total memories: 1" in journey_text
            assert "journey (1)" in journey_text
            assert "Capture one" in journey_text

    asyncio.run(run_flow())


def test_tui_journey_prompt_opens_prefilled_capture(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        init_database(db_path)
        add_entry(
            db_path,
            raw_text="A project memory already exists.",
            memory_type="project",
            title="Project memory",
            summary="A project source memory.",
            tags=("journey",),
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("j")
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#journey-capture-0"))
            await pilot.pause(0.2)

            assert app.screen.query_one("#memory-type", Input).value == "daily"
            memory_text = app.screen.query_one("#memory-text", TextArea).text
            assert "Capture one ordinary detail" in memory_text

    asyncio.run(run_flow())


def test_tui_journey_reflection_opens_prefilled_reflect(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        init_database(db_path)
        add_entry(
            db_path,
            raw_text="A recent memory for reflection.",
            memory_type="daily",
            title="Recent memory",
            summary="A current memory.",
            tags=("journey",),
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("j")
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#journey-reflect-0"))
            await pilot.pause(0.2)

            assert app.screen.query_one("#reflect-period", Input).value == "today"

    asyncio.run(run_flow())


def test_tui_reflect_due_windows_shows_queue(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        init_database(db_path)
        add_entry(
            db_path,
            raw_text="A memory for reflection queue.",
            memory_type="daily",
            title="Reflection queue memory",
            summary="A reflection queue source.",
            tags=("reflection",),
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#reflect"))
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#reflection-due"))
            await pilot.pause(0.2)

            preview = str(app.screen.query_one("#reflection-preview", Static).content)
            status = str(app.screen.query_one("#reflection-status", Static).content)
            assert "Reflection Windows" in preview
            assert "waymark reflect --period" in preview
            assert "Loaded reflection queue" in status
            assert app.screen.query_one("#reflect-period", Input).value == "today"

    asyncio.run(run_flow())


def test_tui_reflect_generate_due_previews_first_window(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        init_database(db_path)
        add_entry(
            db_path,
            raw_text="A memory for generate due.",
            memory_type="daily",
            title="Generate due memory",
            summary="A generate due source.",
            tags=("reflection",),
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#reflect"))
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#generate-due-reflection"))
            await pilot.pause(0.2)

            preview = str(app.screen.query_one("#reflection-preview", Static).content)
            status = str(app.screen.query_one("#reflection-status", Static).content)
            assert "Today Reflection" in preview
            assert "Generated first due reflection: today" in status
            assert app.screen.query_one("#reflect-period", Input).value == "today"
            assert app.screen.query_one("#save-reflection", Button).disabled is False

    asyncio.run(run_flow())


def test_tui_reflect_compare_shows_saved_period_context(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        init_database(db_path)
        add_entry(
            db_path,
            raw_text="A memory for reflection comparison.",
            memory_type="daily",
            title="Comparison memory",
            summary="A comparison source.",
            tags=("reflection",),
        )
        add_reflection(
            db_path,
            period_type="week",
            period_start="2000-01-01",
            period_end="2000-01-07",
            summary="Older saved week.",
            wins=("#99 Older win",),
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(150, 46)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#reflect"))
            await pilot.pause(0.2)
            app.screen.query_one("#reflect-period", Input).value = "week"
            await pilot.click(app.screen.query_one("#compare-reflection"))
            await pilot.pause(0.2)

            preview = str(app.screen.query_one("#reflection-preview", Static).content)
            status = str(app.screen.query_one("#reflection-status", Static).content)
            assert "Reflection Comparison" in preview
            assert "Latest saved: #1 2000-01-01 to 2000-01-07" in preview
            assert "Reflection comparison loaded" in status

    asyncio.run(run_flow())


def test_tui_reflect_trends_shows_saved_reflection_patterns(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        init_database(db_path)
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
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#reflect"))
            await pilot.pause(0.2)
            app.screen.query_one("#reflect-period", Input).value = "week"
            await pilot.click(app.screen.query_one("#reflection-trends"))
            await pilot.pause(0.2)

            preview = str(app.screen.query_one("#reflection-preview", Static).content)
            status = str(app.screen.query_one("#reflection-status", Static).content)
            assert "Saved Reflection Trends (week)" in preview
            assert "Repeated patterns" in preview
            assert "Reflection trends loaded" in status

    asyncio.run(run_flow())


def test_tui_reflect_trends_supports_scope_filters(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        today = datetime.now(UTC).date().isoformat()
        init_database(db_path)
        add_entry(
            db_path,
            raw_text="A scoped trend source.",
            memory_type="project",
            title="Scoped trend source",
            summary="Scoped trend source.",
            tags=("focus",),
        )
        add_reflection(
            db_path,
            period_type="week",
            period_start=today,
            period_end=today,
            summary="Matching scoped week.",
            patterns=("Scoped project pattern.",),
            suggestions=("Review scoped project.",),
        )
        add_reflection(
            db_path,
            period_type="week",
            period_start="2000-01-01",
            period_end="2000-01-07",
            summary="Unmatched old week.",
            patterns=("Old pattern.",),
            suggestions=("Review old week.",),
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#reflect"))
            await pilot.pause(0.2)
            app.screen.query_one("#reflect-period", Input).value = "week"
            app.screen.query_one("#reflection-trend-tags", Input).value = "focus"
            app.screen.query_one("#reflection-trend-types", Input).value = "project"
            await pilot.click(app.screen.query_one("#reflection-trends"))
            await pilot.pause(0.2)

            preview = str(app.screen.query_one("#reflection-preview", Static).content)
            assert "Memory scope: tags: focus; types: project" in preview
            assert "Matching scoped week." in preview
            assert "Unmatched old week." not in preview

    asyncio.run(run_flow())


def test_tui_capture_can_use_local_ai_draft(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from waymark import tui
    from waymark.config import (
        FeatureConfig,
        ModelConfig,
        PerformanceConfig,
        SetupConfig,
        WaymarkConfig,
        write_config,
    )
    from waymark.memory import MemoryDraft

    home_path = tmp_path / "home"
    monkeypatch.setenv("WAYMARK_HOME", str(home_path))
    write_config(
        home_path / "config.json",
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

    def fake_structure_memory_with_ollama(
        raw_text: str,
        *,
        memory_type: str,
        raw_tags: str,
        model: str,
    ) -> MemoryDraft:
        assert raw_text == "Captured with local AI in the guided flow."
        assert memory_type == "daily"
        assert raw_tags == "guided"
        assert model == "qwen3:4b"
        return MemoryDraft(
            raw_text=raw_text,
            memory_type="project",
            title="Guided AI title",
            summary="Guided AI summary.",
            tags=("guided", "local-ai"),
        )

    monkeypatch.setattr(tui, "structure_memory_with_ollama", fake_structure_memory_with_ollama)
    monkeypatch.setattr(
        tui,
        "get_ollama_status",
        lambda: ModelRuntimeStatus(
            name="ollama",
            available=True,
            executable="ollama",
            models=("qwen3:4b",),
        ),
    )

    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(150, 44)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#capture"))
            await pilot.pause(0.2)
            app.screen.query_one("#memory-tags", Input).value = "guided"
            app.screen.query_one("#capture-local-ai", Input).value = "yes"
            app.screen.query_one("#memory-text", TextArea).text = (
                "Captured with local AI in the guided flow."
            )
            await pilot.click(app.screen.query_one("#draft"))
            await pilot.pause(0.2)
            preview = app.screen.query_one("#draft-preview", Static).content
            status = app.screen.query_one("#capture-status", Static).content
            assert "Guided AI title" in str(preview)
            assert "Drafted with local-ai:qwen3:4b" in str(status)

            await pilot.click(app.screen.query_one("#save"))
            await pilot.pause(0.2)

        entries = list_entries(db_path)
        assert len(entries) == 1
        assert entries[0].title == "Guided AI title"
        assert entries[0].tags == ("guided", "local-ai")

    asyncio.run(run_flow())


def test_tui_decision_flow_saves_open_decision(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(140, 42)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#decisions"))
            await pilot.pause(0.2)
            app.screen.query_one("#decision-title", Input).value = "Build CLI first?"
            app.screen.query_one("#decision-context", TextArea).text = (
                "The memory engine matters more than UI polish."
            )
            app.screen.query_one("#decision-options", Input).value = "CLI first, desktop first"
            app.screen.query_one("#decision-confidence", Input).value = "4"
            await pilot.click(app.screen.query_one("#add-decision"))
            await pilot.pause(0.2)

        decisions = list_decisions(db_path)
        assert len(decisions) == 1
        assert decisions[0].title == "Build CLI first?"
        assert decisions[0].options == ("CLI first", "desktop first")
        assert decisions[0].confidence == 4

    asyncio.run(run_flow())


def test_tui_timeline_shows_memory_id(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        init_database(db_path)
        add_entry(
            db_path,
            raw_text="Timeline cards should show their IDs.",
            memory_type="project",
            title="Timeline ID",
            summary="Timeline cards should show their IDs.",
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#timeline"))
            await pilot.pause(0.2)
            timeline_text = str(app.screen.query_one("#timeline-list Static", Static).content)
            assert "#1  PROJECT  Timeline ID" in timeline_text

    asyncio.run(run_flow())


def test_tui_decision_flow_links_memory(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        init_database(db_path)
        entry_id = add_entry(
            db_path,
            raw_text="This memory should stay attached to the decision.",
            memory_type="project",
            title="Decision evidence",
            summary="This memory should stay attached to the decision.",
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(150, 46)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#decisions"))
            await pilot.pause(0.2)
            app.screen.query_one("#decision-title", Input).value = "Link a memory?"
            app.screen.query_one("#decision-context", TextArea).text = (
                "The decision should cite its memory context."
            )
            app.screen.query_one("#decision-memory-ids", Input).value = str(entry_id)
            await pilot.click(app.screen.query_one("#add-decision"))
            await pilot.pause(0.2)

        decisions = list_decisions(db_path)
        assert len(decisions) == 1
        assert decisions[0].entry_ids == (entry_id,)

    asyncio.run(run_flow())


def test_tui_decision_finalize_and_outcome_flow(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#decisions"))
            await pilot.pause(0.2)
            app.screen.query_one("#decision-title", Input).value = "Build CLI first?"
            app.screen.query_one("#decision-context", TextArea).text = (
                "The memory engine matters more than UI polish."
            )
            await pilot.click(app.screen.query_one("#add-decision"))
            await pilot.pause(0.2)

            app.screen.query_one("#decision-update-id", Input).value = "1"
            app.screen.query_one("#decision-final-choice", Input).value = "CLI first"
            app.screen.query_one("#decision-confidence", Input).value = "5"
            await pilot.click(app.screen.query_one("#finalize-decision"))
            await pilot.pause(0.2)

            app.screen.query_one("#decision-outcome", TextArea).text = (
                "The CLI foundation was the right first move."
            )
            await pilot.click(app.screen.query_one("#record-outcome"))
            await pilot.pause(0.2)

        decisions = list_decisions(db_path)
        assert len(decisions) == 1
        assert decisions[0].status == "reviewed"
        assert decisions[0].final_choice == "CLI first"
        assert decisions[0].confidence == 5
        assert decisions[0].outcome == "The CLI foundation was the right first move."

    asyncio.run(run_flow())


def test_tui_memory_detail_shows_linked_decision(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        init_database(db_path)
        entry_id = add_entry(
            db_path,
            raw_text="Memory detail should show this full text.",
            memory_type="project",
            title="Memory detail source",
            summary="Memory detail should show this full text.",
            tags=("detail",),
        )
        decision_id = add_decision(
            db_path,
            title="Inspect memories in TUI?",
            context="IDs should be easy to inspect.",
        )
        link_decision_entry(db_path, decision_id=decision_id, entry_id=entry_id)
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(140, 42)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#memory"))
            await pilot.pause(0.2)
            app.screen.query_one("#memory-detail-id", Input).value = str(entry_id)
            await pilot.click(app.screen.query_one("#show-memory"))
            await pilot.pause(0.2)

            detail_text = app.screen.query_one("#memory-detail-status", Static).content
            assert "Memory detail source" in str(detail_text)
            assert "Inspect memories in TUI?" in str(detail_text)

    asyncio.run(run_flow())


def test_tui_memory_detail_saves_edits(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        init_database(db_path)
        entry_id = add_entry(
            db_path,
            raw_text="Original text.",
            memory_type="daily",
            title="Original title",
            summary="Original summary.",
            tags=("old",),
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(150, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#memory"))
            await pilot.pause(0.2)
            app.screen.query_one("#memory-detail-id", Input).value = str(entry_id)
            await pilot.click(app.screen.query_one("#show-memory"))
            await pilot.pause(0.2)

            app.screen.query_one("#memory-edit-title", Input).value = "Updated title"
            app.screen.query_one("#memory-edit-type", Input).value = "project"
            app.screen.query_one("#memory-edit-tags", Input).value = "edited, project"
            app.screen.query_one("#memory-edit-summary", Input).value = "Updated summary."
            app.screen.query_one("#memory-edit-text", TextArea).text = "Updated text."
            await pilot.click(app.screen.query_one("#save-memory-edits"))
            await pilot.pause(0.2)

        entries = list_entries(db_path)
        assert len(entries) == 1
        assert entries[0].title == "Updated title"
        assert entries[0].type == "project"
        assert entries[0].summary == "Updated summary."
        assert entries[0].raw_text == "Updated text."
        assert entries[0].tags == ("edited", "project")

    asyncio.run(run_flow())


def test_tui_reflection_flow_saves_reflection(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(140, 42)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#capture"))
            await pilot.pause(0.2)
            app.screen.query_one("#memory-type", Input).value = "project"
            app.screen.query_one("#memory-text", TextArea).text = (
                "Built the guided reflection flow."
            )
            await pilot.click(app.screen.query_one("#draft"))
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#save"))
            await pilot.pause(0.2)

            await pilot.press("r")
            await pilot.pause(0.2)
            app.screen.query_one("#reflect-period", Input).value = "today"
            await pilot.click(app.screen.query_one("#generate-reflection"))
            await pilot.pause(0.2)
            assert app.screen.query_one("#save-reflection", Button).disabled is False
            await pilot.click(app.screen.query_one("#save-reflection"))
            await pilot.pause(0.2)
            assert app.screen.query_one("#save-reflection", Button).disabled is True

        reflections = list_reflections(db_path)
        assert len(reflections) == 1
        assert "memories" in reflections[0].summary

    asyncio.run(run_flow())


def test_tui_reflection_save_skips_duplicate_window(tmp_path: Path) -> None:
    async def run_flow() -> None:
        from waymark.reflection import reflection_window

        db_path = tmp_path / "waymark.sqlite3"
        init_database(db_path)
        add_entry(
            db_path,
            raw_text="Duplicate reflection source.",
            memory_type="daily",
            title="Duplicate reflection source",
            summary="Duplicate reflection source.",
            tags=(),
        )
        period_start, period_end = reflection_window("today")
        add_reflection(
            db_path,
            period_type="today",
            period_start=period_start,
            period_end=period_end,
            summary="Already saved.",
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(140, 42)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#reflect"))
            await pilot.pause(0.2)
            app.screen.query_one("#reflect-period", Input).value = "today"
            await pilot.click(app.screen.query_one("#generate-reflection"))
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#save-reflection"))
            await pilot.pause(0.2)

            status = str(app.screen.query_one("#reflection-status", Static).content)
            assert "already saved as #1" in status
            assert app.screen.query_one("#save-reflection", Button).disabled is True

        reflections = list_reflections(db_path)
        assert len(reflections) == 1

    asyncio.run(run_flow())


def test_tui_reflection_history_shows_saved_reflection(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        init_database(db_path)
        reflection_id = add_reflection(
            db_path,
            period_type="week",
            period_start="2026-05-24",
            period_end="2026-05-30",
            summary="A saved weekly reflection.",
            wins=("Built history",),
            patterns=("Reflection history exists.",),
            suggestions=("Review it later.",),
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(150, 46)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#reflect"))
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#reflection-history"))
            await pilot.pause(0.2)
            history_text = app.screen.query_one("#reflection-preview", Static).content
            assert "A saved weekly reflection." in str(history_text)

            app.screen.query_one("#saved-reflection-id", Input).value = str(reflection_id)
            await pilot.click(app.screen.query_one("#show-saved-reflection"))
            await pilot.pause(0.2)
            detail_text = app.screen.query_one("#reflection-preview", Static).content
            assert "Saved Reflection #1" in str(detail_text)
            assert "Built history" in str(detail_text)

    asyncio.run(run_flow())


def test_tui_import_markdown_flow_saves_memory(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        markdown_path = tmp_path / "note.md"
        markdown_path.write_text(
            "# Guided Import\n\nImported from the guided interface.",
            encoding="utf-8",
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(140, 42)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#import"))
            await pilot.pause(0.2)
            app.screen.query_one("#import-path", Input).value = str(markdown_path)
            await pilot.click(app.screen.query_one("#import-markdown"))
            await pilot.pause(0.2)

        entries = list_entries(db_path)
        assert len(entries) == 1
        assert entries[0].title == "Guided Import"
        assert entries[0].source == "source:1"

    asyncio.run(run_flow())


def test_tui_import_text_flow_saves_memory(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        text_path = tmp_path / "note.txt"
        text_path.write_text(
            "Guided Text Import\n\nImported from the guided text action.",
            encoding="utf-8",
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(150, 44)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#import"))
            await pilot.pause(0.2)
            app.screen.query_one("#import-path", Input).value = str(text_path)
            await pilot.click(app.screen.query_one("#import-text"))
            await pilot.pause(0.2)

        entries = list_entries(db_path)
        assert len(entries) == 1
        assert entries[0].title == "Guided Text Import"
        assert entries[0].source == "source:1"
        assert entries[0].tags == ("import", "text")

    asyncio.run(run_flow())


def test_tui_import_docx_flow_saves_memory(
    tmp_path: Path, make_docx: Callable[[Path, list[str]], Path]
) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        docx_path = make_docx(
            tmp_path / "note.docx",
            ["Guided Docx Import", "Imported from the guided docx action."],
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(150, 44)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#import"))
            await pilot.pause(0.2)
            app.screen.query_one("#import-path", Input).value = str(docx_path)
            await pilot.click(app.screen.query_one("#import-docx"))
            await pilot.pause(0.2)

        entries = list_entries(db_path)
        assert len(entries) == 1
        assert entries[0].title == "Guided Docx Import"
        assert entries[0].source == "source:1"
        assert entries[0].tags == ("docx", "import")

    asyncio.run(run_flow())


def test_tui_markdown_folder_preview_then_apply_flow(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        notes_path = tmp_path / "notes"
        notes_path.mkdir()
        (notes_path / "alpha.md").write_text("# Alpha\n\nFirst guided import.", encoding="utf-8")
        (notes_path / "beta.markdown").write_text(
            "# Beta\n\nSecond guided import.",
            encoding="utf-8",
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#import"))
            await pilot.pause(0.2)
            app.screen.query_one("#import-path", Input).value = str(notes_path)
            await pilot.click(app.screen.query_one("#preview-folder"))
            await pilot.pause(0.2)

            assert list_entries(db_path) == []
            assert app.screen.query_one("#apply-folder", Button).disabled is False

            await pilot.click(app.screen.query_one("#apply-folder"))
            await pilot.pause(0.2)

        entries = list_entries(db_path)
        assert sorted(entry.title for entry in entries) == ["Alpha", "Beta"]

    asyncio.run(run_flow())


def test_tui_folder_import_handles_mixed_types(
    tmp_path: Path, make_docx: Callable[[Path, list[str]], Path]
) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        folder = tmp_path / "mixed"
        folder.mkdir()
        (folder / "a-note.md").write_text("# Alpha\n\nGuided md.", encoding="utf-8")
        make_docx(folder / "b-note.docx", ["BetaDoc", "Guided doc."])
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#import"))
            await pilot.pause(0.2)
            app.screen.query_one("#import-path", Input).value = str(folder)
            await pilot.click(app.screen.query_one("#preview-folder"))
            await pilot.pause(0.2)

            assert list_entries(db_path) == []
            assert app.screen.query_one("#apply-folder", Button).disabled is False

            await pilot.click(app.screen.query_one("#apply-folder"))
            await pilot.pause(0.2)

        entries = list_entries(db_path)
        assert sorted(entry.title for entry in entries) == ["Alpha", "BetaDoc"]

    asyncio.run(run_flow())


def test_tui_export_memory_flow_writes_markdown_and_refuses_overwrite(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        output_path = tmp_path / "memory.md"
        init_database(db_path)
        add_entry(
            db_path,
            raw_text="Export this memory from the guided interface.",
            memory_type="project",
            title="Guided export memory",
            summary="Export this memory from the guided interface.",
            tags=("export",),
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(150, 46)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#export"))
            await pilot.pause(0.2)
            app.screen.query_one("#export-path", Input).value = str(output_path)
            app.screen.query_one("#export-memory-id", Input).value = "1"
            await pilot.click(app.screen.query_one("#export-memory"))
            await pilot.pause(0.2)

            assert output_path.exists()
            assert "Guided export memory" in output_path.read_text(encoding="utf-8")

            await pilot.click(app.screen.query_one("#export-memory"))
            await pilot.pause(0.2)
            status = app.screen.query_one("#export-status", Static).content
            assert "already exists" in str(status)

            app.screen.query_one("#export-force", Input).value = "yes"
            await pilot.click(app.screen.query_one("#export-memory"))
            await pilot.pause(0.2)
            status = app.screen.query_one("#export-status", Static).content
            assert "Exported memory #1" in str(status)

    asyncio.run(run_flow())


def test_tui_export_timeline_flow_writes_markdown(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        output_path = tmp_path / "timeline.md"
        init_database(db_path)
        add_entry(
            db_path,
            raw_text="First timeline export memory.",
            memory_type="project",
            title="First timeline export",
            summary="First timeline export memory.",
        )
        add_entry(
            db_path,
            raw_text="Second timeline export memory.",
            memory_type="project",
            title="Second timeline export",
            summary="Second timeline export memory.",
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(150, 46)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#export"))
            await pilot.pause(0.2)
            app.screen.query_one("#export-path", Input).value = str(output_path)
            app.screen.query_one("#export-timeline-limit", Input).value = "2"
            await pilot.click(app.screen.query_one("#export-timeline"))
            await pilot.pause(0.2)

        content = output_path.read_text(encoding="utf-8")
        assert "# Waymark Timeline" in content
        assert "First timeline export" in content
        assert "Second timeline export" in content

    asyncio.run(run_flow())


def test_tui_export_reflection_flow_writes_markdown(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        output_path = tmp_path / "reflection.md"
        init_database(db_path)
        add_reflection(
            db_path,
            period_type="week",
            period_start="2026-05-24",
            period_end="2026-05-30",
            summary="A guided reflection export.",
            wins=("#1 Kept exports explicit.",),
            patterns=("Reflection export pattern.",),
            suggestions=("Review the exported file.",),
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(170, 52)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#export"))
            await pilot.pause(0.2)
            app.screen.query_one("#export-path", Input).value = str(output_path)
            app.screen.query_one("#export-reflection-id", Input).value = "1"
            await pilot.click(app.screen.query_one("#export-reflection"))
            await pilot.pause(0.2)

        content = output_path.read_text(encoding="utf-8")
        assert "# Saved Reflection #1" in content
        assert "A guided reflection export." in content
        assert "#1 Kept exports explicit." in content

    asyncio.run(run_flow())


def test_tui_export_reflection_trends_flow_writes_scoped_markdown(tmp_path: Path) -> None:
    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        output_path = tmp_path / "reflection-trends.md"
        today = datetime.now(UTC).date().isoformat()
        init_database(db_path)
        add_entry(
            db_path,
            raw_text="A guided trend export source.",
            memory_type="project",
            title="Guided trend export source",
            summary="Guided trend export source.",
            tags=("focus",),
        )
        add_reflection(
            db_path,
            period_type="week",
            period_start=today,
            period_end=today,
            summary="Matching guided trend export.",
            patterns=("Guided scoped export pattern.",),
            suggestions=("Review guided scoped export.",),
        )
        add_reflection(
            db_path,
            period_type="week",
            period_start="2000-01-01",
            period_end="2000-01-07",
            summary="Unmatched guided trend export.",
            patterns=("Old export pattern.",),
            suggestions=("Review old export.",),
        )
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(170, 52)) as pilot:
            await pilot.pause(0.2)
            await pilot.click(app.screen.query_one("#export"))
            await pilot.pause(0.2)
            app.screen.query_one("#export-path", Input).value = str(output_path)
            app.screen.query_one("#export-trend-period", Input).value = "week"
            app.screen.query_one("#export-trend-tags", Input).value = "focus"
            app.screen.query_one("#export-trend-types", Input).value = "project"
            await pilot.click(app.screen.query_one("#export-reflection-trends"))
            await pilot.pause(0.2)

        content = output_path.read_text(encoding="utf-8")
        assert "# Waymark Reflection Trends" in content
        assert "Memory scope: tags: focus; types: project" in content
        assert "Matching guided trend export." in content
        assert "Unmatched guided trend export." not in content

    asyncio.run(run_flow())


def test_tui_doctor_shows_model_setup_and_saves_config(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from waymark import tui

    home_path = tmp_path / "home"
    monkeypatch.setenv("WAYMARK_HOME", str(home_path))
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
    monkeypatch.setattr(tui, "collect_system_profile", lambda path: profile)
    monkeypatch.setattr(
        tui,
        "get_ollama_status",
        lambda: ModelRuntimeStatus(
            name="ollama",
            available=True,
            executable="ollama",
            models=("nomic-embed-text:latest",),
        ),
    )

    async def run_flow() -> None:
        db_path = tmp_path / "waymark.sqlite3"
        app = WaymarkApp(db_path=db_path)

        async with app.run_test(size=(140, 42)) as pilot:
            await pilot.pause(0.2)
            await app.push_screen(tui.DoctorScreen(db_path))
            await pilot.pause(0.2)
            model_setup = app.screen.query_one("#doctor-model-setup", Static).content
            assert "ollama pull qwen3:4b" in str(model_setup)
            assert "already present" in str(model_setup)
            assert "No models are downloaded" in str(model_setup)

            await pilot.click(app.screen.query_one("#save-config"))
            await pilot.pause(0.2)
            status = app.screen.query_one("#doctor-status", Static).content
            assert "Saved config" in str(status)

        assert (home_path / "config.json").exists()

    asyncio.run(run_flow())
