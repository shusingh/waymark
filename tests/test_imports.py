from __future__ import annotations

from pathlib import Path

import pytest

from waymark.imports import (
    DuplicateMarkdownImportError,
    DuplicateTextImportError,
    extract_markdown_summary,
    extract_markdown_title,
    import_markdown_file,
    import_markdown_folder,
    import_text_file,
    preview_markdown_file,
    preview_markdown_folder,
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
