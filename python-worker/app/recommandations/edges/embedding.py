"""
Product embedding writer.

Populates `product_vectors`, which is what `resolution.py` searches to ground
LLM category strings against the merchant's real catalog. Without this the
priors are empty and a new shop has nothing to serve on install day.

Uses Google Vertex AI multimodal embeddings (1408 dimensions) to jointly embed
product images and context text into the same vector space.

Idempotent: a product whose image and text have not changed is skipped, so this
is safe to run on every `products/update` webhook.
"""

import base64
import hashlib
import logging
import os
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import httpx
from google.cloud import aiplatform_v1
from google.protobuf import json_format
from google.protobuf.struct_pb2 import Value
from sqlalchemy import select, and_

from app.core.database.models.product_data import ProductData
from app.core.database.models.product_vector import ProductVector
from app.core.database.session import get_transaction_context

logger = logging.getLogger(__name__)

# The single source of truth for which model wrote these vectors.
# `resolution.py` imports this rather than declaring its own: if the two ever
# disagreed, category vectors would land in a different space from product
# vectors and every similarity score would be meaningless.
EMBEDDING_MODEL = "multimodalembedding"
VECTOR_DIM = 1408
ENCODE_BATCH_SIZE = 16


def build_product_text(product: ProductData) -> str:
    """The text that represents a product context to the embedder."""
    parts = [
        product.title or "",
        product.product_type or "",
        (product.description or "")[:200],
    ]
    if product.tags and isinstance(product.tags, list):
        parts.extend(str(t) for t in product.tags[:12])
    return " | ".join(p for p in parts if p)


def build_multimodal_hash(product: ProductData) -> str:
    """Hash both the image URL and the text so any change triggers a re-embed."""
    content = (
        f"{product.image_url}|{product.title}|{product.product_type}"
        f"|{product.description}|{product.tags}"
    )
    return hashlib.md5(content.encode()).hexdigest()


def text_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


class ProductEmbedder:
    """Computes and stores multimodal product vectors via Google Vertex AI."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: str = "us-central1",
        model_name: str = EMBEDDING_MODEL,
        client: Optional[Any] = None,
    ):
        self.model_name = model_name
        self.location = location
        if not project_id:
            from app.core.config.settings import settings

            ai = getattr(settings, "ml", settings)
            project_id = getattr(ai, "VERTEX_PROJECT_ID", "") or os.environ.get(
                "VERTEX_PROJECT_ID", ""
            )
            if not project_id:
                try:
                    import google.auth

                    _, default_proj = google.auth.default()
                    project_id = default_proj or ""
                except Exception:
                    pass

            if location == "us-central1":
                self.location = getattr(
                    ai, "VERTEX_LOCATION", "us-central1"
                ) or os.environ.get("VERTEX_LOCATION", "us-central1")
        self.project_id = project_id

        self.endpoint = (
            f"projects/{self.project_id}/locations/{self.location}/publishers/google/models/{self.model_name}"
            if self.project_id
            else ""
        )

        if client is not None:
            self.client = client
        else:
            api_endpoint = f"{self.location}-aiplatform.googleapis.com"
            self.client = aiplatform_v1.PredictionServiceAsyncClient(
                client_options={"api_endpoint": api_endpoint}
            )

    async def _encode_multimodal(
        self, products: Sequence[ProductData]
    ) -> List[List[float]]:
        embeddings = []

        # Async HTTP client to fetch Shopify images
        async with httpx.AsyncClient() as http_client:
            for product in products:
                # 1. Fetch the image bytes from Shopify URL (HTTPS only)
                image_bytes = None
                if product.image_url and product.image_url.startswith("https://"):
                    try:
                        image_response = await http_client.get(
                            product.image_url, timeout=15.0
                        )
                        if image_response.status_code == 200:
                            image_bytes = image_response.content
                    except Exception as e:
                        logger.warning(
                            f"Failed to fetch image for product {product.product_id} "
                            f"from {product.image_url}: {e}"
                        )

                # 2. Build the context text (Title + Type + Description + Tags)
                context_text = build_product_text(product)

                # 3. Call Vertex AI Prediction Service
                instance_dict: Dict[str, Any] = {"text": context_text}
                if image_bytes:
                    instance_dict["image"] = {
                        "bytesBase64Encoded": base64.b64encode(image_bytes).decode(
                            "utf-8"
                        )
                    }

                instance = Value()
                json_format.ParseDict(instance_dict, instance)

                response = await self.client.predict(
                    endpoint=self.endpoint,
                    instances=[instance],
                )
                pred = dict(response.predictions[0])
                if image_bytes and "imageEmbedding" in pred:
                    embeddings.append(list(pred["imageEmbedding"]))
                else:
                    embeddings.append(list(pred.get("textEmbedding", [])))

        return embeddings

    async def embed_shop(
        self, shop_id: str, product_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Embed a shop's active products, skipping unchanged products."""
        start = datetime.now()
        try:
            products = await self._load_products(shop_id, product_ids)
            if not products:
                logger.info(f"No products to embed for shop {shop_id}")
                return {"success": True, "processed": 0, "embedded": 0, "skipped": 0}

            existing = await self._existing_hashes(shop_id)

            pending: List[Tuple[ProductData, str]] = []  # (product, digest)
            skipped = 0
            for product in products:
                digest = build_multimodal_hash(product)
                # Compared against "<model>:<hash>" so a model change re-embeds.
                if existing.get(product.product_id) == f"{self.model_name}:{digest}":
                    skipped += 1
                    continue
                pending.append((product, digest))

            embedded = 0
            for chunk in _chunk(pending, ENCODE_BATCH_SIZE):
                embedded += await self._store_chunk(shop_id, chunk)

            duration = (datetime.now() - start).total_seconds()
            logger.info(
                f"Embeddings for shop {shop_id}: {embedded} embedded, "
                f"{skipped} unchanged, in {duration:.1f}s"
            )
            return {
                "success": True,
                "processed": len(products),
                "embedded": embedded,
                "skipped": skipped,
                "duration_seconds": round(duration, 2),
            }

        except Exception as e:
            logger.error(
                f"Embedding failed for shop {shop_id}: {e}", exc_info=True
            )
            return {"success": False, "error": str(e), "embedded": 0}

    async def _load_products(
        self, shop_id: str, product_ids: Optional[List[str]]
    ) -> List[ProductData]:
        async with get_transaction_context() as session:
            query = select(ProductData).where(
                and_(ProductData.shop_id == shop_id, ProductData.is_active.is_(True))
            )
            if product_ids:
                query = query.where(ProductData.product_id.in_(list(product_ids)))
            return list((await session.execute(query)).scalars().all())

    async def _existing_hashes(self, shop_id: str) -> Dict[str, str]:
        """Stored (text_hash, model_version) per product, in one query.

        The model has to be part of the key. Changing models does not change any
        product's text, so a text-only check would skip every product and leave
        the shop on vectors from the previous model — in a different vector
        space from the category queries being embedded against them. No error,
        just quietly wrong matches.
        """
        async with get_transaction_context() as session:
            rows = (
                await session.execute(
                    select(
                        ProductVector.product_id,
                        ProductVector.text_hash,
                        ProductVector.model_version,
                    ).where(ProductVector.shop_id == shop_id)
                )
            ).all()
        return {r.product_id: f"{r.model_version}:{r.text_hash}" for r in rows}

    async def _store_chunk(
        self, shop_id: str, chunk: List[Tuple[ProductData, str]]
    ) -> int:
        if not chunk:
            return 0

        chunk_products = [prod for prod, _ in chunk]
        vectors = await self._encode_multimodal(chunk_products)

        async with get_transaction_context() as session:
            for (product, digest), vector in zip(chunk, vectors):
                existing = (
                    await session.execute(
                        select(ProductVector).where(
                            and_(
                                ProductVector.shop_id == shop_id,
                                ProductVector.product_id == product.product_id,
                            )
                        )
                    )
                ).scalar_one_or_none()

                if existing:
                    existing.vector = vector
                    existing.text_hash = digest
                    existing.model_version = self.model_name
                else:
                    session.add(
                        ProductVector(
                            shop_id=shop_id,
                            product_id=product.product_id,
                            vector=vector,
                            text_hash=digest,
                            model_version=self.model_name,
                        )
                    )
        return len(chunk)


def _chunk(items: List[Any], size: int) -> Iterable[List[Any]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]
