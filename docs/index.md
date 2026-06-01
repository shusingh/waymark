<section class="waymark-hero" markdown>

# Private memory, from the terminal

Waymark is a local-first CLI and guided terminal app for capturing memories,
tracking decisions, reviewing patterns, and asking grounded questions over your
own saved context.

</section>

```text
capture -> timeline -> ask with sources -> reflect -> review decisions
```

!!! note "Package name"
    The PyPI distribution is `waymark-memory` because `waymark` is already used
    by another package. The installed command remains `waymark`.

## Install

Install Waymark with `pipx`:

=== "Windows PowerShell"

    ```powershell
    py -m pip install --user pipx
    py -m pipx ensurepath
    py -m pipx install waymark-memory
    waymark --version
    ```

=== "macOS"

    ```bash
    brew install pipx
    pipx ensurepath
    pipx install waymark-memory
    waymark --version
    ```

=== "Linux"

    ```bash
    python3 -m pip install --user pipx
    python3 -m pipx ensurepath
    python3 -m pipx install waymark-memory
    waymark --version
    ```

You can also install the latest GitHub Release wheel directly:

```bash
python -m pip install https://github.com/shusingh/waymark/releases/download/v0.3.0/waymark_memory-0.3.0-py3-none-any.whl
```

## First minute

```bash
waymark today
waymark capture --type project "Shipped the first import flow today."
waymark timeline
waymark ask "import flow"
waymark reflect --period week
```

## What Waymark Does

<div class="waymark-grid" markdown>

<div class="waymark-card" markdown>
**Daily loop**

See what needs attention today: new capture, due reflection, or decision review.
</div>

<div class="waymark-card" markdown>
**Grounded recall**

Ask questions over saved memories and imported sources with visible citations.
</div>

<div class="waymark-card" markdown>
**Decisions**

Track choices, review dates, outcomes, and the memories that informed them.
</div>

<div class="waymark-card" markdown>
**Portability**

Back up and restore your local memory trail without sending it to a service.
</div>

</div>

## Local-First Rules

- Data is stored under your Waymark home in a local SQLite database.
- Manual capture works without AI models.
- Local AI is opt-in and uses your own Ollama installation.
- Folders are never scanned without an explicit command.
- Generated answers must cite saved memories or imported sources.

Continue with **[Getting Started](getting-started.md)** or the
**[Installation guide](guides/installation.md)**.
