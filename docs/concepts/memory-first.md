# Memory-first design

Waymark is a memory-first companion, not a generic document-search tool. That
distinction drives every design decision. The core loop is always:

```text
capture messy thought -> structure memory card -> store locally -> retrieve with sources -> reflect over time
```

## Non-drift rules

These rules keep the product from drifting into "yet another RAG app":

1. **Memory before automation.** Manual capture is the foundation; AI is an
   enhancement.
2. **Capture before import.** Documents enrich the journey — they don't replace
   your own captured memories.
3. **Local SQLite backbone before vector search.** A simple, inspectable
   relational store comes first.
4. **App-only mode before local AI setup.** Everything works with no model
   installed.
5. **Explicit confirmation before model downloads, file scans, OCR, or
   background indexing.** Nothing heavy happens by surprise.
6. **Every generated answer must cite saved memories or imported sources.**
7. **Decisions are first-class objects, not just tagged notes.**

## What this means in practice

- **Private by default.** All data is local. Local AI is opt-in and runs through
  Ollama on your machine; no remote calls.
- **Models are never downloaded for you.** Setup prints the exact
  `ollama pull ...` commands and lets you run them.
- **Folders are never scanned automatically.** You always name the file or
  folder, and imports are preview-first.
- **AI output is always a draft.** Generated titles, summaries, tags, and
  reflections are shown for confirmation before anything is saved.
- **Answers are grounded.** If no saved memory or source matches, Waymark says
  so and invites you to capture or import more context — it does not fabricate.

## Guided first, commands second

The guided Textual interface is the primary experience: calm, warm, and
keyboard-driven, framed around attention and documentation coverage rather than
scoring your life. Every guided action has a direct CLI equivalent for
scripting and automation.
