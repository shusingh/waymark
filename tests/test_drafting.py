from __future__ import annotations

from waymark.config import FeatureConfig, ModelConfig, PerformanceConfig, SetupConfig, WaymarkConfig
from waymark.drafting import build_capture_draft, local_ai_readiness_note
from waymark.memory import MemoryDraft
from waymark.runtime import ModelRuntimeStatus


def test_local_ai_readiness_note_reports_missing_ollama() -> None:
    note = local_ai_readiness_note(
        "qwen3:4b",
        ModelRuntimeStatus(
            name="ollama",
            available=False,
            executable=None,
            models=(),
            error="not found",
        ),
    )

    assert note is not None
    assert "Ollama was not found" in note


def test_local_ai_readiness_note_reports_missing_chat_model() -> None:
    note = local_ai_readiness_note(
        "qwen3:4b",
        ModelRuntimeStatus(
            name="ollama",
            available=True,
            executable="ollama",
            models=("nomic-embed-text:latest",),
        ),
    )

    assert note == "Configured chat model qwen3:4b is not installed. Run: ollama pull qwen3:4b."


def test_build_capture_draft_skips_model_call_when_chat_model_is_missing() -> None:
    called = False

    def fail_if_called(
        raw_text: str,
        *,
        memory_type: str,
        raw_tags: str,
        model: str,
    ) -> MemoryDraft:
        nonlocal called
        called = True
        return MemoryDraft(
            raw_text=raw_text,
            memory_type=memory_type,
            title="Should not happen",
            summary="Should not happen.",
            tags=(),
        )

    result = build_capture_draft(
        "Use fallback if the configured model is missing.",
        memory_type="daily",
        raw_tags="local-ai",
        local_ai=True,
        config=make_config(),
        runtime_status=ModelRuntimeStatus(
            name="ollama",
            available=True,
            executable="ollama",
            models=("nomic-embed-text:latest",),
        ),
        structure_memory=fail_if_called,
    )

    assert not called
    assert result.source == "fallback"
    assert result.note is not None
    assert "ollama pull qwen3:4b" in result.note
    assert result.draft.title == "Use fallback if the configured model is missing."


def test_build_capture_draft_calls_model_when_chat_model_is_ready() -> None:
    def fake_structure_memory(
        raw_text: str,
        *,
        memory_type: str,
        raw_tags: str,
        model: str,
    ) -> MemoryDraft:
        assert model == "qwen3:4b"
        return MemoryDraft(
            raw_text=raw_text,
            memory_type="project",
            title="Ready local draft",
            summary="Ready local draft.",
            tags=("ready",),
        )

    result = build_capture_draft(
        "Use local AI when the model is ready.",
        memory_type="daily",
        raw_tags="",
        local_ai=True,
        config=make_config(),
        runtime_status=ModelRuntimeStatus(
            name="ollama",
            available=True,
            executable="ollama",
            models=("qwen3:4b",),
        ),
        structure_memory=fake_structure_memory,
    )

    assert result.source == "local-ai:qwen3:4b"
    assert result.note is None
    assert result.draft.title == "Ready local draft"


def make_config() -> WaymarkConfig:
    return WaymarkConfig(
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
