import re
from dataclasses import dataclass

from app.services.extraction_service import PageText

CHUNK_TARGET_TOKENS = 600
CHUNK_OVERLAP_TOKENS = 80
CHUNK_MIN_TOKENS = 100


@dataclass(frozen=True, slots=True)
class Chunk:
    content: str
    page_start: int
    page_end: int
    section_title: str | None
    token_count: int


def chunk_pages(
    pages: list[PageText],
    target_tokens: int = CHUNK_TARGET_TOKENS,
    overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
    min_tokens: int = CHUNK_MIN_TOKENS,
) -> list[Chunk]:
    if target_tokens <= 0 or overlap_tokens < 0 or overlap_tokens >= target_tokens:
        raise ValueError("chunk target must be positive and greater than overlap")

    tokens = _page_tokens(pages)
    if not tokens:
        return []

    chunks: list[Chunk] = []
    start = 0
    total = len(tokens)
    while start < total:
        remaining = total - start
        if remaining < min_tokens and chunks:
            start = max(0, total - target_tokens)
        end = min(total, start + target_tokens)
        selected = tokens[start:end]
        chunks.append(_build_chunk(selected))
        if end == total:
            break
        start = end - overlap_tokens
    return chunks


def _page_tokens(pages: list[PageText]) -> list[tuple[str, int, str | None]]:
    result: list[tuple[str, int, str | None]] = []
    section_title: str | None = None
    for page in pages:
        for line in page.text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if _looks_like_heading(stripped):
                section_title = stripped.lstrip("#").strip()
            result.extend(
                (token, page.page_number, section_title) for token in stripped.split()
            )
    return result


def _build_chunk(tokens: list[tuple[str, int, str | None]]) -> Chunk:
    return Chunk(
        content=" ".join(token for token, _, _ in tokens),
        page_start=min(page for _, page, _ in tokens),
        page_end=max(page for _, page, _ in tokens),
        section_title=next(
            (section for _, _, section in tokens if section is not None), None
        ),
        token_count=len(tokens),
    )


def _looks_like_heading(line: str) -> bool:
    return bool(
        line.startswith("#")
        or re.match(r"^\d+(?:\.\d+)*\s+\S+", line)
        or (len(line.split()) <= 12 and line.isupper())
    )
