# Waymark

Waymark is a local-first terminal companion for capturing personal memories,
tracking decisions, reflecting on patterns, and asking grounded questions about
your life over time.

```text
capture messy thought -> structure memory card -> store locally -> retrieve with sources -> reflect over time
```

Full documentation lives at **https://shusingh.github.io/waymark/**.
The PyPI package name is **`waymark-memory`**; the installed command remains
**`waymark`**.
The complete CLI reference is generated from the Typer app, so use the docs site
instead of hand-maintained command lists.

## What Works

- Guided Textual interface for today, capture, ask, timeline, memory detail,
  reflection, decisions, import, export, backup, and doctor checks.
- Local SQLite storage with source citations, saved reflections, linked
  decisions, local backups, and portable bundles.
- Explicit imports for Markdown, text, PDF text layers, DOCX paragraphs, and
  bounded preview-first folder batches.
- Optional local AI through Ollama for memory structuring and semantic retrieval.

## Install

Recommended install:

```bash
pipx install waymark-memory
waymark --version
```

Current GitHub Release:

```bash
python -m pip install https://github.com/shusingh/waymark/releases/download/v0.3.1/waymark_memory-0.3.1-py3-none-any.whl
waymark --version
```

Platform-specific commands are in
[Installation & Updates](docs/guides/installation.md).

From source on Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,docs,pdf]"
```

From source on macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,docs,pdf]"
```

## First Minute

```bash
waymark
waymark today
waymark capture --type project "Shipped the first import flow today."
waymark timeline
waymark ask "import flow"
waymark reflect --period week
```

Start with [Getting Started](docs/getting-started.md), or open the live
[CLI reference](https://shusingh.github.io/waymark/reference/cli/).

## Development

Runtime data defaults to `~/.waymark`. For local development, keep test data out
of your real profile:

```powershell
$env:WAYMARK_HOME = "$PWD\.waymark-runtime"
```

Before committing code changes:

```bash
ruff check .
mypy src
pytest -q
mkdocs build --strict
python -m build
python -m twine check dist/*
```

CI and release jobs also run a fresh wheel install smoke test:

```bash
python -m venv .wheel-smoke
. .wheel-smoke/bin/activate
python -m pip install dist/*.whl
waymark --version
```

## Product Guardrails

- Local-first by default.
- Manual capture works without AI models.
- AI-generated summaries, tags, and reflections require user confirmation.
- Answers must cite saved memories or imported sources.
- No large model downloads, file scans, OCR, or indexing jobs without explicit
  approval.
