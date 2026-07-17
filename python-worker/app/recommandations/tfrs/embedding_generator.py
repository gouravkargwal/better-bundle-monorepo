"""
Cold-start embedding generator.

Generates Vertex AI embeddings for all products in a shop.
Called when a shop first installs the app, and periodically for new products.

This is what makes TFRS work from DAY 1 — no purchase data needed.
Without this, a new shop with 50 products and 0 orders would get random recommendations.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

from app.core.database.session import get_transaction_context
from app.core.database.models import ProductData
from app.core.logging import get_logger
from app.recommandations.tfrs.embeddings import VertexAIEmbeddings
from sqlalchemy import select

logger = get_logger(__name__)


class EmbeddingGenerator:
    """Generates Vertex AI embeddings for all active products in a shop."""

    def __init__(self):
        self.embeddings_service = VertexAIEmbeddings()

    async def generate_for_shop(
        self, shop_id: str, batch_size: int = 100
    ) -> Dict[str, Any]:
        """Generate embeddings for all active products in a shop.

        Args:
            shop_id: Shop to generate embeddings for.
            batch_size: Products per batch (Vertex AI rate limit).

        Returns:
            Dict with count of embeddings stored.
        """
        products = await self._load_products(shop_id)
        if not products:
            logger.info(f"No active products for shop {shop_id}, skipping")
            return {"status": "skipped", "reason": "no_products", "count": 0}

        logger.info(
            f"Generating embeddings for {len(products)} products in shop {shop_id}"
        )

        # Build product texts for Vertex AI
        texts = []
        for p in products:
            tags = p.get("tags") or []
            if isinstance(tags, list):
                tags_str = ", ".join(tags)
            else:
                tags_str = str(tags)
            text = (
                f"{p['title']}. {(p.get('description') or '')[:500]}. "
                f"Type: {p.get('product_type', '')}. "
                f"Brand: {p.get('vendor', '')}. "
                f"Tags: {tags_str}"
            )
            texts.append(text)

        # Generate embeddings via Vertex AI
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_embeddings = await self.embeddings_service.embed_texts(batch_texts)
            all_embeddings.extend(batch_embeddings)
            logger.info(
                f"  Embedded batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}"
            )

        # Store embeddings in product_embeddings table
        stored = 0
        async with get_transaction_context() as session:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            from app.core.database.models import ProductFeatures

            for product, embedding in zip(products, all_embeddings):
                if not embedding:
                    continue

                stmt = pg_insert(ProductFeatures).values(
                    shop_id=shop_id,
                    product_id=product["product_id"],
                    embedding=embedding,
                )
                stmt = stmt.on_conflict_do_update(
                    constraint="ix_product_features_shop_id_product_id",
                    set_={"embedding": embedding},
                )
                await session.execute(stmt)
                stored += 1

            await session.commit()

        logger.info(f"✅ Stored {stored}/{len(products)} embeddings for shop {shop_id}")
        return {"status": "success", "count": stored, "total": len(products)}

    async def _load_products(self, shop_id: str) -> List[Dict[str, Any]]:
        """Load active products for a shop."""
        async with get_transaction_context() as session:
            result = await session.execute(
                select(ProductData).where(
                    ProductData.shop_id == shop_id,
                    ProductData.is_active == True,
                )
            )
            products = result.scalars().all()
            return [
                {
                    "product_id": p.product_id,
                    "title": p.title,
                    "description": p.description or "",
                    "product_type": p.product_type or "",
                    "vendor": p.vendor or "",
                    "tags": p.tags or [],
                }
                for p in products
            ]
