from app.services.cleaning_service import clean_pages, clean_text
from app.services.extraction_service import PageText


def test_clean_text_normalizes_spacing_and_dehyphenates() -> None:
    text = "Cafe\u0301   text\nexecu-\ntion\n\n\nnext paragraph"

    assert clean_text(text) == "Caf\u00e9 text\nexecution\n\nnext paragraph"


def test_clean_pages_removes_repeated_headers_and_page_numbers() -> None:
    pages = [
        PageText(1, "Document Header\n1\nFirst page content"),
        PageText(2, "Document Header\n2\nSecond page content"),
        PageText(3, "Document Header\n3\nThird page content"),
    ]

    cleaned = clean_pages(pages)

    assert [page.page_number for page in cleaned] == [1, 2, 3]
    assert [page.text for page in cleaned] == [
        "First page content",
        "Second page content",
        "Third page content",
    ]
