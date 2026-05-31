from __future__ import annotations

import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

_DOCX_MAIN_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _build_docx(path: Path, paragraphs: list[str]) -> Path:
    """Write a minimal but valid DOCX containing the given paragraphs.

    Only ``word/document.xml`` is needed for Waymark's stdlib extractor.
    """

    body = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'
        for text in paragraphs
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{_DOCX_MAIN_NS}"><w:body>{body}</w:body></w:document>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document)
    return path


def _build_minimal_pdf(path: Path, text: str) -> Path:
    """Write a one-page PDF with a single text-showing operator.

    The cross-reference table offsets are computed so the file parses cleanly.
    """

    stream = f"BT /F1 24 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += str(index).encode("ascii") + b" 0 obj\n" + obj + b"\nendobj\n"

    xref_offset = len(pdf)
    pdf += b"xref\n0 " + str(len(objects) + 1).encode("ascii") + b"\n"
    pdf += b"0000000000 65535 f \n"
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n".encode("ascii")
    pdf += (
        b"trailer\n<< /Size "
        + str(len(objects) + 1).encode("ascii")
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_offset).encode("ascii")
        + b"\n%%EOF"
    )
    path.write_bytes(bytes(pdf))
    return path


@pytest.fixture
def make_docx() -> Callable[[Path, list[str]], Path]:
    return _build_docx


@pytest.fixture
def make_minimal_pdf() -> Callable[[Path, str], Path]:
    return _build_minimal_pdf
