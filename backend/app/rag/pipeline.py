from collections.abc import Sequence
from time import perf_counter
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.grounding import PipelineResult, Source, refusal
from app.rag.llm_client import LLMAnswer, LLMClient, parse_llm_answer
from app.rag.prompts import SYSTEM_PROMPT, build_user_message
from app.rag.retriever import Candidate, Retriever
from app.services.embedding_service import EmbeddingService


async def answer_question(
    session: AsyncSession,
    *,
    user_id: UUID,
    document_ids: Sequence[UUID],
    question: str,
    retriever: Retriever,
    embedder: EmbeddingService,
    llm: LLMClient,
    min_cosine: float = 0.0,
) -> PipelineResult:
    started = perf_counter()
    query_embedding = embedder.embed_query(question)
    candidates = await retriever.search(
        session,
        user_id=user_id,
        document_ids=document_ids,
        query_embedding=query_embedding,
        min_cosine=min_cosine,
    )
    debug = {
        "top_scores": [candidate.cosine_score for candidate in candidates],
        "gate_outcomes": {"cosine_floor": bool(candidates)},
        "timings_ms": {"retrieval": round((perf_counter() - started) * 1000, 2)},
    }
    if not candidates:
        result = refusal()
        result.debug.update(debug)
        return result

    raw = await llm.generate(SYSTEM_PROMPT, build_user_message(question, candidates))
    result = parse_llm_answer(raw)
    debug["gate_outcomes"]["answerable"] = result.answerable
    if not result.answerable or not result.answer.strip():
        refused = refusal()
        refused.debug.update(debug)
        return refused
    grounded = grounded_result(result, candidates)
    grounded.debug.update(debug)
    return grounded


def grounded_result(
    result: LLMAnswer, candidates: Sequence[Candidate]
) -> PipelineResult:
    sources = [
        _source_for_index(index, candidates[index - 1])
        for index in result.citations
        if 1 <= index <= len(candidates)
    ]
    return PipelineResult(answer=result.answer, grounded=True, sources=sources)


def _source_for_index(index: int, candidate: Candidate) -> Source:
    return Source(
        index=index,
        chunk_id=candidate.chunk_id,
        document_id=candidate.document_id,
        document=candidate.document_name,
        page=candidate.page_start,
        page_end=candidate.page_end,
        snippet=candidate.content[:200].strip(),
    )
