"""
Vertex AI embeddings service for product understanding.

Generates semantic embeddings from product text (title, description, tags)
using Vertex AI text-embedding-004 to enable content-based recommendation
for cold-start products.
"""

import logging
import os
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class VertexAIEmbeddings:
    """Generate embeddings via Vertex AI text-embedding-004."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        location: str = "us-central1",
        model_name: str = "text-embedding-004",
    ):
        self.api_key = api_key or os.getenv("VERTEX_AI_API_KEY")
        self.project_id = project_id or os.getenv("VERTEX_AI_PROJECT_ID")
        self.location = location
        self.model_name = model_name
        self._client = None

    async def _ensure_client(self):
        """Lazy-init the Vertex AI client."""
        if self._client is not None:
            return self._client

        try:
            from vertexai.language_models import TextEmbeddingModel
            import vertexai

            if self.api_key:
                os.environ["VERTEX_AI_API_KEY"] = self.api_key

            if self.project_id:
                vertexai.init(project=self.project_id, location=self.location)
            else:
                vertexai.init(location=self.location)

            self._client = TextEmbeddingModel.from_pretrained(self.model_name)
            logger.info(f"✅ Vertex AI embeddings initialized: {self.model_name}")
            return self._client

        except Exception as e:
            logger.error(f"Failed to init Vertex AI embeddings: {e}")
            raise

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        client = await self._ensure_client()
        embeddings = client.get_embeddings(texts)
        return [emb.values for emb in embeddings]

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
    """Create the Vertex AI embedding service."""
    api_key = os.getenv("VERTEX_AI_API_KEY")
    project_id = os.getenv("VERTEX_AI_PROJECT_ID")
    return VertexAIEmbeddings(api_key=api_key, project_id=project_id)
