from app.services.chunking_service import chunk_pages
from app.services.extraction_service import PageText


def test_chunk_pages_respects_size_overlap_and_page_mapping() -> None:
    pages = [
        PageText(1, "INTRODUCTION\n" + "one " * 8),
        PageText(2, "2 Methods\n" + "two " * 8),
    ]

    chunks = chunk_pages(pages, target_tokens=6, overlap_tokens=2, min_tokens=3)

    assert len(chunks) > 1
    assert all(chunk.token_count <= 6 for chunk in chunks)
    assert all(chunk.page_start <= chunk.page_end for chunk in chunks)
    assert chunks[0].section_title == "INTRODUCTION"
    assert set(chunks[0].content.split()[-2:]) & set(chunks[1].content.split()[:2])


def test_chunk_pages_returns_empty_for_empty_input() -> None:
    assert chunk_pages([]) == []
