"""
Google AI Provider - Gemini (AI Studio) / Vertex AI

Backs two Gorse-facing features:
  - Item embeddings (computed here, attached to Gorse item Labels)
  - LLM-based reranking (scores query/document relevance for the ai_rerank endpoint)

Provider is selected by settings.ml.AI_PROVIDER:
  - "gemini": AI Studio, authenticated with a static API key (staging)
  - "vertex": Vertex AI, authenticated via ADC/service-account (prod)
"""

from typing import List

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.config.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class _RelevanceScores(BaseModel):
    scores: List[float]


class AIProvider:
    """Thin client wrapping google-genai for embeddings and relevance scoring."""

    def __init__(self):
        ml = settings.ml
        self._embedding_model = ml.AI_EMBEDDING_MODEL
        self._embedding_dimensions = ml.AI_EMBEDDING_DIMENSIONS
        self._chat_model = ml.AI_CHAT_MODEL

        if ml.AI_PROVIDER == "vertex":
            self._client = genai.Client(
                vertexai=True,
                project=ml.VERTEX_PROJECT_ID,
                location=ml.VERTEX_LOCATION,
            )
        else:
            self._client = genai.Client(api_key=ml.GEMINI_API_KEY)

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Compute an embedding vector per input text, preserving order."""
        if not texts:
            return []

        response = await self._client.aio.models.embed_content(
            model=self._embedding_model,
            contents=texts,
            config=types.EmbedContentConfig(
                output_dimensionality=self._embedding_dimensions
            ),
        )
        return [embedding.values for embedding in response.embeddings]

    async def score_relevance(self, query: str, documents: List[str]) -> List[float]:
        """Score each document's relevance to the query, in the same order as `documents`."""
        if not documents:
            return []

        prompt = self._build_scoring_prompt(query, documents)
        response = await self._client.aio.models.generate_content(
            model=self._chat_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_RelevanceScores,
            ),
        )
        parsed: _RelevanceScores = response.parsed
        scores = list(parsed.scores) if parsed else []

        if len(scores) != len(documents):
            logger.warning(
                f"Rerank score count mismatch: got {len(scores)} scores for "
                f"{len(documents)} documents; padding/truncating to match"
            )
            if len(scores) < len(documents):
                scores.extend([0.0] * (len(documents) - len(scores)))
            else:
                scores = scores[: len(documents)]

        return scores

    @staticmethod
    def _build_scoring_prompt(query: str, documents: List[str]) -> str:
        numbered_docs = "\n".join(
            f"{i}: {doc}" for i, doc in enumerate(documents)
        )
        return (
            "You are a relevance-scoring engine for a product recommendation system.\n\n"
            f"User context (query):\n{query}\n\n"
            "Candidate items, one per line, prefixed by index:\n"
            f"{numbered_docs}\n\n"
            "Score how relevant each candidate item is to the user context, from 0.0 "
            "(irrelevant) to 1.0 (highly relevant). Return exactly one score per item, "
            "in the same order as given."
        )


_provider: AIProvider = None


def get_ai_provider() -> AIProvider:
    """Return the process-wide AIProvider instance, creating it on first use."""
    global _provider
    if _provider is None:
        _provider = AIProvider()
    return _provider
