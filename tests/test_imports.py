from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from waymark.imports import (
    DuplicateDocxImportError,
    DuplicateMarkdownImportError,
    DuplicatePdfImportError,
    DuplicateTextImportError,
    MissingImportDependencyError,
    extract_docx_text,
    extract_markdown_summary,
    extract_markdown_title,
    extract_pdf_text,
    import_docx_file,
    import_markdown_file,
    import_markdown_folder,
    import_pdf_file,
    import_text_file,
    preview_docx_file,
    preview_markdown_file,
    preview_markdown_folder,
    preview_pdf_file,
    preview_text_file,
)
from waymark.storage import init_database, list_entries, list_sources


def test_extract_markdown_title_and_summary() -> None:
    raw_text = """---
tags: [project]
---

# Waymark Note

This is the first useful paragraph.

- A bullet that should not be the summary.
"""

    assert extract_markdown_title(raw_text) == "Waymark Note"
    assert extract_markdown_summary(raw_text) == "This is the first useful paragraph."


def test_preview_markdown_file_requires_single_markdown_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="single file"):
        preview_markdown_file(tmp_path)

    text_file = tmp_path / "note.txt"
    text_file.write_text("# Not Markdown", encoding="utf-8")
    with pytest.raises(ValueError, match="only accepts"):
        preview_markdown_file(text_file)


def test_import_markdown_file_creates_source_and_entry(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    markdown_path = tmp_path / "note.md"
    markdown_path.write_text(
        "# Imported Note\n\nThis should become a sourced memory.",
        encoding="utf-8",
    )
    init_database(db_path)

    result = import_markdown_file(db_path, markdown_path)

    entries = list_entries(db_path)
    sources = list_sources(db_path)
    assert result.entry_id == 1
    assert result.source_id == 1
    assert entries[0].title == "Imported Note"
    assert entries[0].source == "source:1"
    assert entries[0].tags == ("import", "markdown")
    assert sources[0].path == str(markdown_path.resolve())
    size_bytes = sources[0].metadata["size_bytes"]
    assert isinstance(size_bytes, int)
    assert size_bytes > 0


def test_import_markdown_file_skips_duplicate_path_by_default(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    markdown_path = tmp_path / "note.md"
    markdown_path.write_text("# Imported Note\n\nOnly import once.", encoding="utf-8")
    init_database(db_path)

    import_markdown_file(db_path, markdown_path)

    with pytest.raises(DuplicateMarkdownImportError, match="already imported"):
        import_markdown_file(db_path, markdown_path)

    assert len(list_entries(db_path)) == 1
    assert len(list_sources(db_path)) == 1

    forced = import_markdown_file(db_path, markdown_path, force=True)
    assert forced.entry_id == 2
    assert len(list_entries(db_path)) == 2
    assert len(list_sources(db_path)) == 2


def test_import_text_file_creates_source_and_entry(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    text_path = tmp_path / "note.txt"
    text_path.write_text(
        "Plain text title\n\nThis should become a sourced plain text memory.",
        encoding="utf-8",
    )
    init_database(db_path)

    preview = preview_text_file(text_path)
    result = import_text_file(db_path, text_path)

    entries = list_entries(db_path)
    sources = list_sources(db_path)
    assert preview.title == "Plain text title"
    assert result.entry_id == 1
    assert result.source_id == 1
    assert entries[0].title == "Plain text title"
    assert entries[0].source == "source:1"
    assert entries[0].tags == ("import", "text")
    assert sources[0].type == "text"
    assert sources[0].path == str(text_path.resolve())


def test_import_text_file_skips_duplicate_path_by_default(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    text_path = tmp_path / "note.text"
    text_path.write_text("Plain text memory.", encoding="utf-8")
    init_database(db_path)

    import_text_file(db_path, text_path)

    with pytest.raises(DuplicateTextImportError, match="already imported"):
        import_text_file(db_path, text_path)

    forced = import_text_file(db_path, text_path, force=True)
    assert forced.entry_id == 2
    assert len(list_entries(db_path)) == 2
    assert len(list_sources(db_path)) == 2


def test_preview_markdown_folder_defaults_to_top_level_only(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (tmp_path / "alpha.md").write_text("# Alpha\n\nTop-level note.", encoding="utf-8")
    (nested / "beta.md").write_text("# Beta\n\nNested note.", encoding="utf-8")

    preview = preview_markdown_folder(tmp_path)

    assert preview.root == tmp_path.resolve()
    assert preview.recursive is False
    assert preview.truncated is False
    assert [item.title for item in preview.files] == ["Alpha"]


def test_preview_markdown_folder_recursive_limit_and_skips(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (tmp_path / "alpha.md").write_text("# Alpha\n\nTop-level note.", encoding="utf-8")
    (tmp_path / "empty.md").write_text("   ", encoding="utf-8")
    (nested / "beta.markdown").write_text("# Beta\n\nNested note.", encoding="utf-8")
    (nested / "gamma.md").write_text("# Gamma\n\nAnother nested note.", encoding="utf-8")

    preview = preview_markdown_folder(tmp_path, recursive=True, limit=2)

    assert preview.recursive is True
    assert preview.truncated is True
    assert [item.title for item in preview.files] == ["Alpha", "Beta"]
    assert len(preview.skipped) == 1
    assert "empty.md" in preview.skipped[0]


def test_import_markdown_folder_creates_sources_and_entries(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    notes_path = tmp_path / "notes"
    notes_path.mkdir()
    (notes_path / "alpha.md").write_text("# Alpha\n\nFirst imported note.", encoding="utf-8")
    (notes_path / "beta.markdown").write_text("# Beta\n\nSecond imported note.", encoding="utf-8")
    init_database(db_path)

    result = import_markdown_folder(db_path, notes_path)

    entries = list_entries(db_path)
    sources = list_sources(db_path)
    assert len(result.imported) == 2
    assert sorted(entry.title for entry in entries) == ["Alpha", "Beta"]
    assert sorted(source.original_filename or "" for source in sources) == [
        "alpha.md",
        "beta.markdown",
    ]


def test_import_markdown_folder_skips_duplicates(tmp_path: Path) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    notes_path = tmp_path / "notes"
    notes_path.mkdir()
    (notes_path / "alpha.md").write_text("# Alpha\n\nFirst imported note.", encoding="utf-8")
    (notes_path / "beta.md").write_text("# Beta\n\nSecond imported note.", encoding="utf-8")
    init_database(db_path)

    first = import_markdown_folder(db_path, notes_path)
    second = import_markdown_folder(db_path, notes_path)

    assert len(first.imported) == 2
    assert second.imported == ()
    assert len(second.skipped) == 2
    assert "already imported" in second.skipped[0]
    assert len(list_entries(db_path)) == 2


def test_extract_docx_text_reads_paragraphs(
    tmp_path: Path, make_docx: Callable[[Path, list[str]], Path]
) -> None:
    docx_path = make_docx(
        tmp_path / "note.docx",
        ["Docx Title", "Body paragraph with detail."],
    )

    assert extract_docx_text(docx_path) == "Docx Title\n\nBody paragraph with detail."


def test_extract_docx_text_rejects_non_zip(tmp_path: Path) -> None:
    not_docx = tmp_path / "broken.docx"
    not_docx.write_text("this is not a zip archive", encoding="utf-8")

    with pytest.raises(ValueError, match="Could not read DOCX file"):
        extract_docx_text(not_docx)


def test_import_docx_file_creates_source_and_entry(
    tmp_path: Path, make_docx: Callable[[Path, list[str]], Path]
) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    docx_path = make_docx(
        tmp_path / "note.docx",
        ["Docx Memory", "This becomes a sourced docx memory."],
    )
    init_database(db_path)

    preview = preview_docx_file(docx_path)
    result = import_docx_file(db_path, docx_path)

    entries = list_entries(db_path)
    sources = list_sources(db_path)
    assert preview.title == "Docx Memory"
    assert result.entry_id == 1
    assert result.source_id == 1
    assert entries[0].title == "Docx Memory"
    assert entries[0].source == "source:1"
    assert entries[0].tags == ("docx", "import")
    assert sources[0].type == "docx"
    assert sources[0].path == str(docx_path.resolve())


def test_preview_docx_file_requires_extractable_text(
    tmp_path: Path, make_docx: Callable[[Path, list[str]], Path]
) -> None:
    docx_path = make_docx(tmp_path / "empty.docx", [])

    with pytest.raises(ValueError, match="No extractable text"):
        preview_docx_file(docx_path)


def test_preview_docx_file_rejects_wrong_suffix(tmp_path: Path) -> None:
    text_file = tmp_path / "note.txt"
    text_file.write_text("not a docx", encoding="utf-8")

    with pytest.raises(ValueError, match="only accepts"):
        preview_docx_file(text_file)


def test_import_docx_file_skips_duplicate_path_by_default(
    tmp_path: Path, make_docx: Callable[[Path, list[str]], Path]
) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    docx_path = make_docx(tmp_path / "note.docx", ["Docx", "Only import once."])
    init_database(db_path)

    import_docx_file(db_path, docx_path)

    with pytest.raises(DuplicateDocxImportError, match="already imported"):
        import_docx_file(db_path, docx_path)

    forced = import_docx_file(db_path, docx_path, force=True)
    assert forced.entry_id == 2
    assert len(list_entries(db_path)) == 2
    assert len(list_sources(db_path)) == 2


def test_extract_pdf_text_reads_text_layer(
    tmp_path: Path, make_minimal_pdf: Callable[[Path, str], Path]
) -> None:
    pytest.importorskip("pypdf")
    pdf_path = make_minimal_pdf(tmp_path / "note.pdf", "Hello Waymark")

    assert "Waymark" in extract_pdf_text(pdf_path)


def test_extract_pdf_text_without_pypdf_raises_missing_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "note.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 placeholder")
    # Make `import pypdf` fail as if the optional package were not installed.
    monkeypatch.setitem(sys.modules, "pypdf", None)

    with pytest.raises(MissingImportDependencyError, match="pypdf"):
        extract_pdf_text(pdf_path)


def test_import_pdf_file_creates_source_and_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    pdf_path = tmp_path / "note.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 placeholder")
    monkeypatch.setattr(
        "waymark.imports.extract_pdf_text",
        lambda _path: "PDF Memory\n\nExtracted body text.",
    )
    init_database(db_path)

    preview = preview_pdf_file(pdf_path)
    result = import_pdf_file(db_path, pdf_path)

    entries = list_entries(db_path)
    sources = list_sources(db_path)
    assert preview.title == "PDF Memory"
    assert result.entry_id == 1
    assert entries[0].tags == ("import", "pdf")
    assert sources[0].type == "pdf"
    assert sources[0].path == str(pdf_path.resolve())


def test_preview_pdf_file_requires_extractable_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "scan.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 placeholder")
    monkeypatch.setattr("waymark.imports.extract_pdf_text", lambda _path: "")

    with pytest.raises(ValueError, match="No extractable text"):
        preview_pdf_file(pdf_path)


def test_import_pdf_file_skips_duplicate_path_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "waymark.sqlite3"
    pdf_path = tmp_path / "note.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 placeholder")
    monkeypatch.setattr("waymark.imports.extract_pdf_text", lambda _path: "Imported once.")
    init_database(db_path)

    import_pdf_file(db_path, pdf_path)

    with pytest.raises(DuplicatePdfImportError, match="already imported"):
        import_pdf_file(db_path, pdf_path)

    forced = import_pdf_file(db_path, pdf_path, force=True)
    assert forced.entry_id == 2
    assert len(list_sources(db_path)) == 2
