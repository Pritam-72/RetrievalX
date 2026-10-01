from dataclasses import dataclass
from pathlib import Path

import fitz

MIN_AVERAGE_TEXT_CHARS = 200


class NoExtractableTextError(ValueError):
    """Raised when a PDF has no usable text for the ingestion pipeline."""


@dataclass(frozen=True, slots=True)
class PageText:
    page_number: int
    text: str


def extract_pdf(path: Path) -> list[PageText]:
    """Extract ordered, page-numbered text and reject likely scanned PDFs."""
    with fitz.open(path) as document:
        pages = [
            PageText(page_number=index + 1, text=_extract_page_text(page))
            for index, page in enumerate(document)
        ]

    total_characters = sum(len(page.text) for page in pages)
    average_characters = total_characters / len(pages) if pages else 0
    if not pages or average_characters < MIN_AVERAGE_TEXT_CHARS:
        raise NoExtractableTextError("No extractable text (scanned document?)")

    return pages


def extract_file(path: Path, file_type: str) -> list[PageText]:
    if file_type == "pdf":
        return extract_pdf(path)
    if file_type in {"txt", "md"}:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            raise NoExtractableTextError("No extractable text")
        return [PageText(page_number=1, text=text)]
    if file_type == "docx":
        return _extract_docx(path)
    raise ValueError(f"Unsupported file type: {file_type}")


def _extract_docx(path: Path) -> list[PageText]:
    from docx import Document

    document = Document(path)
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs]
    text = "\n\n".join(paragraph for paragraph in paragraphs if paragraph)
    if not text:
        raise NoExtractableTextError("No extractable text")
    return [PageText(page_number=1, text=text)]


def _extract_page_text(page: fitz.Page) -> str:
    blocks = page.get_text("blocks")
    text_blocks = [block for block in blocks if len(block) > 6 and block[4].strip()]
    text_blocks.sort(key=lambda block: (block[1], block[0]))
    return "\n\n".join(block[4].strip() for block in text_blocks)
