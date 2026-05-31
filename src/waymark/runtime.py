"""Read-only local model runtime detection."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRuntimeStatus:
    name: str
    available: bool
    executable: str | None
    models: tuple[str, ...]
    error: str | None = None


def get_ollama_status(*, timeout_seconds: int = 5) -> ModelRuntimeStatus:
    executable = find_ollama_executable()
    if executable is None:
        return ModelRuntimeStatus(
            name="ollama",
            available=False,
            executable=None,
            models=(),
            error="Ollama executable was not found on PATH.",
        )

    try:
        result = run_ollama_list(executable, timeout_seconds=timeout_seconds)
    except (OSError, subprocess.TimeoutExpired) as error:
        return ModelRuntimeStatus(
            name="ollama",
            available=True,
            executable=executable,
            models=(),
            error=str(error),
        )

    if result.returncode != 0:
        return ModelRuntimeStatus(
            name="ollama",
            available=True,
            executable=executable,
            models=(),
            error=(result.stderr or result.stdout).strip() or "ollama list failed.",
        )

    return ModelRuntimeStatus(
        name="ollama",
        available=True,
        executable=executable,
        models=parse_ollama_list(result.stdout),
    )


def parse_ollama_list(output: str) -> tuple[str, ...]:
    models: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("name "):
            continue
        model_name = stripped.split()[0]
        if model_name:
            models.append(model_name)
    return tuple(models)


def find_ollama_executable() -> str | None:
    return shutil.which("ollama")


def run_ollama_list(
    executable: str,
    *,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [executable, "list"],
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout_seconds,
    )
