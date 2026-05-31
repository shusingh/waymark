from __future__ import annotations

import subprocess

from pytest import MonkeyPatch

from waymark import runtime
from waymark.runtime import get_ollama_status, parse_ollama_list


def test_parse_ollama_list_extracts_model_names() -> None:
    output = """NAME              ID              SIZE      MODIFIED
qwen3:4b          abc123          2.6 GB    2 days ago
nomic-embed-text  def456          274 MB    1 week ago
"""

    assert parse_ollama_list(output) == ("qwen3:4b", "nomic-embed-text")


def test_get_ollama_status_when_missing(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "find_ollama_executable", lambda: None)

    status = get_ollama_status()

    assert status.available is False
    assert status.models == ()


def test_get_ollama_status_lists_models(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "find_ollama_executable", lambda: "ollama")

    def fake_run(executable: str, *, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        assert executable == "ollama"
        assert timeout_seconds == 5
        return subprocess.CompletedProcess(
            args=["ollama", "list"],
            returncode=0,
            stdout="NAME ID SIZE MODIFIED\nqwen3:4b abc 2 GB today\n",
            stderr="",
        )

    monkeypatch.setattr(runtime, "run_ollama_list", fake_run)

    status = get_ollama_status()

    assert status.available is True
    assert status.models == ("qwen3:4b",)
