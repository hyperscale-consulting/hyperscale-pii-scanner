"""Test helpers: build small PDFs in code.

For this library's tests and for apps that test their scan. A fixture built
here keeps its planted identifiers visible in the test source, so no binary
document is ever committed. Not for production use.
"""

from __future__ import annotations

import io
from collections.abc import Sequence


def _escape(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return escaped.encode("latin-1")


def _content(text: str | None) -> bytes:
    if text is None:
        return b""
    return b"BT /F1 12 Tf 72 720 Td (" + _escape(text) + b") Tj ET"


def pdf_bytes(pages: Sequence[str | None], *, password: str | None = None) -> bytes:
    """A minimal PDF with one page per item.

    A ``str`` page draws that text (Latin-1) in Helvetica; a ``None`` page has
    no text at all, as a scanned page has none. The output is the same for the
    same arguments unless ``password`` is given, which encrypts the file
    (RC4-128, needing the ``documents`` extra's ``pypdf``).
    """
    if not pages:
        raise ValueError("a PDF needs at least one page")
    count = len(pages)
    # Objects: 1 catalog, 2 pages tree, 3 font, then a page and its content
    # stream for each page.
    page_ids = [4 + 2 * i for i in range(count)]
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids ["
        + b" ".join(b"%d 0 R" % pid for pid in page_ids)
        + b"] /Count %d >>" % count,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for pid, text in zip(page_ids, pages, strict=True):
        stream = _content(text)
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % (pid + 1)
        )
        objects.append(
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"
        )

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, xref)
    )
    data = out.getvalue()
    if password is None:
        return data

    from pypdf import PdfReader
    from pypdf import PdfWriter

    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
    writer.encrypt(user_password=password, algorithm="RC4-128")
    encrypted = io.BytesIO()
    writer.write(encrypted)
    return encrypted.getvalue()
