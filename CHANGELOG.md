# Changelog

## Unreleased

## 0.2.0 - 2026-05-31

- Added `waymark today` and a guided Today screen, an app-only daily loop showing
  today's captures, due reflection windows, decision review/outcome items, and
  copyable next commands. The guided screen also opens daily capture, the next
  due reflection, and decision review directly.
- Added `waymark today --commands-only` for quick copy/paste or script-friendly
  daily next actions.
- Surfaced the daily loop in the plain `waymark --plain` welcome menu.
- Clarified public release install commands with direct `pip` and `pipx` wheel
  URLs.
- Added a release workflow guard that requires the pushed tag to match the
  package version.
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
