"""
Product embedding writer.

Populates `product_vectors`, which is what `resolution.py` searches to ground
LLM category strings against the merchant's real catalog. Without this the
priors are empty and a new shop has nothing to serve on install day.

Extracted from the old `cross_encoder_service`, with two defects fixed:

1. The previous version opened a fresh transaction *per product* to check the
   text hash — 2,000 round trips for a 2,000-SKU install. Hashes are now read
   in one query.
2. `_embed_and_store_batch` called `.tolist()` on values that were already
   lists, raising AttributeError on every invocation. So no embedding was ever
   actually stored.

Idempotent: a product whose text has not changed is skipped, so this is safe to
run on every `products/update` webhook.
"""

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import select, and_, text as sql_text

from app.core.database.models.product_data import ProductData
from app.core.database.models.product_vector import ProductVector
from app.core.database.session import get_transaction_context

logger = logging.getLogger(__name__)

# Must match resolution.EMBEDDING_MODEL. If these diverge, category vectors land
# in a different space from product vectors and every similarity is meaningless.
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
VECTOR_DIM = 384
ENCODE_BATCH_SIZE = 64


def build_product_text(product: ProductData) -> str:
    """The text that represents a product to the embedder.

    Title, type and tags carry the merchandising signal. Description is capped
    because past the first couple of sentences it is shipping tables and size
    charts, which push the vector toward whatever boilerplate the theme uses.
    """
    parts = [
        product.title or "",
        product.product_type or "",
        (product.description or "")[:200],
    ]
    if product.tags and isinstance(product.tags, list):
        parts.extend(str(t) for t in product.tags[:12])
    return " | ".join(p for p in parts if p)


def text_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


class ProductEmbedder:
    """Computes and stores product vectors."""

    def __init__(self, model_name: str = EMBEDDING_MODEL):
        self.model_name = model_name
        self._model = None

    def _encode(self, texts: Sequence[str]) -> List[List[float]]:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
        # `encode` returns an ndarray; tolist() once, here, gives plain lists
        # all the way down.
        return self._model.encode(list(texts), batch_size=ENCODE_BATCH_SIZE).tolist()

    async def embed_shop(
        self, shop_id: str, product_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Embed a shop's active products, skipping unchanged text."""
        start = datetime.now()
        try:
            products = await self._load_products(shop_id, product_ids)
            if not products:
                logger.info(f"No products to embed for shop {shop_id}")
                return {"success": True, "processed": 0, "embedded": 0, "skipped": 0}

            existing = await self._existing_hashes(shop_id)

            pending: List[Tuple[str, str, str]] = []  # (product_id, text, hash)
            skipped = 0
            for product in products:
                body = build_product_text(product)
                if not body:
                    skipped += 1
                    continue
                digest = text_hash(body)
                if existing.get(product.product_id) == digest:
                    skipped += 1
                    continue
                pending.append((product.product_id, body, digest))

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
        """All stored hashes for the shop, in one query."""
        async with get_transaction_context() as session:
            rows = (
                await session.execute(
                    select(ProductVector.product_id, ProductVector.text_hash).where(
                        ProductVector.shop_id == shop_id
                    )
                )
            ).all()
        return {r.product_id: r.text_hash for r in rows}

    async def _store_chunk(
        self, shop_id: str, chunk: List[Tuple[str, str, str]]
    ) -> int:
        if not chunk:
            return 0

        vectors = self._encode([body for _, body, _ in chunk])

        async with get_transaction_context() as session:
            for (product_id, _, digest), vector in zip(chunk, vectors):
                existing = (
                    await session.execute(
                        select(ProductVector).where(
                            and_(
                                ProductVector.shop_id == shop_id,
                                ProductVector.product_id == product_id,
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
                            product_id=product_id,
                            vector=vector,
                            text_hash=digest,
                            model_version=self.model_name,
                        )
                    )
        return len(chunk)


def _chunk(items: List[Any], size: int) -> Iterable[List[Any]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]
