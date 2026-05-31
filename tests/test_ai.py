from __future__ import annotations

import pytest

from waymark.ai import (
    MEMORY_STRUCTURE_SYSTEM_PROMPT,
    LocalAiError,
    build_memory_structure_prompt,
    normalize_memory_type,
    normalize_model_tags,
    parse_memory_structure_response,
    parse_ollama_embed_response,
)


def test_memory_structure_prompt_is_stable() -> None:
    assert MEMORY_STRUCTURE_SYSTEM_PROMPT == (
        "You structure one personal memory.\n"
        "Return compact JSON only with: title, summary, type, tags.\n"
        "Do not add facts that are not present in the memory.\n"
        "Use 2-5 lowercase tags."
    )
    assert build_memory_structure_prompt(
        "Met Dana about Waymark onboarding.",
        memory_type=" Project ",
        raw_tags="waymark, onboarding",
    ) == (
        "Draft a memory card for this saved memory.\n"
        "Requested type: Project\n"
        "User tags: waymark, onboarding\n\n"
        "Memory:\n"
        "Met Dana about Waymark onboarding."
    )


def test_parse_memory_structure_response_accepts_fenced_json_and_combines_tags() -> None:
    draft = parse_memory_structure_response(
        """```json
        {
          "title": "Met with the design partner",
          "summary": "A useful call clarified onboarding and safety.",
          "type": "project",
          "tags": ["design", "onboarding"]
        }
        ```""",
        raw_text="Talked with a design partner about Waymark onboarding.",
        fallback_memory_type="daily",
        raw_tags="waymark, design",
    )

    assert draft.title == "Met with the design partner"
    assert draft.summary == "A useful call clarified onboarding and safety."
    assert draft.memory_type == "project"
    assert draft.tags == ("design", "onboarding", "waymark")


def test_parse_memory_structure_response_uses_fallback_fields() -> None:
    draft = parse_memory_structure_response(
        '{"tags": "local-ai, capture"}',
        raw_text="A short fallback memory.",
        fallback_memory_type="project",
    )

    assert draft.title == "A short fallback memory."
    assert draft.summary == "A short fallback memory."
    assert draft.memory_type == "project"
    assert draft.tags == ("capture", "local-ai")


def test_parse_memory_structure_response_rejects_non_json() -> None:
    with pytest.raises(LocalAiError):
        parse_memory_structure_response(
            "title: no json here",
            raw_text="Raw memory",
            fallback_memory_type="daily",
        )


def test_parse_memory_structure_response_repairs_trailing_commas() -> None:
    draft = parse_memory_structure_response(
        """
        {
          "title": "Trailing comma draft",
          "summary": "The response had trailing commas.",
          "type": "Project Memory!",
          "tags": ["local AI", "cleanup",],
        }
        """,
        raw_text="A model returned JSON with trailing commas.",
        fallback_memory_type="daily",
    )

    assert draft.title == "Trailing comma draft"
    assert draft.memory_type == "project-memory"
    assert draft.tags == ("cleanup", "local-ai")


def test_model_tags_are_bounded() -> None:
    tags = normalize_model_tags(
        [
            "six",
            "five",
            "four",
            "three",
            "two",
            "one",
            "x" * 80,
        ]
    )

    assert tags == ("five", "four", "one", "six", "three")


def test_memory_type_is_slug_normalized_with_fallback() -> None:
    assert normalize_memory_type("Project Memory!") == "project-memory"
    assert normalize_memory_type("!!!", fallback="Daily") == "daily"
    assert normalize_memory_type(None, fallback="Learning") == "learning"


def test_parse_ollama_embed_response_returns_first_vector() -> None:
    vector = parse_ollama_embed_response(
        b'{"model": "nomic-embed-text", "embeddings": [[0.1, -0.2, 3]]}'
    )

    assert vector == (0.1, -0.2, 3.0)


def test_parse_ollama_embed_response_rejects_empty_vectors() -> None:
    with pytest.raises(LocalAiError):
        parse_ollama_embed_response(b'{"embeddings": []}')
