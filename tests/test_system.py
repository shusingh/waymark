from __future__ import annotations

from waymark.system import recommend_capability


def test_recommend_capability_app_only_for_low_disk() -> None:
    recommendation = recommend_capability(total_ram_gb=32, disk_free_gb=2, cpu_count=12)

    assert recommendation.mode == "app-only"
    assert recommendation.chat_model is None


def test_recommend_capability_lite_for_8gb_ram() -> None:
    recommendation = recommend_capability(total_ram_gb=8, disk_free_gb=20, cpu_count=4)

    assert recommendation.mode == "lite"
    assert recommendation.embedding_model == "nomic-embed-text"


def test_recommend_capability_balanced_for_16gb_ram() -> None:
    recommendation = recommend_capability(total_ram_gb=16, disk_free_gb=20, cpu_count=8)

    assert recommendation.mode == "balanced"
    assert recommendation.chat_model == "qwen3:4b"


def test_recommend_capability_pro_for_32gb_ram() -> None:
    recommendation = recommend_capability(total_ram_gb=32, disk_free_gb=40, cpu_count=12)

    assert recommendation.mode == "pro"
    assert recommendation.chat_model == "qwen3:8b"
