# Waymark

Waymark is a local-first terminal companion for capturing personal memories,
tracking decisions, reflecting on patterns, and asking grounded questions about
your life over time.

```text
capture messy thought -> structure memory card -> store locally -> retrieve with sources -> reflect over time
```

Full documentation lives at **https://shusingh.github.io/waymark/**.
Downloadable packages live on **https://github.com/shusingh/waymark/releases**.
The complete CLI reference is generated from the Typer app, so use the docs site
instead of hand-maintained command lists.

## What Works

- Guided Textual interface for capture, ask, timeline, memory detail,
  reflection, decisions, import, export, backup, and doctor checks.
- Local SQLite storage with source citations, saved reflections, linked
  decisions, local backups, and portable bundles.
- Explicit imports for Markdown, text, PDF text layers, DOCX paragraphs, and
  bounded preview-first folder batches.
- Optional local AI through Ollama for memory structuring and semantic retrieval.

## Install

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

PDF import needs the optional PDF extra:

```bash
python -m pip install -e ".[pdf]"
```

Docs tooling is separate:

```bash
python -m pip install -e ".[docs]"
mkdocs serve
```

For public downloads, Waymark's first distribution channel is
[GitHub Releases](https://github.com/shusingh/waymark/releases): tagged releases
build a wheel and source archive that people can install with `pip` or `pipx`.
See [Installation & Updates](docs/guides/installation.md).

## First Minute

```bash
waymark
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
$env:WAYMARK_HOME = "D:\Code\waymark\.waymark-local\runtime"
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
