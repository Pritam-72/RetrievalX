from uuid import uuid4

import numpy as np
import pytest

from app.rag.grounding import REFUSAL_MESSAGE
from app.rag.llm_client import StubLLMClient
from app.rag.pipeline import answer_question
from app.rag.retriever import Candidate


class FakeEmbedder:
    def embed_query(self, question: str) -> np.ndarray:
        return np.ones(384, dtype=np.float32)


class FakeRetriever:
    def __init__(self, candidates: list[Candidate]) -> None:
        self.candidates = candidates

    async def search(self, *args, **kwargs) -> list[Candidate]:
        return self.candidates


def candidate() -> Candidate:
    return Candidate(
        chunk_id=uuid4(),
        document_id=uuid4(),
        document_name="notes.pdf",
        content="Paris is the capital of France.",
        page_start=1,
        page_end=1,
        cosine_score=0.9,
    )


@pytest.mark.asyncio
async def test_answer_question_refuses_without_calling_llm() -> None:
    llm = StubLLMClient('{"answerable": true, "answer": "leak", "citations": [1]}')

    result = await answer_question(
        None,
        user_id=uuid4(),
        document_ids=[uuid4()],
        question="Who invented Python?",
        retriever=FakeRetriever([]),
        embedder=FakeEmbedder(),
        llm=llm,
    )

    assert result.answer == REFUSAL_MESSAGE
    assert result.grounded is False
    assert result.sources == []
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_answer_question_returns_grounded_source() -> None:
    llm = StubLLMClient(
        '{"answerable": true, "answer": "Paris is the capital. [1]", "citations": [1]}'
    )

    result = await answer_question(
        None,
        user_id=uuid4(),
        document_ids=[uuid4()],
        question="What is the capital?",
        retriever=FakeRetriever([candidate()]),
        embedder=FakeEmbedder(),
        llm=llm,
    )

    assert result.grounded is True
    assert result.sources[0].index == 1
    assert llm.calls == 1
