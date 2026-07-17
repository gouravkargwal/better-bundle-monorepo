"""
Gemini embeddings service for product understanding.

Generates semantic embeddings from product text (title, description, tags)
using the Gemini embedding model to enable content-based recommendation
for cold-start products.

Authenticates via API key (Google AI Studio today; Vertex AI Express Mode
supports the same API-key flow, so switching backends later only requires
setting GOOGLE_GENAI_USE_VERTEXAI=true alongside the existing key).
"""

import logging
import os
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class VertexAIEmbeddings:
    """Generate embeddings via the Gemini API using an API key."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        use_vertexai: Optional[bool] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = (
            api_key or os.getenv("GOOGLE_AI_API_KEY") or os.getenv("VERTEX_AI_API_KEY")
        )
        if use_vertexai is None:
            use_vertexai = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "false").lower() in (
                "1",
                "true",
                "yes",
            )
        self.use_vertexai = use_vertexai
        # Prefer env var, then passed arg, then default
        self.model_name = (
            model_name
            or os.getenv("VERTEX_AI_EMBEDDING_MODEL")
            or "models/gemini-embedding-2"
        )
        self._client = None

    async def _ensure_client(self):
        """Lazy-init the Gemini API client."""
        if self._client is not None:
            return self._client

        if not self.api_key:
            raise RuntimeError(
                "Missing API key: set GOOGLE_AI_API_KEY (Google AI Studio) or "
                "VERTEX_AI_API_KEY (Vertex AI Express Mode)."
            )

        try:
            from google import genai

            self._client = genai.Client(
                api_key=self.api_key, vertexai=self.use_vertexai
            )
            backend = "Vertex AI" if self.use_vertexai else "Google AI Studio"
            logger.info(
                f"✅ Gemini embeddings initialized ({backend}): {self.model_name}"
            )
            return self._client

        except Exception as e:
            logger.error(f"Failed to init Gemini embeddings client: {e}")
            raise

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        client = await self._ensure_client()
        result = client.models.embed_content(model=self.model_name, contents=texts)
        return [embedding.values for embedding in result.embeddings]

    async def embed_product(self, product: Dict[str, Any]) -> List[float]:
        """Generate embedding for a single product."""
        text = self._product_to_text(product)
        embeddings = await self.embed_texts([text])
        return embeddings[0] if embeddings else []

    async def embed_products_batch(
        self, products: List[Dict[str, Any]], batch_size: int = 100
    ) -> Dict[str, List[float]]:
        """Generate embeddings for many products."""
        results = {}
        for i in range(0, len(products), batch_size):
            batch = products[i : i + batch_size]
            texts = [self._product_to_text(p) for p in batch]
            embeddings = await self.embed_texts(texts)
            for product, emb in zip(batch, embeddings):
                if emb:
                    results[product["product_id"]] = emb
            logger.info(
                f"  Embedded batch {i//batch_size + 1}/{(len(products)-1)//batch_size + 1}"
            )
        return results

    @staticmethod
    def _product_to_text(product: Dict[str, Any]) -> str:
        """Convert product data to a text string for embedding."""
        parts = [
            product.get("title", ""),
            (product.get("description") or "")[:500],
        ]
        if product.get("product_type"):
            parts.append(f"Type: {product['product_type']}")
        if product.get("vendor"):
            parts.append(f"Brand: {product['vendor']}")
        if product.get("tags"):
            tags = product["tags"]
            if isinstance(tags, list):
                parts.append(f"Tags: {', '.join(tags)}")
            elif isinstance(tags, str):
                parts.append(f"Tags: {tags}")
        return ". ".join(parts)


def create_embedding_service() -> VertexAIEmbeddings:
    """Create the Gemini embedding service, authenticated via API key."""
    return VertexAIEmbeddings()
