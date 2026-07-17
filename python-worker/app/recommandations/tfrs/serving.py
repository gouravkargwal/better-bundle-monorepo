"""
TFRS serving wrapper.

Loads trained TFRS models and serves recommendations.
Maintains an LRU cache of loaded models per shop.
"""

import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime

import tensorflow as tf
import numpy as np

from app.core.logging import get_logger
from .config import TfrsConfig
from .features import FeatureTransformer

logger = get_logger(__name__)


class TfrsServing:
    """Serves recommendations from trained TFRS models."""

    def __init__(self, config: Optional[TfrsConfig] = None):
        self.config = config or TfrsConfig()
        self.features = FeatureTransformer(self.config)
        self._models: Dict[str, tf.saved_model] = {}  # shop_id -> model
        self._model_paths: Dict[str, str] = {}  # shop_id -> path
        self._product_cache: Dict[str, List[Dict[str, Any]]] = {}  # shop_id -> products

    async def recommend(
        self,
        shop_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        context: str = "checkout",
        limit: int = 6,
        exclude_product_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get top-N recommendations for a user/session.

        Args:
            shop_id: Shop identifier.
            user_id: Customer identifier (optional, for personalized).
            session_id: Session identifier (optional, for session-based).
            context: Recommendation context (checkout, post_purchase, etc.).
            limit: Number of recommendations to return.
            exclude_product_ids: Products to exclude (already in cart/purchased).

        Returns:
            Dict with recommendations and metadata.
        """
        # Load model for this shop
        model = await self._load_model(shop_id)
        if model is None:
            logger.warning(f"No TFRS model for shop {shop_id}, using fallback")
            return {"success": False, "items": [], "source": "tfrs_no_model"}

        # Load product catalog
        products = await self._get_product_catalog(shop_id)
        if not products:
            return {"success": False, "items": [], "source": "tfrs_no_products"}

        # Build query features
        if user_id:
            features = await self._build_query_features(shop_id, user_id, context)
        elif session_id:
            features = await self._build_session_features(shop_id, session_id, context)
        else:
            # Popular/contextual (no user or session)
            return await self._popular_fallback(products, context, limit)

        if not features:
            return {"success": False, "items": [], "source": "tfrs_no_features"}

        try:
            # Get scores for all products
            all_scores = []
            batch_size = 64
            for i in range(0, len(products), batch_size):
                batch = products[i : i + batch_size]
                batch_features = self._batch_features(features, batch)
                scores = model(batch_features)
                all_scores.extend(scores["score"].numpy().tolist())

            # Sort by score descending
            scored = list(zip(all_scores, products))
            scored.sort(key=lambda x: x[0], reverse=True)

            # Apply exclusions
            if exclude_product_ids:
                exclude_set = set(exclude_product_ids)
                scored = [
                    (s, p) for s, p in scored if p["product_id"] not in exclude_set
                ]

            # Return top-N
            top = scored[:limit]
            items = [
                {
                    "id": p["product_id"],
                    "title": p.get("title", ""),
                    "score": float(s),
                    "price": p.get("price", 0),
                }
                for s, p in top
            ]

            logger.info(
                f"TFRS: {len(items)} recommendations for shop {shop_id} "
                f"(context={context}, user={'yes' if user_id else 'no'})"
            )

            return {
                "success": True,
                "items": items,
                "source": "tfrs",
                "count": len(items),
            }

        except Exception as e:
            logger.error(f"TFRS inference error for shop {shop_id}: {e}")
            return {"success": False, "items": [], "source": "tfrs_error"}

    async def _load_model(self, shop_id: str) -> Optional[tf.saved_model]:
        """Load a TFRS model for a shop (cached)."""
        if shop_id in self._models:
            return self._models[shop_id]

        model_path = os.path.join(
            os.getenv("TFRS_MODEL_PATH", self.config.model_base_path),
            shop_id,
            "latest",
        )

        if not os.path.exists(model_path):
            logger.warning(f"TFRS model not found for shop {shop_id} at {model_path}")
            return None

        try:
            model = tf.saved_model.load(model_path)
            self._models[shop_id] = model
            self._model_paths[shop_id] = model_path
            logger.info(f"✅ Loaded TFRS model for shop {shop_id}")
            return model
        except Exception as e:
            logger.error(f"Failed to load TFRS model for shop {shop_id}: {e}")
            return None

    async def _get_product_catalog(self, shop_id: str) -> List[Dict[str, Any]]:
        """Get product catalog for a shop (cached in memory)."""
        if shop_id in self._product_cache:
            return self._product_cache[shop_id]

        from app.core.database.models import ProductData
        from app.core.database.session import get_transaction_context
        from sqlalchemy import select

        async with get_transaction_context() as session:
            result = await session.execute(
                select(ProductData).where(
                    ProductData.shop_id == shop_id,
                    ProductData.is_active == True,
                )
            )
            products = result.scalars().all()
            catalog = [
                {
                    "product_id": p.product_id,
                    "title": p.title,
                    "price": p.price or 0,
                    "product_type": p.product_type or "",
                    "vendor": p.vendor or "",
                    "description": p.description or "",
                    "tags": p.tags or [],
                    "collections": p.collections or [],
                    "total_inventory": p.total_inventory or 0,
                    "image": (p.images or [{}])[0].get("src") if p.images else None,
                    "url": f"/products/{p.handle}" if p.handle else None,
                }
                for p in products
            ]
            self._product_cache[shop_id] = catalog
            return catalog

    async def _build_query_features(
        self,
        shop_id: str,
        user_id: str,
        context: str,
    ) -> Optional[Dict[str, Any]]:
        """Build query features for a known user."""
        from app.core.database.models import CustomerBehaviorFeatures
        from app.core.database.session import get_transaction_context
        from sqlalchemy import select

        async with get_transaction_context() as session:
            result = await session.execute(
                select(CustomerBehaviorFeatures).where(
                    CustomerBehaviorFeatures.shop_id == shop_id,
                    CustomerBehaviorFeatures.customer_id == user_id,
                )
            )
            user = result.scalar_one_or_none()

            if user is None:
                # Try UserFeatures
                from app.core.database.models import UserFeatures

                result = await session.execute(
                    select(UserFeatures).where(
                        UserFeatures.shop_id == shop_id,
                        UserFeatures.customer_id == user_id,
                    )
                )
                user = result.scalar_one_or_none()

            if user is None:
                return None

            return {
                "user_id": user_id,
                "total_purchases": float(getattr(user, "total_purchases", 0)),
                "lifetime_value": float(getattr(user, "lifetime_value", 0)),
                "avg_order_value": float(getattr(user, "avg_order_value", 0)),
                "purchase_frequency_score": float(
                    getattr(user, "purchase_frequency_score", 0)
                ),
                "recency_score": float(getattr(user, "recency_score", 0)),
                "retention_score": 1.0 - float(getattr(user, "churn_risk_score", 0.5)),
                "context": context,
            }

    async def _build_session_features(
        self,
        shop_id: str,
        session_id: str,
        context: str,
    ) -> Optional[Dict[str, Any]]:
        """Build query features from a session (anonymous user)."""
        from app.core.database.models import UserSession
        from app.core.database.session import get_transaction_context
        from sqlalchemy import select

        async with get_transaction_context() as session:
            result = await session.execute(
                select(UserSession).where(UserSession.id == session_id)
            )
            user_session = result.scalar_one_or_none()

            if user_session and user_session.customer_id:
                return await self._build_query_features(
                    shop_id, user_session.customer_id, context
                )

        # No user info — return context-only features
        return {"context": context, "user_id": "anonymous"}

    def _batch_features(
        self,
        query_features: Dict[str, Any],
        products: List[Dict[str, Any]],
    ) -> Dict[str, tf.Tensor]:
        """Combine query features with each product for batch inference."""
        batch = {}
        n = len(products)

        # Replicate query features for each product
        for key, val in query_features.items():
            if isinstance(val, (int, float)):
                batch[key] = tf.constant([val] * n, dtype=tf.float32)
            elif isinstance(val, str):
                batch[key] = tf.constant([val] * n, dtype=tf.string)
            elif isinstance(val, list):
                batch[key] = tf.constant([val] * n, dtype=tf.float32)

        # Add product features
        for key in ["product_id", "price", "product_type", "vendor"]:
            vals = [p.get(key, "") for p in products]
            if isinstance(vals[0], str):
                batch[key] = tf.constant(vals, dtype=tf.string)
            else:
                batch[key] = tf.constant(vals, dtype=tf.float32)

        # Add text embeddings if available
        for p in products:
            if "embedding" not in p:
                p["embedding"] = [0.0] * self.config.text_embedding_dim

        batch["embedding"] = tf.constant(
            [
                p.get("embedding", [0.0] * self.config.text_embedding_dim)
                for p in products
            ],
            dtype=tf.float32,
        )

        return batch

    async def _popular_fallback(
        self,
        products: List[Dict[str, Any]],
        context: str,
        limit: int,
    ) -> Dict[str, Any]:
        """Fallback: return popular products when no user/session data."""
        # Sort by price * inventory as a simple popularity heuristic
        sorted_products = sorted(
            products,
            key=lambda p: (p.get("price", 0) or 0) * (p.get("total_inventory", 0) or 1),
            reverse=True,
        )

        items = [
            {
                "id": p["product_id"],
                "title": p.get("title", ""),
                "score": 1.0 - (i / len(sorted_products)),
                "price": p.get("price", 0),
            }
            for i, p in enumerate(sorted_products[:limit])
        ]

        return {
            "success": True,
            "items": items,
            "source": "tfrs_popular_fallback",
            "count": len(items),
        }

    def invalidate_cache(self, shop_id: str) -> None:
        """Clear cached model and products for a shop (call after training)."""
        self._models.pop(shop_id, None)
        self._product_cache.pop(shop_id, None)
        logger.info(f"Cache invalidated for shop {shop_id}")
