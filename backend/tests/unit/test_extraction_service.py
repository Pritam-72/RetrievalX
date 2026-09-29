import fitz
import pytest

from app.services.extraction_service import NoExtractableTextError, extract_pdf


def _write_pdf(path, page_texts: list[str]) -> None:
    document = fitz.open()
    for text in page_texts or [""]:
        page = document.new_page()
        page.insert_textbox((72, 72, 520, 760), text, fontsize=10)
    document.save(path)
    document.close()


def test_extract_pdf_returns_ordered_page_text(tmp_path) -> None:
    first_page = "First page content. " * 20
    second_page = "Second page content. " * 20
    pdf_path = tmp_path / "document.pdf"
    _write_pdf(pdf_path, [first_page, second_page])

    pages = extract_pdf(pdf_path)

    assert [page.page_number for page in pages] == [1, 2]
    assert "First page content." in pages[0].text
    assert "Second page content." in pages[1].text


@pytest.mark.parametrize("page_texts", [[], [""], ["image-only page"]])
def test_extract_pdf_rejects_missing_or_insufficient_text(tmp_path, page_texts) -> None:
    pdf_path = tmp_path / "scanned.pdf"
    _write_pdf(pdf_path, page_texts)

    with pytest.raises(NoExtractableTextError, match="No extractable text"):
        extract_pdf(pdf_path)
