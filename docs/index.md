# Waymark

Waymark is a **local-first terminal companion** for capturing personal memories,
tracking decisions, reflecting on patterns, and asking grounded questions about
your life over time.

The product direction is **memory-first, not file-search-first**:

```text
capture messy thought -> structure memory card -> store locally -> retrieve with sources -> reflect over time
```

!!! info "Private by default"
    Everything lives in a local SQLite database under your Waymark home. Nothing
    is uploaded. Local AI is opt-in, models are never downloaded for you, and
    folders are never scanned without an explicit command.

## What you can do

- **Capture** a messy thought and turn it into a structured memory card.
- **Browse** a chronological timeline of everything you've saved.
- **Ask** grounded questions that answer only from your saved memories, with
  citations.
- **Reflect** over days, weeks, and months, with saved reflection history.
- **Track decisions** as first-class objects and review their outcomes.
- **Import** Markdown, text, PDF, and Word documents — single files or folders.
- **Back up and restore** your entire memory trail to a local backup file or a
  readable portable folder.

## Install

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1     # Windows; use source .venv/bin/activate elsewhere
python -m pip install -e ".[dev]"
```

Public downloads are built on tagged GitHub Releases as wheels and source
archives. See **[Installation & Updates](guides/installation.md)** for install
and release details.

PDF import needs an optional extra:

```bash
python -m pip install -e ".[pdf]"
```

## Your first minute

```bash
waymark                                   # guided terminal interface
waymark capture --type project "Shipped the first import flow today."
waymark timeline
waymark ask "import flow"
waymark reflect --period week
```

Continue with **[Getting Started](getting-started.md)**, or jump to the full
**[CLI reference](reference/cli.md)**.
