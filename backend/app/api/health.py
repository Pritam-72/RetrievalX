from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    db: Literal["not_configured"]
    embedding_model: Literal["not_loaded"]
    reranker: Literal["not_loaded"]
    llm: Literal["not_configured"]


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        db="not_configured",
        embedding_model="not_loaded",
        reranker="not_loaded",
        llm="not_configured",
    )
