"""Shared memory draft selection for app-only and optional local AI capture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from waymark.ai import LocalAiError, structure_memory_with_ollama
from waymark.config import WaymarkConfig
from waymark.memory import MemoryDraft, draft_memory
from waymark.model_setup import is_model_installed
from waymark.runtime import ModelRuntimeStatus


class StructureMemoryFn(Protocol):
    def __call__(
        self,
        raw_text: str,
        *,
        memory_type: str,
        raw_tags: str,
        model: str,
    ) -> MemoryDraft: ...


@dataclass(frozen=True)
class CaptureDraftResult:
    draft: MemoryDraft
    source: str
    note: str | None = None


def build_capture_draft(
    raw_text: str,
    *,
    memory_type: str,
    raw_tags: str,
    local_ai: bool,
    config: WaymarkConfig | None,
    runtime_status: ModelRuntimeStatus | None = None,
    structure_memory: StructureMemoryFn = structure_memory_with_ollama,
) -> CaptureDraftResult:
    fallback = draft_memory(raw_text, memory_type=memory_type, raw_tags=raw_tags)
    if not local_ai:
        return CaptureDraftResult(draft=fallback, source="fallback")

    if config is None:
        return CaptureDraftResult(
            draft=fallback,
            source="fallback",
            note="Local AI requested, but config is missing. Using fallback draft.",
        )
    if config.models.runtime != "ollama" or not config.models.chat_model:
        return CaptureDraftResult(
            draft=fallback,
            source="fallback",
            note="Local AI is not configured for chat. Using fallback draft.",
        )

    chat_model = config.models.chat_model
    if runtime_status is not None:
        readiness_note = local_ai_readiness_note(chat_model, runtime_status)
        if readiness_note is not None:
            return CaptureDraftResult(
                draft=fallback,
                source="fallback",
                note=f"{readiness_note} Using fallback draft.",
            )

    try:
        draft = structure_memory(
            raw_text,
            memory_type=memory_type,
            raw_tags=raw_tags,
            model=chat_model,
        )
    except LocalAiError as error:
        return CaptureDraftResult(
            draft=fallback,
            source="fallback",
            note=f"Local AI draft failed: {error} Using fallback draft.",
        )

    return CaptureDraftResult(draft=draft, source=f"local-ai:{chat_model}")


def local_ai_readiness_note(
    chat_model: str,
    runtime_status: ModelRuntimeStatus,
) -> str | None:
    if not runtime_status.available:
        return "Ollama was not found. Run waymark setup models for manual setup commands."
    if runtime_status.error:
        return f"Ollama model check failed: {runtime_status.error}"
    if not is_model_installed(chat_model, runtime_status.models):
        return (
            f"Configured chat model {chat_model} is not installed. "
            f"Run: ollama pull {chat_model}."
        )
    return None
