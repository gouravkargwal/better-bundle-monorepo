"""
AI Rerank API - translation endpoint between Gorse's reranker_api contract and
Google Gemini/Vertex AI.

Contract confirmed against Gorse v0.5.11 source (common/reranker/client.go,
logics/chat.go), not just docs:
  - Gorse sends: POST {url}, "Authorization: Bearer {auth_token}",
    body {"model": str, "query": str, "documents": [str], "top_n"?: int}
    (Gorse never sets top_n in practice).
  - Gorse expects back: {"model": str, "usage": {"total_tokens": int},
    "results": [{"index": int, "relevance_score": float}, ...]}.
  - Order-sensitive: Gorse walks `results` in array order to build the final
    ranking - it does not re-sort by relevance_score itself. This endpoint
    must return `results` already sorted descending by score.
"""

from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.config.settings import settings
from app.core.logging import get_logger
from app.shared.ai_provider import get_ai_provider

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/ai-rerank", tags=["ai-rerank"])


class RerankRequest(BaseModel):
    model: str
    query: str
    documents: List[str]
    top_n: Optional[int] = None


class RerankResultItem(BaseModel):
    index: int
    relevance_score: float


class Usage(BaseModel):
    total_tokens: int = 0


class RerankResponse(BaseModel):
    model: str
    usage: Usage
    results: List[RerankResultItem]


def _check_auth(authorization: Optional[str]) -> None:
    expected_token = settings.ml.AI_RERANK_TOKEN
    if not expected_token:
        return
    if authorization != f"Bearer {expected_token}":
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token")


@router.post("/rerank", response_model=RerankResponse)
async def rerank(
    request: RerankRequest,
    authorization: Optional[str] = Header(default=None),
):
    """Score and rank candidate documents against a query, Jina-rerank-shaped."""
    _check_auth(authorization)

    if not request.documents:
        return RerankResponse(
            model=request.model, usage=Usage(total_tokens=0), results=[]
        )

    try:
        provider = get_ai_provider()
        scores = await provider.score_relevance(request.query, request.documents)
    except Exception as e:
        logger.error(f"Rerank scoring failed: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Rerank scoring failed: {str(e)}")

    ranked_indices = sorted(
        range(len(request.documents)), key=lambda i: scores[i], reverse=True
    )
    if request.top_n:
        ranked_indices = ranked_indices[: request.top_n]

    results = [
        RerankResultItem(index=i, relevance_score=scores[i]) for i in ranked_indices
    ]

    return RerankResponse(
        model=request.model, usage=Usage(total_tokens=0), results=results
    )
