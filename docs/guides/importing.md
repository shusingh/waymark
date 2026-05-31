# Importing your world

Waymark can pull existing notes and documents into memory cards **without losing
its memory-first identity**. Every import is explicit and preview-first:

- Folders are never scanned automatically — you always name the file or folder.
- Each imported file becomes a `sources` row and a sourced memory, so retrieval
  can cite it (for example `pdf: brief.pdf`).
- The same resolved file path is skipped on re-import unless you pass `--force`.

## Supported formats

| Format | Suffixes | How text is extracted | Dependency |
| --- | --- | --- | --- |
| Markdown | `.md`, `.markdown` | Heading + first paragraph | none |
| Plain text | `.txt`, `.text` | Raw text | none |
| PDF | `.pdf` | Existing text layer, **no OCR** | optional `pypdf` |
| Word | `.docx` | Paragraph text (no styles/images) | none (stdlib) |

!!! warning "No OCR"
    PDF import reads the existing text layer only. Scanned or image-only PDFs
    report *"no extractable text"* rather than running OCR.

## Import a single file

```bash
waymark import markdown .\notes\idea.md
waymark import text .\notes\standup.txt
waymark import pdf .\docs\brief.pdf
waymark import docx .\docs\weekly.docx
```

For the binary formats you can inspect the extracted card before saving:

```bash
waymark import pdf .\docs\brief.pdf --preview
waymark import docx .\docs\weekly.docx --preview
```

If `pypdf` is not installed, PDF import exits cleanly with the exact install
command (`pip install waymark[pdf]`).

## Import a whole folder

`waymark import folder` previews every supported file in a folder, then imports
them only when you add `--apply`:

```bash
waymark import folder .\dropbox                 # preview only
waymark import folder .\dropbox --apply         # import the previewed files
waymark import folder .\dropbox --apply --recursive --limit 100
```

!!! note "Legacy Markdown folder command"
    `waymark import markdown-folder` still works for older scripts, but new
    workflows should use `waymark import folder`. The unified command covers
    Markdown plus text, PDF, and DOCX files with the same preview-first safety
    model.

A batch **never aborts on a bad file**:

- Files whose path was already imported are reported as **duplicates**.
- Unreadable files (or PDFs with no extractable text) are reported as **skipped**.
- Everything else still imports.

Because imported paths are skipped, re-running the same command **resumes**
naturally — already-imported files are left alone.

!!! tip "Guided import"
    In the guided interface (`waymark`), the Import screen offers the same
    single-file buttons and a **Preview Folder → Apply Preview** flow for the
    multi-type folder import.

## After importing

```bash
waymark sources list          # what came from where
waymark ask "the topic"       # answers cite imported sources
```
