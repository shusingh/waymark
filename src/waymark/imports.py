"""Explicit, user-approved import helpers."""

from __future__ import annotations

import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from waymark.memory import fallback_summary, fallback_title
from waymark.storage import Source, add_entry, add_source, get_source_by_path

MARKDOWN_SUFFIXES = {".md", ".markdown"}
TEXT_SUFFIXES = {".txt", ".text"}
PDF_SUFFIXES = {".pdf"}
DOCX_SUFFIXES = {".docx"}

# All single-file suffixes a folder import can pick up, mapped to source type.
IMPORT_SUFFIXES = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
    ".text": "text",
    ".pdf": "pdf",
    ".docx": "docx",
}

# WordprocessingML main namespace used inside word/document.xml.
_DOCX_MAIN_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


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
class FolderFilePreview:
    path: Path
    source_type: str
    title: str
    summary: str


@dataclass(frozen=True)
class FolderImportPreview:
    root: Path
    files: tuple[FolderFilePreview, ...]
    skipped: tuple[str, ...]
    truncated: bool
    recursive: bool


@dataclass(frozen=True)
class FolderImportItem:
    source_type: str
    source_id: int
    entry_id: int
    title: str


@dataclass(frozen=True)
class FolderImportResult:
    root: Path
    imported: tuple[FolderImportItem, ...]
    duplicates: tuple[str, ...]
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


@dataclass(frozen=True)
class PdfImportPreview:
    path: Path
    title: str
    summary: str
    raw_text: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class PdfImportResult:
    source_id: int
    entry_id: int
    title: str
    summary: str


@dataclass(frozen=True)
class DocxImportPreview:
    path: Path
    title: str
    summary: str
    raw_text: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class DocxImportResult:
    source_id: int
    entry_id: int
    title: str
    summary: str


class MissingImportDependencyError(RuntimeError):
    """Raised when an optional import dependency is not installed."""

    def __init__(self, *, file_format: str, package: str, extra: str) -> None:
        super().__init__(
            f"{file_format} import needs the optional '{package}' package. "
            f"Install it with: pip install waymark[{extra}]"
        )
        self.file_format = file_format
        self.package = package
        self.extra = extra


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


class DuplicatePdfImportError(ValueError):
    """Raised when a PDF file has already been imported."""

    def __init__(self, path: Path, source: Source) -> None:
        super().__init__(
            f"PDF file already imported as source #{source.id}: {path}"
        )
        self.path = path
        self.source = source


class DuplicateDocxImportError(ValueError):
    """Raised when a DOCX file has already been imported."""

    def __init__(self, path: Path, source: Source) -> None:
        super().__init__(
            f"DOCX file already imported as source #{source.id}: {path}"
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


def preview_pdf_file(path: Path) -> PdfImportPreview:
    resolved_path = validate_pdf_file(path)
    raw_text = extract_pdf_text(resolved_path).strip()
    if not raw_text:
        raise ValueError(
            "No extractable text found in this PDF. It may be scanned or image-only; "
            "Waymark does not run OCR."
        )

    return PdfImportPreview(
        path=resolved_path,
        title=fallback_title(raw_text),
        summary=fallback_summary(raw_text),
        raw_text=raw_text,
        tags=("import", "pdf"),
    )


def import_pdf_file(
    db_path: Path,
    path: Path,
    *,
    force: bool = False,
) -> PdfImportResult:
    preview = preview_pdf_file(path)
    return import_pdf_preview(db_path, preview, force=force)


def import_pdf_preview(
    db_path: Path,
    preview: PdfImportPreview,
    *,
    force: bool = False,
) -> PdfImportResult:
    existing_source = get_source_by_path(
        db_path,
        source_type="pdf",
        path=str(preview.path),
    )
    if existing_source is not None and not force:
        raise DuplicatePdfImportError(preview.path, existing_source)

    source_id = add_source(
        db_path,
        source_type="pdf",
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
    return PdfImportResult(
        source_id=source_id,
        entry_id=entry_id,
        title=preview.title,
        summary=preview.summary,
    )


def preview_docx_file(path: Path) -> DocxImportPreview:
    resolved_path = validate_docx_file(path)
    raw_text = extract_docx_text(resolved_path).strip()
    if not raw_text:
        raise ValueError("No extractable text found in this DOCX file.")

    return DocxImportPreview(
        path=resolved_path,
        title=fallback_title(raw_text),
        summary=fallback_summary(raw_text),
        raw_text=raw_text,
        tags=("import", "docx"),
    )


def import_docx_file(
    db_path: Path,
    path: Path,
    *,
    force: bool = False,
) -> DocxImportResult:
    preview = preview_docx_file(path)
    return import_docx_preview(db_path, preview, force=force)


def import_docx_preview(
    db_path: Path,
    preview: DocxImportPreview,
    *,
    force: bool = False,
) -> DocxImportResult:
    existing_source = get_source_by_path(
        db_path,
        source_type="docx",
        path=str(preview.path),
    )
    if existing_source is not None and not force:
        raise DuplicateDocxImportError(preview.path, existing_source)

    source_id = add_source(
        db_path,
        source_type="docx",
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
    return DocxImportResult(
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


# Union of the single-file import result types a folder import can produce.
_ImportResult = (
    MarkdownImportResult | TextImportResult | PdfImportResult | DocxImportResult
)

# Errors raised when a single previewed file is already imported.
_DUPLICATE_IMPORT_ERRORS = (
    DuplicateMarkdownImportError,
    DuplicateTextImportError,
    DuplicatePdfImportError,
    DuplicateDocxImportError,
)


def _preview_importable_file(path: Path) -> FolderFilePreview:
    source_type = IMPORT_SUFFIXES[path.suffix.lower()]
    if source_type == "markdown":
        preview: MarkdownImportPreview | TextImportPreview | PdfImportPreview | DocxImportPreview
        preview = preview_markdown_file(path)
    elif source_type == "text":
        preview = preview_text_file(path)
    elif source_type == "pdf":
        preview = preview_pdf_file(path)
    else:
        preview = preview_docx_file(path)
    return FolderFilePreview(
        path=preview.path,
        source_type=source_type,
        title=preview.title,
        summary=preview.summary,
    )


def _import_importable_file(db_path: Path, path: Path, *, force: bool) -> _ImportResult:
    source_type = IMPORT_SUFFIXES[path.suffix.lower()]
    if source_type == "markdown":
        return import_markdown_file(db_path, path, force=force)
    if source_type == "text":
        return import_text_file(db_path, path, force=force)
    if source_type == "pdf":
        return import_pdf_file(db_path, path, force=force)
    return import_docx_file(db_path, path, force=force)


def preview_import_folder(
    root: Path,
    *,
    recursive: bool = False,
    limit: int = 25,
) -> FolderImportPreview:
    resolved_root = validate_import_folder(root)
    if limit < 1:
        raise ValueError("Folder import limit must be at least 1.")

    previews: list[FolderFilePreview] = []
    skipped: list[str] = []
    truncated = False

    for path in iter_importable_paths(resolved_root, recursive=recursive):
        if len(previews) >= limit:
            truncated = True
            break
        try:
            previews.append(_preview_importable_file(path))
        except (OSError, UnicodeDecodeError, ValueError, MissingImportDependencyError) as error:
            skipped.append(f"{path}: {error}")

    return FolderImportPreview(
        root=resolved_root,
        files=tuple(previews),
        skipped=tuple(skipped),
        truncated=truncated,
        recursive=recursive,
    )


def import_folder(
    db_path: Path,
    root: Path,
    *,
    recursive: bool = False,
    limit: int = 25,
    force: bool = False,
) -> FolderImportResult:
    preview = preview_import_folder(root, recursive=recursive, limit=limit)
    imported: list[FolderImportItem] = []
    duplicates: list[str] = []
    skipped = list(preview.skipped)
    for item in preview.files:
        try:
            result = _import_importable_file(db_path, item.path, force=force)
        except _DUPLICATE_IMPORT_ERRORS as error:
            duplicates.append(str(error))
            continue
        except (OSError, UnicodeDecodeError, ValueError, MissingImportDependencyError) as error:
            skipped.append(f"{item.path}: {error}")
            continue
        imported.append(
            FolderImportItem(
                source_type=item.source_type,
                source_id=result.source_id,
                entry_id=result.entry_id,
                title=result.title,
            )
        )
    return FolderImportResult(
        root=preview.root,
        imported=tuple(imported),
        duplicates=tuple(duplicates),
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


def validate_pdf_file(path: Path) -> Path:
    resolved_path = path.expanduser().resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(f"PDF file not found: {resolved_path}")
    if not resolved_path.is_file():
        raise ValueError("PDF import requires a single file path, not a folder.")
    if resolved_path.suffix.lower() not in PDF_SUFFIXES:
        raise ValueError("PDF import only accepts .pdf files.")
    return resolved_path


def validate_docx_file(path: Path) -> Path:
    resolved_path = path.expanduser().resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(f"DOCX file not found: {resolved_path}")
    if not resolved_path.is_file():
        raise ValueError("DOCX import requires a single file path, not a folder.")
    if resolved_path.suffix.lower() not in DOCX_SUFFIXES:
        raise ValueError("DOCX import only accepts .docx files.")
    return resolved_path


def validate_markdown_folder(path: Path) -> Path:
    resolved_path = path.expanduser().resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(f"Markdown folder not found: {resolved_path}")
    if not resolved_path.is_dir():
        raise ValueError("Markdown folder import requires a folder path.")
    return resolved_path


def validate_import_folder(path: Path) -> Path:
    resolved_path = path.expanduser().resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(f"Import folder not found: {resolved_path}")
    if not resolved_path.is_dir():
        raise ValueError("Folder import requires a folder path.")
    return resolved_path


def iter_importable_paths(root: Path, *, recursive: bool = False) -> Iterator[Path]:
    candidates = root.rglob("*") if recursive else root.iterdir()
    sorted_candidates = sorted(
        candidates,
        key=lambda candidate: candidate.relative_to(root).as_posix().lower(),
    )
    for candidate in sorted_candidates:
        if candidate.is_file() and candidate.suffix.lower() in IMPORT_SUFFIXES:
            yield candidate


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


def extract_pdf_text(path: Path) -> str:
    """Extract the text layer of a PDF.

    Requires the optional ``pypdf`` dependency. No OCR is performed, so
    scanned or image-only PDFs return no text.
    """

    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as error:
        raise MissingImportDependencyError(
            file_format="PDF", package="pypdf", extra="pdf"
        ) from error

    try:
        reader = PdfReader(str(path))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except (PdfReadError, OSError, ValueError) as error:
        raise ValueError(f"Could not read PDF file: {error}") from error

    return "\n\n".join(part for part in pages if part).strip()


def extract_docx_text(path: Path) -> str:
    """Extract paragraph text from a DOCX file using only the standard library.

    A DOCX file is an Office Open XML package: a ZIP archive whose
    ``word/document.xml`` holds the document body. We read the text runs
    (``w:t``) within each paragraph (``w:p``) and join paragraphs with blank
    lines. No styles, images, or embedded objects are imported.
    """

    try:
        with zipfile.ZipFile(path) as archive:
            xml_bytes = archive.read("word/document.xml")
    except KeyError as error:
        raise ValueError("DOCX file is missing word/document.xml.") from error
    except (zipfile.BadZipFile, OSError) as error:
        raise ValueError(
            f"Could not read DOCX file: {error}"
        ) from error

    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as error:
        raise ValueError(f"Could not parse DOCX document.xml: {error}") from error

    paragraph_tag = f"{{{_DOCX_MAIN_NS}}}p"
    text_tag = f"{{{_DOCX_MAIN_NS}}}t"
    paragraphs: list[str] = []
    for paragraph in root.iter(paragraph_tag):
        runs = [node.text for node in paragraph.iter(text_tag) if node.text]
        text = "".join(runs).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs).strip()
