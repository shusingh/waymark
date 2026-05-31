# Waymark

Waymark is a local-first terminal companion for capturing personal memories,
tracking decisions, reflecting on patterns, and asking grounded questions about
your life over time.

The product direction is memory-first, not file-search-first:

```text
capture messy thought -> structure memory card -> store locally -> retrieve with sources -> reflect over time
```

## Current Status

This repository is in the early local-first MVP. The current implementation
includes:

- A Python package scaffold
- A `waymark` CLI entrypoint
- A local SQLite schema
- Guided Textual flows for capture, timeline, memory detail, reflection,
  decisions, import, export, and doctor checks
- CLI commands for capture, retrieval, editing, reflection, decisions,
  Markdown/text import, Markdown export, journey map, and setup
- A gitignored local handoff folder at `.waymark-local/`

## Setup

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## First Commands

```bash
waymark
waymark --plain
waymark tui
waymark doctor
waymark setup
waymark setup --apply
waymark setup models
waymark models list
waymark models check
waymark embeddings status
waymark embeddings backfill
waymark embeddings backfill --apply --limit 10
waymark capture --type project "I want Waymark to become my private memory terminal."
waymark capture --preview "Draft this card without saving it yet."
waymark capture --local-ai "Ask the configured local model to draft this memory."
waymark capture --local-ai --yes "Save a confirmed local-AI draft in scripts."
waymark timeline
waymark memory show 1
waymark memory edit 1 --title "Better title" --summary "Clearer summary." --tag project
waymark ask "private memory"
waymark ask "private memory" --semantic
waymark journey
waymark journey prompts
waymark reflect --period week
waymark reflect --period today --save
waymark reflections list
waymark reflections due
waymark reflections due --generate-next
waymark reflections due --save-next
waymark reflections compare --period week
waymark reflections trends --period week
waymark reflections trends --period week --tag focus --type project
waymark reflections show 1
waymark import markdown .\notes\memory.md
waymark import text .\notes\memory.txt
waymark import markdown-folder .\notes
waymark import markdown-folder .\notes --apply
waymark sources list
waymark export memory 1 .\exports\memory-1.md
waymark export timeline .\exports\timeline.md --limit 20
waymark export reflection 1 .\exports\reflection-1.md
waymark export reflection-trends .\exports\reflection-trends.md --period week
waymark decision add "Build CLI first?" --context "The memory engine matters most." --memory 1
waymark decision show 1
waymark decision review
waymark decision link 1 2
waymark decision unlink 1 2
waymark decision finalize 1 --choice "CLI first" --confidence 4
waymark decision outcome 1 --outcome "The CLI foundation was the right first move."
waymark decision list
```

`waymark` launches the guided Textual interface. The direct commands remain
available for scripting, testing, and quick capture.

The guided Capture flow is intentionally two-step: draft a memory card first,
then choose Save, Edit, or Discard. Its Local AI field defaults to `no`; setting
it to `yes` uses the configured local model for the draft and still requires
confirmation before saving.

CLI capture can opt into local AI structuring with `--local-ai` or `--ai`. This
uses the chat model saved in `config.json`, asks local Ollama for JSON fields,
and falls back to deterministic app-only drafting if config or Ollama is
unavailable. Before calling the model, Waymark checks read-only Ollama status and
shows the exact `ollama pull ...` command when the configured chat model is
missing. Successful local-AI drafts are shown before saving; confirm the prompt
or pass `--yes` for scripted capture.

Add `--preview` or `--dry-run` to `waymark capture` to inspect the drafted memory
card without saving it. This works for both app-only and local-AI drafts.

The guided Import flow mirrors that safety model: a folder path must be
previewed before Apply Preview writes entries. It can also import one explicit
Markdown or plain text file.

The guided Memory Detail view shows a memory by ID with source and linked
decision context.

The guided Doctor view shows local capability, Ollama status, recommended model
commands, and a deliberate Save Safe Config action.

Timeline rows include memory IDs, so a recent entry can be opened with
`waymark memory show ID` or linked to a decision.

The guided Export screen writes one memory, a recent timeline slice, one saved
reflection, or saved reflection trends to an explicit Markdown path, preserving
the same overwrite protection as the CLI.

`waymark setup` previews a safe local capability recommendation. `waymark setup
--apply` writes `config.json` with those defaults. `waymark setup models`
checks the recommended local models against installed Ollama models and prints
manual `ollama pull ...` commands when a model is missing. These commands do not
download models, scan folders, or start background indexing.

`waymark reflect` currently generates an app-only, source-grounded reflection
from saved entries using counts, memory types, tags, and recent titles. It does
not ask an AI model to infer unsupported patterns yet.

`waymark reflect --save` skips a reflection window that is already saved. Add
`--force` when you intentionally want another saved copy for the same window.

`waymark reflections list` and `waymark reflections show ID` inspect saved
reflections. Reflection wins include memory IDs so the source trail remains
visible.

`waymark reflections due` shows current reflection windows that have saved
memories but no saved reflection yet. The guided Reflect screen can show the
same due-window queue, including the latest saved window for that period when
one exists, list saved reflections, and show one by ID. Add `--generate-next`
to preview the first due reflection or `--save-next` to save it explicitly. The
guided Reflect screen has a Generate Due action for the same first due window.

`waymark reflections compare --period week` compares the current generated
reflection with the latest saved reflection for that period. The guided Reflect
screen has the same Compare action.

`waymark reflections trends --period week` summarizes saved reflections for a
period, including repeated patterns, repeated suggestions, and latest summaries.
Add `--tag` and/or `--type` to include only saved reflection windows that contain
matching memories. The guided Reflect screen has matching Trend tags and Trend
types fields for scoped trend review. Use `waymark export reflection ID FILE` or
`waymark export reflection-trends FILE` to write saved reflection material to
explicit Markdown files. The reflection-trends export accepts the same
`--period`, `--tag`, and `--type` scope options.

`waymark journey` shows an app-only memory-health snapshot: recent capture
rhythm, top memory types/tags, decision review/outcome signals, and saved
reflection coverage. It includes thin memory areas from the last 30 days,
capture prompts, adaptive reflection commands, and specific decision IDs for
open, review, and outcome follow-up. The guided Journey Map screen shows the
same local summary, plus prompt buttons that open Capture with the suggested
type and prompt prefilled, and reflection buttons that open Reflect with the
suggested period selected.

`waymark journey prompts` prints copyable capture commands for the same thin-area
prompts.

`waymark models list` is a read-only Ollama check. It lists local models when
Ollama is available and never downloads anything.

`waymark models check` compares the models in `config.json` with installed
Ollama models. It prints missing-model commands but does not run them.

`waymark embeddings status` shows configured embedding readiness. `waymark
embeddings backfill` previews entries missing vectors, and `--apply` generates
embeddings explicitly with the configured local Ollama embedding model. There is
no background indexing.

`waymark ask "question"` retrieves by keyword and matching tags. `waymark ask
"question" --semantic` adds explicitly generated embedding vectors and shows
scored source cards. It does not generate vectors itself; run `waymark
embeddings backfill --apply` when you want current memories indexed for semantic
retrieval.

Ask results include a simple grounded answer panel that cites memory IDs and
only uses retrieved source summaries, followed by the full source cards. The
guided Ask screen uses the same app-only keyword/tag retrieval path.

`waymark import markdown FILE` imports one explicit Markdown file as a sourced
memory. It does not scan folders. If the same resolved file path was already
imported, Waymark skips it unless you add `--force`.

`waymark import text FILE` imports one explicit `.txt` or `.text` file as a
sourced memory with `import,text` tags and the same duplicate-path protection.

`waymark import markdown-folder FOLDER` previews Markdown files from one
explicit folder without importing them. Add `--apply` to import the previewed
files, `--recursive` to include nested folders, and `--limit` to bound the
batch. Duplicate file paths are skipped during apply unless `--force` is used.

`waymark sources list` shows imported source metadata. Ask results include the
source filename when a memory came from an imported file.

`waymark export memory ID FILE`, `waymark export timeline FILE`,
`waymark export reflection ID FILE`, and `waymark export reflection-trends FILE`
write Markdown to an explicit output path. Existing files are not overwritten
unless you add `--force`.

Decisions can be linked to memories with `--memory` during creation or later via
`waymark decision link DECISION_ID MEMORY_ID`. `waymark decision show ID`
includes linked memory summaries.

`waymark decision review` shows decisions whose review date is due and decided
items still waiting for an outcome. The guided Decisions screen has the same
Review Queue action.

`waymark memory show ID` displays the full memory card, its source, and any
linked decisions.

`waymark memory edit ID` updates selected fields on a saved memory. In the
guided interface, Memory Detail can load a memory, edit its fields, and save the
corrected card.

By default, runtime data is stored in `~/.waymark`. For local development, set:

```bash
$env:WAYMARK_HOME = "D:\Code\waymark\.waymark-local\runtime"
```

## Product Guardrails

- Local-first by default.
- Manual capture works even without AI models.
- AI-generated summaries, tags, and reflections require user confirmation.
- Answers must cite saved memories or imported sources.
- No large model downloads, file scans, OCR, or indexing jobs without explicit approval.
