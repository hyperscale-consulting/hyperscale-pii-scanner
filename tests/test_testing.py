import io

from pypdf import PdfReader

from hyperscale.pii_scanner.testing import pdf_bytes


def test_pdf_bytes_draws_text_on_text_pages_and_nothing_on_none_pages():
    reader = PdfReader(io.BytesIO(pdf_bytes(["Jane Smith, LS1 4AP", None])))
    assert len(reader.pages) == 2
    assert "Jane Smith" in reader.pages[0].extract_text()
    assert reader.pages[1].extract_text().strip() == ""


def test_pdf_bytes_escapes_brackets_and_backslashes():
    reader = PdfReader(io.BytesIO(pdf_bytes([r"Ref (A) \ B"])))
    assert reader.pages[0].extract_text().strip() == r"Ref (A) \ B"


def test_pdf_bytes_is_deterministic():
    assert pdf_bytes(["a", None]) == pdf_bytes(["a", None])


def test_pdf_bytes_with_password_is_encrypted():
    assert PdfReader(io.BytesIO(pdf_bytes(["x"], password="p"))).is_encrypted
