"""Model setup recommendations without side effects."""

from __future__ import annotations

from dataclasses import dataclass

from waymark.runtime import ModelRuntimeStatus
from waymark.system import SystemProfile


@dataclass(frozen=True)
class ModelSetupItem:
    purpose: str
    model: str
    installed: bool
    command: str


@dataclass(frozen=True)
class ModelSetupPlan:
    mode: str
    reason: str
    runtime_available: bool
    runtime_error: str | None
    items: tuple[ModelSetupItem, ...]


def build_model_setup_plan(
    profile: SystemProfile,
    runtime_status: ModelRuntimeStatus,
) -> ModelSetupPlan:
    recommendation = profile.recommendation
    items: list[ModelSetupItem] = []
    recommended_models = (
        ("Chat", recommendation.chat_model),
        ("Embeddings", recommendation.embedding_model),
    )

    for purpose, model in recommended_models:
        if model is None:
            continue
        installed = is_model_installed(model, runtime_status.models)
        items.append(
            ModelSetupItem(
                purpose=purpose,
                model=model,
                installed=installed,
                command=f"ollama pull {model}",
            )
        )

    return ModelSetupPlan(
        mode=recommendation.mode,
        reason=recommendation.reason,
        runtime_available=runtime_status.available,
        runtime_error=runtime_status.error,
        items=tuple(items),
    )


def is_model_installed(recommended_model: str, installed_models: tuple[str, ...]) -> bool:
    if recommended_model in installed_models:
        return True

    if ":" in recommended_model:
        return False

    return any(model == f"{recommended_model}:latest" for model in installed_models)
