# Changelog

## Unreleased

- Added `waymark today` and a guided Today screen, an app-only daily loop showing
  today's captures, due reflection windows, decision review/outcome items, and
  copyable next commands. The guided screen also opens daily capture, the next
  due reflection, and decision review directly.
- Added a Daily Loop guide to the documentation site.
- Added CI and release wheel-install smoke tests for built packages.

## 0.1.0 - 2026-05-31

Initial public release.

- Local-first SQLite memory storage with a guided Textual interface.
- Capture, timeline, memory detail, editing, grounded ask, and app-only
  reflections.
- Decision tracking with linked memories, review queues, and outcomes.
- Explicit imports for Markdown, text, PDF text layers, DOCX paragraphs, and
  preview-first folder batches.
- Optional local AI through Ollama for capture structuring, embeddings, and
  semantic retrieval.
- Markdown exports for memories, timeline slices, reflections, and trends.
- Versioned JSON backup/restore and portable readable backup bundles.
- MkDocs documentation site and downloadable GitHub Release packages.
