# Configuration

Waymark keeps all of its state inside a single **Waymark home** directory. You
can override the location with the `WAYMARK_HOME` environment variable; otherwise
a per-user application directory is used.

```text
$WAYMARK_HOME/
  waymark.sqlite3     # all memories, decisions, reflections, sources, embeddings
  config.json         # local settings (written by `waymark setup --apply`)
```

`waymark doctor` prints the resolved home and the active configuration.

## config.json

`config.json` is optional. Without it, Waymark runs in app-only mode. Write a
safe default with `waymark setup --apply`. It is plain JSON with four sections:

```json
{
  "performance": {
    "mode": "balanced",
    "max_memory_gb": 8,
    "max_cpu_percent": 60,
    "pause_on_battery": true,
    "background_indexing": false
  },
  "models": {
    "runtime": "ollama",
    "chat_model": "qwen3:4b",
    "embedding_model": "nomic-embed-text"
  },
  "features": {
    "local_ai_chat": true,
    "semantic_search": true,
    "ocr": "manual",
    "background_indexing": false
  },
  "setup": {
    "completed": true,
    "completed_at": "2026-05-31T00:00:00+00:00"
  }
}
```

### performance

| Field | Type | Meaning |
| --- | --- | --- |
| `mode` | string | Capability tier: `app-only`, `lite`, `balanced`, or `pro`. |
| `max_memory_gb` | int or null | Soft memory ceiling for local models (null in app-only mode). |
| `max_cpu_percent` | int | Soft CPU ceiling. |
| `pause_on_battery` | bool | Prefer to avoid heavy work on battery. |
| `background_indexing` | bool | Always `false` — Waymark never indexes in the background by default. |

### models

| Field | Type | Meaning |
| --- | --- | --- |
| `runtime` | string | Local model runtime, currently `ollama`. |
| `chat_model` | string or null | Model used for opt-in capture structuring. |
| `embedding_model` | string or null | Model used for opt-in semantic search. |

### features

| Field | Type | Meaning |
| --- | --- | --- |
| `local_ai_chat` | bool | Enables `--local-ai` capture structuring. |
| `semantic_search` | bool | Enables `ask --semantic`. |
| `ocr` | string | OCR policy. `manual` means never automatic. |
| `background_indexing` | bool | Mirrors the performance flag; kept `false` by default. |

### setup

| Field | Type | Meaning |
| --- | --- | --- |
| `completed` | bool | Whether first-run setup has been applied. |
| `completed_at` | string | UTC ISO timestamp of the last apply. |

!!! tip "Safe by construction"
    `waymark setup --apply` derives these values from your machine's capability
    profile and never downloads a model, scans a folder, or starts background
    work. Run `waymark setup models` to see the manual `ollama pull ...`
    commands for any recommended model you don't have yet.
