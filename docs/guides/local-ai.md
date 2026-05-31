# Local AI with Ollama

Waymark works fully in **app-only mode** with no AI at all. Local AI is an
opt-in enhancement that runs entirely on your machine through
[Ollama](https://ollama.com). Waymark never downloads a model for you and never
calls a remote API.

## How setup stays safe

```bash
waymark doctor          # capability profile + Ollama detection
waymark setup           # preview a safe local recommendation
waymark setup --apply   # write config.json with those defaults (no downloads)
waymark setup models    # compare recommended vs installed models
```

`waymark setup models` prints the exact `ollama pull ...` commands for any
missing model — it **does not** run them. You stay in control of every download.

```bash
waymark models list     # detect Ollama + installed models
waymark models check    # compare your config's models against what's installed
```

## AI-assisted capture

Once a chat model is configured, capture can ask it to structure a memory card:

```bash
waymark capture --local-ai "Ask the local model to draft this memory."
waymark capture --local-ai --yes "Save a confirmed local-AI draft in scripts."
```

Before any model call, Waymark checks Ollama readiness and shows the precise
`ollama pull ...` command if the configured chat model is missing. The generated
card is always shown for confirmation before it is saved — pass `--yes` only for
scripted, non-interactive capture. If config or Ollama is unavailable, capture
falls back to deterministic app-only drafting.

## Semantic search

Semantic retrieval is opt-in and built on **explicitly generated** embeddings:

```bash
waymark embeddings status                       # what's indexed
waymark embeddings backfill                     # preview only (no model calls)
waymark embeddings backfill --apply --limit 10  # generate embeddings via Ollama
waymark ask "a fuzzy topic" --semantic          # hybrid keyword + tag + vector
```

Default `ask` uses keyword + tag matching. `--semantic` adds vector matches over
the embeddings you've generated, and still renders cited source cards.

!!! note "Always grounded"
    Even with local AI enabled, every answer cites saved memories or imported
    sources. Waymark separates *saved memory* from *AI interpretation* in its UI
    copy, and treats all model output as a draft until you confirm it.
