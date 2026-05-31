"""Local Waymark configuration."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from waymark.storage import utc_now
from waymark.system import SystemProfile


@dataclass(frozen=True)
class PerformanceConfig:
    mode: str
    max_memory_gb: int | None
    max_cpu_percent: int
    pause_on_battery: bool
    background_indexing: bool


@dataclass(frozen=True)
class ModelConfig:
    runtime: str
    chat_model: str | None
    embedding_model: str | None


@dataclass(frozen=True)
class FeatureConfig:
    local_ai_chat: bool
    semantic_search: bool
    ocr: str
    background_indexing: bool


@dataclass(frozen=True)
class SetupConfig:
    completed: bool
    completed_at: str


@dataclass(frozen=True)
class WaymarkConfig:
    performance: PerformanceConfig
    models: ModelConfig
    features: FeatureConfig
    setup: SetupConfig


def build_recommended_config(profile: SystemProfile) -> WaymarkConfig:
    recommendation = profile.recommendation
    has_chat_model = recommendation.chat_model is not None
    has_embedding_model = recommendation.embedding_model is not None
    max_memory_gb = suggested_max_memory_gb(profile.total_ram_gb, recommendation.mode)

    return WaymarkConfig(
        performance=PerformanceConfig(
            mode=recommendation.mode,
            max_memory_gb=max_memory_gb,
            max_cpu_percent=60,
            pause_on_battery=True,
            background_indexing=False,
        ),
        models=ModelConfig(
            runtime="ollama",
            chat_model=recommendation.chat_model,
            embedding_model=recommendation.embedding_model,
        ),
        features=FeatureConfig(
            local_ai_chat=has_chat_model,
            semantic_search=has_embedding_model,
            ocr="manual",
            background_indexing=False,
        ),
        setup=SetupConfig(completed=True, completed_at=utc_now()),
    )


def suggested_max_memory_gb(total_ram_gb: float | None, mode: str) -> int | None:
    if total_ram_gb is None or mode == "app-only":
        return None
    if mode == "lite":
        return max(2, min(4, int(total_ram_gb // 2)))
    if mode == "balanced":
        return max(6, min(8, int(total_ram_gb // 2)))
    if mode == "pro":
        return max(8, min(16, int(total_ram_gb // 2)))
    return None


def write_config(path: Path, config: WaymarkConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_config(path: Path) -> WaymarkConfig | None:
    if not path.exists():
        return None

    data = json.loads(path.read_text(encoding="utf-8"))
    return WaymarkConfig(
        performance=PerformanceConfig(**data["performance"]),
        models=ModelConfig(**data["models"]),
        features=FeatureConfig(**data["features"]),
        setup=SetupConfig(**data["setup"]),
    )

