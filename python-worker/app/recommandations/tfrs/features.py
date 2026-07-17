"""
Feature transformers for TFRS model.

Transforms ProductData, OrderData, CustomerData, and UserInteraction
into TFRS-compatible feature tensors. Uses Vertex AI embeddings
for product text and image understanding.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

import numpy as np
import pandas as pd

from .embeddings import VertexAIEmbeddings
from .config import TfrsConfig

logger = logging.getLogger(__name__)


class FeatureTransformer:
    """Transforms database models into TFRS feature tensors."""

    def __init__(self, config: Optional[TfrsConfig] = None):
        self.config = config or TfrsConfig()
        self.embedding_service = VertexAIEmbeddings()

        # Vocabularies (built during training, used during serving)
        self.product_id_vocab: Dict[str, int] = {}
        self.user_id_vocab: Dict[str, int] = {}
        self.product_type_vocab: Dict[str, int] = {}
        self.vendor_vocab: Dict[str, int] = {}
        self.category_vocab: Dict[str, int] = {}
        self.tag_vocab: Dict[str, int] = {}
        self.collection_vocab: Dict[str, int] = {}
        self.location_vocab: Dict[str, int] = {}

        # Pre-computed product embeddings (product_id -> vector)
        self.product_embeddings: Dict[str, List[float]] = {}
        self.product_image_embeddings: Dict[str, List[float]] = {}

    # ------------------------------------------------------------------
    # Product features
    # ------------------------------------------------------------------

    async def build_product_features(
        self, products: List[Dict[str, Any]]
    ) -> pd.DataFrame:
        """Transform ProductData records into a rich feature DataFrame.

        Features:
        - text_embedding: title + description via Vertex AI
        - image_embedding: first product image via Vertex AI (if available)
        - price_bucket / log_price / is_on_sale
        - product_type_id / vendor_id (categorical)
        - tag_embedding: multi-hot tag signature
        - collection_embedding: multi-hot collection signature
        - total_inventory / is_active / has_images
        """
        if not products:
            return pd.DataFrame()

        df = pd.DataFrame(products)

        # 1. Text embeddings (title + description)
        await self._ensure_product_embeddings(products)
        df["text_embedding"] = df["product_id"].map(self.product_embeddings)

        # 2. Image embeddings (first product image)
        await self._ensure_image_embeddings(products)
        df["image_embedding"] = df["product_id"].map(
            lambda pid: self.product_image_embeddings.get(
                pid, [0.0] * self.config.image_embedding_dim
            )
        )
        df["has_images"] = df.get("images", [[] for _ in range(len(df))]).apply(
            lambda imgs: 1 if imgs and len(imgs) > 0 else 0
        )

        # 3. Price features
        prices = pd.to_numeric(
            df.get("price", pd.Series([0] * len(df))), errors="coerce"
        )
        df["log_price"] = np.log1p(prices.fillna(0))
        df["price_bucket"] = (
            pd.cut(
                prices.fillna(0),
                bins=[0, 10, 25, 50, 100, 200, 500, 1000, 5000, float("inf")],
                labels=False,
                include_lowest=True,
            )
            .fillna(0)
            .astype(int)
        )
        # Compare-at price indicates "on sale"
        compare_prices = pd.to_numeric(
            df.get("compare_at_price", pd.Series([0] * len(df))), errors="coerce"
        )
        df["is_on_sale"] = (compare_prices.fillna(0) > prices.fillna(0)).astype(int)

        # 4. Categorical features
        df["product_type_id"] = (
            df.get("product_type", "")
            .map(lambda x: self.product_type_vocab.get(x or "", 0))
            .fillna(0)
            .astype(int)
        )
        df["vendor_id"] = (
            df.get("vendor", "")
            .map(lambda x: self.vendor_vocab.get(x or "", 0))
            .fillna(0)
            .astype(int)
        )

        # 5. Tags → multi-hot embedding
        df["tag_ids"] = df.get("tags", [[] for _ in range(len(df))]).apply(
            self._tags_to_ids
        )

        # 6. Collections → multi-hot embedding
        df["collection_ids"] = df.get(
            "collections", [[] for _ in range(len(df))]
        ).apply(self._collections_to_ids)

        # 7. Numeric flags
        df["total_inventory"] = (
            pd.to_numeric(df.get("total_inventory", 0), errors="coerce")
            .fillna(0)
            .astype(float)
        )
        df["inventory_score"] = np.log1p(df["total_inventory"].clip(0))
        df["is_active"] = df.get("is_active", True).astype(int)

        return df

    def _tags_to_ids(self, tags: Any) -> List[int]:
        """Convert a list of tag strings to vocabulary IDs."""
        if not tags or not isinstance(tags, list):
            return [0]
        ids = []
        for tag in tags:
            tag_str = str(tag).strip().lower()
            idx = self.tag_vocab.get(tag_str, 0)
            if idx > 0:
                ids.append(idx)
        return ids if ids else [0]

    def _collections_to_ids(self, collections: Any) -> List[int]:
        """Convert a list of collections to vocabulary IDs."""
        if not collections:
            return [0]
        ids = []
        for c in collections:
            if isinstance(c, dict):
                title = c.get("title", "")
            elif isinstance(c, str):
                title = c
            else:
                continue
            idx = self.collection_vocab.get(title, 0)
            if idx > 0:
                ids.append(idx)
        return ids if ids else [0]

    async def _ensure_product_embeddings(self, products: List[Dict[str, Any]]) -> None:
        """Generate text embeddings for products that don't have them yet."""
        missing = [
            p for p in products if p["product_id"] not in self.product_embeddings
        ]
        if not missing:
            return

        logger.info(f"Generating text embeddings for {len(missing)} products...")
        embeddings = await self.embedding_service.embed_products_batch(missing)
        self.product_embeddings.update(embeddings)

        for product in missing:
            pid = product["product_id"]
            if pid not in self.product_embeddings:
                self.product_embeddings[pid] = [0.0] * self.config.text_embedding_dim

    async def _ensure_image_embeddings(self, products: List[Dict[str, Any]]) -> None:
        """Generate image embeddings for products with images."""
        missing = []
        for p in products:
            pid = p["product_id"]
            if pid in self.product_image_embeddings:
                continue
            images = p.get("images") or []
            if images and len(images) > 0:
                img_url = (
                    images[0].get("src") if isinstance(images[0], dict) else images[0]
                )
                if img_url:
                    missing.append((pid, img_url))

        if not missing:
            return

        logger.info(f"Generating image embeddings for {len(missing)} products...")
        try:
            texts = [f"[IMAGE] {url}" for _, url in missing]
            embeddings = await self.embedding_service.embed_texts(texts)
            for (pid, _), emb in zip(missing, embeddings):
                if emb:
                    self.product_image_embeddings[pid] = emb
        except Exception as e:
            logger.warning(f"Image embedding failed (non-fatal): {e}")

    # ------------------------------------------------------------------
    # User features
    # ------------------------------------------------------------------

    async def build_user_features(self, users: List[Dict[str, Any]]) -> pd.DataFrame:
        """Transform user data into a feature DataFrame.

        Features:
        - total_purchases, lifetime_value, avg_order_value
        - purchase_frequency_score, recency_score, retention_score
        - customer_tier: 0=new, 1=regular, 2=VIP (based on total_spent)
        - location_id: country/state from default_address
        """
        if not users:
            return pd.DataFrame()

        df = pd.DataFrame(users)

        # Numeric features
        for col in [
            "total_purchases",
            "lifetime_value",
            "avg_order_value",
            "purchase_frequency_score",
            "recency_score",
        ]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        if "retention_score" in df.columns:
            df["retention_score"] = pd.to_numeric(
                df["retention_score"], errors="coerce"
            ).fillna(0.5)

        # Customer tier (from total_spent)
        if "total_spent" in df.columns:
            spent = pd.to_numeric(df["total_spent"], errors="coerce").fillna(0)
            df["customer_tier"] = pd.cut(
                spent,
                bins=[-1, 0, 100, 500, float("inf")],
                labels=[0, 1, 2, 3],
            ).astype(int)
        else:
            df["customer_tier"] = 0

        # Location (from default_address -> country)
        if "default_address" in df.columns:
            df["location_id"] = df["default_address"].apply(
                lambda addr: self.location_vocab.get((addr or {}).get("country", ""), 0)
            )
        else:
            df["location_id"] = 0

        return df

    # ------------------------------------------------------------------
    # Context features (time, day, device)
    # ------------------------------------------------------------------

    def build_context_features(
        self, context: str = "checkout", user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build context features from request metadata.

        Returns: dict with time_of_day, day_of_week, context_id
        """
        now = datetime.utcnow()
        hour = now.hour

        # Time of day: 0=morning, 1=afternoon, 2=evening, 3=night
        if 6 <= hour < 12:
            time_of_day = 0  # morning
        elif 12 <= hour < 17:
            time_of_day = 1  # afternoon
        elif 17 <= hour < 22:
            time_of_day = 2  # evening
        else:
            time_of_day = 3  # night

        # Day of week: 0=Monday ... 6=Sunday
        day_of_week = now.weekday()

        # Weekend flag
        is_weekend = 1 if day_of_week >= 5 else 0

        # Context mapping
        context_map = {
            "checkout": 0,
            "post_purchase": 1,
            "cart": 2,
            "product_page": 3,
            "homepage": 4,
            "profile": 5,
            "collection_page": 6,
            "order_status": 7,
            "order_history": 8,
        }
        context_id = context_map.get(context, 0)

        return {
            "time_of_day": time_of_day,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "context_id": context_id,
        }

    # ------------------------------------------------------------------
    # Training data (interactions + attributions)
    # ------------------------------------------------------------------

    async def build_training_dataset(
        self,
        interactions: List[Dict[str, Any]],
        attributions: List[Dict[str, Any]],
        products_df: pd.DataFrame,
        users_df: pd.DataFrame,
        co_purchase_examples: Optional[List[Dict[str, Any]]] = None,
    ) -> pd.DataFrame:
        """Build training dataset from interactions, attributions, and co-purchases.

        Args:
            interactions: User interaction events
            attributions: Purchase attribution records
            products_df: Product feature DataFrame
            users_df: User feature DataFrame
            co_purchase_examples: Optional co-purchase pairs from order line items.
                Each entry: {"user_id": str, "product_id": str, "label": 0.4}
        """
        rows = []

        # Positive examples from purchase attributions
        for attr in attributions:
            user_id = attr.get("customer_id")
            revenue = attr.get("total_revenue", 0)
            contributing = attr.get("contributing_extensions", [])
            weight = float(revenue) / max(len(contributing), 1)

            for product in attr.get("purchase_products", []):
                rows.append(
                    {
                        "user_id": user_id,
                        "product_id": product.get("id"),
                        "label": weight,
                        "interaction_type": "purchase",
                    }
                )

        # Positive examples from interactions
        for ix in interactions:
            user_id = ix.get("customer_id") or ix.get("customerId")
            product_id = ix.get("product_id") or ix.get("productId")
            ix_type = ix.get("interaction_type") or ix.get("interactionType", "")

            if not user_id or not product_id:
                continue

            weight = {
                "product_added_to_cart": 0.6,
                "checkout_started": 0.7,
                "checkout_completed": 0.9,
                "recommendation_clicked": 0.5,
                "product_viewed": 0.3,
            }.get(ix_type, 0.1)

            rows.append(
                {
                    "user_id": user_id,
                    "product_id": product_id,
                    "label": weight,
                    "interaction_type": ix_type,
                }
            )

        # Co-purchase examples: when two products appear in the same order,
        # that's a positive signal that they're related. This teaches the
        # model "people who bought X also bought Y" — the FBT pattern.
        if co_purchase_examples:
            rows.extend(co_purchase_examples)

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)

        # Merge with product features
        if "product_id" in products_df.columns:
            merge_cols = [
                "product_id",
                "text_embedding",
                "image_embedding",
                "price_bucket",
                "product_type_id",
                "vendor_id",
                "log_price",
                "is_on_sale",
                "tag_ids",
                "collection_ids",
                "inventory_score",
                "has_images",
            ]
            available = [c for c in merge_cols if c in products_df.columns]
            df = df.merge(products_df[available], on="product_id", how="left")

        # Merge with user features
        if "customer_id" in users_df.columns and "user_id" in df.columns:
            df = df.merge(
                users_df,
                left_on="user_id",
                right_on="customer_id",
                how="left",
            )

        return df

    # ------------------------------------------------------------------
    # Vocabulary building
    # ------------------------------------------------------------------

    def build_vocabularies(
        self,
        products: List[Dict[str, Any]],
        users: List[Dict[str, Any]],
    ) -> None:
        """Build ID vocabularies from products and users."""
        self.product_id_vocab = {p["product_id"]: i + 1 for i, p in enumerate(products)}
        self.user_id_vocab = {
            u.get("customer_id", u.get("user_id", f"user_{i}")): i + 1
            for i, u in enumerate(users)
        }

        # Product types
        types = set()
        for p in products:
            if p.get("product_type"):
                types.add(p["product_type"])
        self.product_type_vocab = {t: i + 1 for i, t in enumerate(sorted(types))}

        # Vendors
        vendors = set()
        for p in products:
            if p.get("vendor"):
                vendors.add(p["vendor"])
        self.vendor_vocab = {v: i + 1 for i, v in enumerate(sorted(vendors))}

        # Tags
        tags = set()
        for p in products:
            for t in p.get("tags") or []:
                if isinstance(t, str):
                    tags.add(t.strip().lower())
        self.tag_vocab = {t: i + 1 for i, t in enumerate(sorted(tags))}

        # Collections
        collections = set()
        for p in products:
            for c in p.get("collections") or []:
                title = c.get("title") if isinstance(c, dict) else str(c)
                if title:
                    collections.add(title)
        self.collection_vocab = {c: i + 1 for i, c in enumerate(sorted(collections))}

        # Locations (countries from CustomerData)
        locations = set()
        for u in users:
            addr = u.get("default_address") or {}
            country = addr.get("country", "")
            if country:
                locations.add(country)
        self.location_vocab = {l: i + 1 for i, l in enumerate(sorted(locations))}

        logger.info(
            f"Vocabularies built: {len(self.product_id_vocab)} products, "
            f"{len(self.user_id_vocab)} users, "
            f"{len(self.product_type_vocab)} types, "
            f"{len(self.vendor_vocab)} vendors, "
            f"{len(self.tag_vocab)} tags, "
            f"{len(self.collection_vocab)} collections"
        )
