"""Explicit, user-approved import helpers."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from waymark.memory import fallback_summary, fallback_title
from waymark.storage import Source, add_entry, add_source, get_source_by_path

MARKDOWN_SUFFIXES = {".md", ".markdown"}
TEXT_SUFFIXES = {".txt", ".text"}


@dataclass(frozen=True)
class MarkdownImportPreview:
    path: Path
    title: str
    summary: str
    raw_text: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class MarkdownImportResult:
    source_id: int
    entry_id: int
    title: str
    summary: str


@dataclass(frozen=True)
class MarkdownFolderPreview:
    root: Path
    files: tuple[MarkdownImportPreview, ...]
    skipped: tuple[str, ...]
    truncated: bool
    recursive: bool


@dataclass(frozen=True)
class MarkdownFolderImportResult:
    root: Path
    imported: tuple[MarkdownImportResult, ...]
    skipped: tuple[str, ...]
    truncated: bool
    recursive: bool


@dataclass(frozen=True)
class TextImportPreview:
    path: Path
    title: str
    summary: str
    raw_text: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class TextImportResult:
    source_id: int
    entry_id: int
    title: str
    summary: str


class DuplicateMarkdownImportError(ValueError):
    """Raised when a Markdown file has already been imported."""

    def __init__(self, path: Path, source: Source) -> None:
        super().__init__(
            f"Markdown file already imported as source #{source.id}: {path}"
        )
        self.path = path
        self.source = source


class DuplicateTextImportError(ValueError):
    """Raised when a plain text file has already been imported."""

    def __init__(self, path: Path, source: Source) -> None:
        super().__init__(
            f"Text file already imported as source #{source.id}: {path}"
        )
        self.path = path
        self.source = source


def preview_markdown_file(path: Path) -> MarkdownImportPreview:
    resolved_path = validate_markdown_file(path)
    raw_text = resolved_path.read_text(encoding="utf-8").strip()
    if not raw_text:
        raise ValueError("Markdown file is empty.")

    title = extract_markdown_title(raw_text) or resolved_path.stem
    summary = extract_markdown_summary(raw_text) or fallback_summary(raw_text)
    return MarkdownImportPreview(
        path=resolved_path,
        title=title,
        summary=summary,
        raw_text=raw_text,
        tags=("import", "markdown"),
    )


def import_markdown_file(
    db_path: Path,
    path: Path,
    *,
    force: bool = False,
) -> MarkdownImportResult:
    preview = preview_markdown_file(path)
    return import_markdown_preview(db_path, preview, force=force)


def import_markdown_preview(
    db_path: Path,
    preview: MarkdownImportPreview,
    *,
    force: bool = False,
) -> MarkdownImportResult:
    existing_source = get_source_by_path(
        db_path,
        source_type="markdown",
        path=str(preview.path),
    )
    if existing_source is not None and not force:
        raise DuplicateMarkdownImportError(preview.path, existing_source)

    source_id = add_source(
        db_path,
        source_type="markdown",
        path=str(preview.path),
        original_filename=preview.path.name,
        metadata={"size_bytes": preview.path.stat().st_size},
    )
    entry_id = add_entry(
        db_path,
        raw_text=preview.raw_text,
        memory_type="import",
        title=preview.title,
        summary=preview.summary,
        tags=preview.tags,
        source=f"source:{source_id}",
    )
    return MarkdownImportResult(
        source_id=source_id,
        entry_id=entry_id,
        title=preview.title,
        summary=preview.summary,
    )


def preview_text_file(path: Path) -> TextImportPreview:
    resolved_path = validate_text_file(path)
    raw_text = resolved_path.read_text(encoding="utf-8").strip()
    if not raw_text:
        raise ValueError("Text file is empty.")

    return TextImportPreview(
        path=resolved_path,
        title=fallback_title(raw_text),
        summary=fallback_summary(raw_text),
        raw_text=raw_text,
        tags=("import", "text"),
    )


def import_text_file(
    db_path: Path,
    path: Path,
    *,
    force: bool = False,
) -> TextImportResult:
    preview = preview_text_file(path)
    return import_text_preview(db_path, preview, force=force)


def import_text_preview(
    db_path: Path,
    preview: TextImportPreview,
    *,
    force: bool = False,
) -> TextImportResult:
    existing_source = get_source_by_path(
        db_path,
        source_type="text",
        path=str(preview.path),
    )
    if existing_source is not None and not force:
        raise DuplicateTextImportError(preview.path, existing_source)

    source_id = add_source(
        db_path,
        source_type="text",
        path=str(preview.path),
        original_filename=preview.path.name,
        metadata={"size_bytes": preview.path.stat().st_size},
    )
    entry_id = add_entry(
        db_path,
        raw_text=preview.raw_text,
        memory_type="import",
        title=preview.title,
        summary=preview.summary,
        tags=preview.tags,
        source=f"source:{source_id}",
    )
    return TextImportResult(
        source_id=source_id,
        entry_id=entry_id,
        title=preview.title,
        summary=preview.summary,
    )


def preview_markdown_folder(
    root: Path,
    *,
    recursive: bool = False,
    limit: int = 25,
) -> MarkdownFolderPreview:
    resolved_root = validate_markdown_folder(root)
    if limit < 1:
        raise ValueError("Markdown folder import limit must be at least 1.")

    previews: list[MarkdownImportPreview] = []
    skipped: list[str] = []
    truncated = False

    for markdown_path in iter_markdown_paths(resolved_root, recursive=recursive):
        if len(previews) >= limit:
            truncated = True
            break
        try:
            previews.append(preview_markdown_file(markdown_path))
        except (OSError, UnicodeDecodeError, ValueError) as error:
            skipped.append(f"{markdown_path}: {error}")

    return MarkdownFolderPreview(
        root=resolved_root,
        files=tuple(previews),
        skipped=tuple(skipped),
        truncated=truncated,
        recursive=recursive,
    )


def import_markdown_folder(
    db_path: Path,
    root: Path,
    *,
    recursive: bool = False,
    limit: int = 25,
    force: bool = False,
) -> MarkdownFolderImportResult:
    preview = preview_markdown_folder(root, recursive=recursive, limit=limit)
    imported: list[MarkdownImportResult] = []
    skipped = list(preview.skipped)
    for item in preview.files:
        try:
            imported.append(import_markdown_preview(db_path, item, force=force))
        except DuplicateMarkdownImportError as error:
            skipped.append(str(error))
    return MarkdownFolderImportResult(
        root=preview.root,
        imported=tuple(imported),
        skipped=tuple(skipped),
        truncated=preview.truncated,
        recursive=preview.recursive,
    )


def validate_markdown_file(path: Path) -> Path:
    resolved_path = path.expanduser().resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {resolved_path}")
    if not resolved_path.is_file():
        raise ValueError("Markdown import requires a single file path, not a folder.")
    if resolved_path.suffix.lower() not in MARKDOWN_SUFFIXES:
        raise ValueError("Markdown import only accepts .md or .markdown files.")
    return resolved_path


def validate_text_file(path: Path) -> Path:
    resolved_path = path.expanduser().resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(f"Text file not found: {resolved_path}")
    if not resolved_path.is_file():
        raise ValueError("Text import requires a single file path, not a folder.")
    if resolved_path.suffix.lower() not in TEXT_SUFFIXES:
        raise ValueError("Text import only accepts .txt or .text files.")
    return resolved_path


def validate_markdown_folder(path: Path) -> Path:
    resolved_path = path.expanduser().resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(f"Markdown folder not found: {resolved_path}")
    if not resolved_path.is_dir():
        raise ValueError("Markdown folder import requires a folder path.")
    return resolved_path


def iter_markdown_paths(root: Path, *, recursive: bool = False) -> Iterator[Path]:
    candidates = root.rglob("*") if recursive else root.iterdir()
    sorted_candidates = sorted(
        candidates,
        key=lambda candidate: candidate.relative_to(root).as_posix().lower(),
    )
    for candidate in sorted_candidates:
        if candidate.is_file() and candidate.suffix.lower() in MARKDOWN_SUFFIXES:
            yield candidate


def extract_markdown_title(raw_text: str) -> str | None:
    for line in raw_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or None
    return None


def extract_markdown_summary(raw_text: str) -> str | None:
    in_frontmatter = False
    for line in raw_text.splitlines():
        stripped = line.strip()
        if stripped == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter or not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(("- ", "* ", "> ", "```")):
            continue
        return fallback_summary(stripped)
    return None
