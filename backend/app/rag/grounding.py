from dataclasses import dataclass
from uuid import UUID

REFUSAL_MESSAGE = "I couldn't find the answer in the uploaded documents."


@dataclass(frozen=True, slots=True)
class Source:
    index: int
    chunk_id: UUID
    document_id: UUID
    document: str
    page: int | None
    page_end: int | None
    snippet: str


@dataclass(frozen=True, slots=True)
class PipelineResult:
    answer: str
    grounded: bool
    sources: list[Source]


def refusal() -> PipelineResult:
    return PipelineResult(answer=REFUSAL_MESSAGE, grounded=False, sources=[])
