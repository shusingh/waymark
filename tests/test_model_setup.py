from __future__ import annotations

from waymark.model_setup import build_model_setup_plan, is_model_installed
from waymark.runtime import ModelRuntimeStatus
from waymark.system import CapabilityRecommendation, SystemProfile


def test_is_model_installed_accepts_latest_tag_for_untagged_recommendation() -> None:
    assert is_model_installed(
        "nomic-embed-text",
        ("nomic-embed-text:latest",),
    )


def test_is_model_installed_requires_exact_tagged_model() -> None:
    assert is_model_installed("qwen3:4b", ("qwen3:4b",))
    assert not is_model_installed("qwen3:4b", ("qwen3:8b",))


def test_build_model_setup_plan_marks_missing_and_installed_models() -> None:
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
    runtime_status = ModelRuntimeStatus(
        name="ollama",
        available=True,
        executable="ollama",
        models=("nomic-embed-text:latest",),
    )

    plan = build_model_setup_plan(profile, runtime_status)

    assert plan.mode == "balanced"
    assert len(plan.items) == 2
    assert plan.items[0].model == "qwen3:4b"
    assert plan.items[0].installed is False
    assert plan.items[0].command == "ollama pull qwen3:4b"
    assert plan.items[1].model == "nomic-embed-text"
    assert plan.items[1].installed is True
