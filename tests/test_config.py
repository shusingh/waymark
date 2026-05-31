from __future__ import annotations

from pathlib import Path

from waymark.config import (
    build_recommended_config,
    read_config,
    suggested_max_memory_gb,
    write_config,
)
from waymark.system import CapabilityRecommendation, SystemProfile


def test_build_recommended_config_from_profile(tmp_path: Path) -> None:
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
            reason="test",
        ),
    )

    config = build_recommended_config(profile)
    config_path = tmp_path / "config.json"
    write_config(config_path, config)
    loaded = read_config(config_path)

    assert loaded is not None
    assert loaded.performance.mode == "balanced"
    assert loaded.performance.background_indexing is False
    assert loaded.models.chat_model == "qwen3:4b"
    assert loaded.features.local_ai_chat is True
    assert loaded.features.ocr == "manual"


def test_suggested_max_memory_gb_stays_conservative() -> None:
    assert suggested_max_memory_gb(None, "balanced") is None
    assert suggested_max_memory_gb(8, "lite") == 4
    assert suggested_max_memory_gb(16, "balanced") == 8
    assert suggested_max_memory_gb(64, "pro") == 16
