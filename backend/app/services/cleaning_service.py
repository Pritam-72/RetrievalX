import re
import unicodedata
from collections import Counter

from app.services.extraction_service import PageText


def clean_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n[ \t]+", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def clean_pages(pages: list[PageText]) -> list[PageText]:
    cleaned_pages = [
        PageText(page.page_number, clean_text(page.text)) for page in pages
    ]
    repeated_lines = _repeating_lines(cleaned_pages)
    return [
        PageText(
            page.page_number,
            "\n".join(
                line
                for line in page.text.splitlines()
                if line.strip() not in repeated_lines
                and not _is_standalone_page_number(line)
            ).strip(),
        )
        for page in cleaned_pages
        if page.text.strip()
    ]


def _repeating_lines(pages: list[PageText]) -> set[str]:
    if len(pages) < 2:
        return set()
    occurrences = Counter(
        line.strip()
        for page in pages
        for line in set(page.text.splitlines())
        if line.strip() and len(line.strip()) < 100
    )
    minimum_occurrences = len(pages) / 2
    return {line for line, count in occurrences.items() if count > minimum_occurrences}


def _is_standalone_page_number(line: str) -> bool:
    return bool(re.fullmatch(r"\s*\d+\s*", line))
