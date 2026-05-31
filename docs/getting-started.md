# Getting Started

This walkthrough follows Waymark's core loop end to end: capture a memory, find
it again, ask a grounded question, and reflect.

## 1. Install

=== "Windows PowerShell"

    ```powershell
    py -m pip install --user pipx
    py -m pipx ensurepath
    py -m pipx install waymark-memory
    ```

=== "macOS"

    ```bash
    brew install pipx
    pipx ensurepath
    pipx install waymark-memory
    ```

=== "Linux"

    ```bash
    python3 -m pip install --user pipx
    python3 -m pipx ensurepath
    python3 -m pipx install waymark-memory
    ```

Until PyPI is live, use the GitHub Release wheel from
[Installation & Updates](guides/installation.md).

## 2. Pick where your data lives

By default Waymark stores everything in a per-user home directory. For
experiments, point it somewhere disposable:

=== "PowerShell"

    ```powershell
    $env:WAYMARK_HOME = "$PWD\.waymark-runtime"
    ```

=== "bash"

    ```bash
    export WAYMARK_HOME="$PWD/.waymark-runtime"
    ```

Run `waymark doctor` to see the resolved home, your local capability profile, and
whether Ollama is detected.

## 3. See today's loop

```bash
waymark today
```

This shows captures from today, reflection windows that need attention, decision
review items, and copyable next commands.

## 4. Capture a memory

```bash
waymark capture --type project "Decided to build the CLI before the desktop app."
```

Waymark drafts a structured **memory card** — a title, a summary, a type, and
tags — and saves it. Want to see the draft before committing?

```bash
waymark capture --preview "Draft this card without saving it yet."
```

The guided interface (`waymark`) uses a two-step **Draft → Save / Edit / Discard**
flow for the same capture.

## 5. Browse the timeline

```bash
waymark timeline
```

Each row includes a memory **ID**. Open one in detail:

```bash
waymark memory show 1
```

## 6. Ask a grounded question

```bash
waymark ask "CLI first"
```

Answers are composed **only** from your saved memories and always cite the
sources they used. If nothing matches, Waymark says so instead of inventing an
answer. Add `--semantic` to include vector matches once you've generated
embeddings (see [Local AI](guides/local-ai.md)).

## 7. Reflect

```bash
waymark reflect --period week
waymark reflect --period week --save
```

Reflections are app-only and source-grounded: they summarize counts, types,
tags, and recent titles rather than inventing patterns. Saved reflections build
a history you can list, compare, and trend over time.

## 8. Track a decision

```bash
waymark decision add "Adopt local embeddings?" \
  --context "Hybrid search would help retrieval." --memory 1
waymark decision finalize 1 --choice "Yes, opt-in" --confidence 4
waymark decision outcome 1 --outcome "Retrieval noticeably improved."
```

## Where to go next

- **[Importing your world](guides/importing.md)** — bring in Markdown, text,
  PDF, and Word documents.
- **[Daily loop](guides/daily-loop.md)** — return tomorrow and know what needs
  attention.
- **[Local AI with Ollama](guides/local-ai.md)** — opt into local model
  structuring and semantic search.
- **[Backup & restore](guides/backup-restore.md)** — keep your memory trail safe
  and portable.
- **[CLI reference](reference/cli.md)** — every command and option.
