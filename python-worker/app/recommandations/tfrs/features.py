"""
Feature transformers for TFRS model.

Transforms ProductData, UserFeatures, and PurchaseAttribution
into TFRS-compatible feature tensors. Uses Vertex AI embeddings
for product text understanding.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

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
        self.product_id_vocab: Dict[str, int] = {}  # product_id -> index
        self.user_id_vocab: Dict[str, int] = {}  # user_id -> index
        self.product_type_vocab: Dict[str, int] = {}
        self.vendor_vocab: Dict[str, int] = {}
        self.category_vocab: Dict[str, int] = {}

        # Pre-computed product embeddings (product_id -> vector)
        self.product_embeddings: Dict[str, List[float]] = {}

    # ------------------------------------------------------------------
    # Product features
    # ------------------------------------------------------------------

    async def build_product_features(
        self, products: List[Dict[str, Any]]
    ) -> pd.DataFrame:
        """Transform ProductData records into a feature DataFrame.

        Args:
            products: List of product dicts from ProductData table.

        Returns:
            DataFrame with columns: product_id, embedding, price_bucket,
            product_type_id, vendor_id, inventory, is_active
        """
        if not products:
            return pd.DataFrame()

        df = pd.DataFrame(products)

        # 1. Generate or load embeddings
        await self._ensure_product_embeddings(products)
        df["embedding"] = df["product_id"].map(self.product_embeddings)

        # 2. Price bucketing (log scale)
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

        # 3. Categorical features
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

        # 4. Numeric features
        df["total_inventory"] = (
            pd.to_numeric(df.get("total_inventory", 0), errors="coerce")
            .fillna(0)
            .astype(float)
        )

        df["is_active"] = df.get("is_active", True).astype(int)

        # 5. Collection membership (multi-hot)
        df["collection_ids"] = df.get("collections", [[] for _ in range(len(df))])

        return df

    async def _ensure_product_embeddings(self, products: List[Dict[str, Any]]) -> None:
        """Generate embeddings for products that don't have them yet."""
        missing = [
            p for p in products if p["product_id"] not in self.product_embeddings
        ]
        if not missing:
            return

        logger.info(f"Generating embeddings for {len(missing)} products...")
        embeddings = await self.embedding_service.embed_products_batch(missing)
        self.product_embeddings.update(embeddings)

        # Fill any products that failed with zero vectors
        for product in missing:
            pid = product["product_id"]
            if pid not in self.product_embeddings:
                self.product_embeddings[pid] = [0.0] * self.config.text_embedding_dim

    # ------------------------------------------------------------------
    # User features
    # ------------------------------------------------------------------

    async def build_user_features(self, users: List[Dict[str, Any]]) -> pd.DataFrame:
        """Transform UserFeatures records into a feature DataFrame.

        Args:
            users: List of user feature dicts from UserFeatures table.

        Returns:
            DataFrame with user features for the query tower.
        """
        if not users:
            return pd.DataFrame()

        df = pd.DataFrame(users)

        # Numeric features (normalized)
        for col in [
            "total_purchases",
            "lifetime_value",
            "avg_order_value",
            "purchase_frequency_score",
            "recency_score",
        ]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # Churn risk (inverted: low risk = good)
        if "churn_risk_score" in df.columns:
            df["retention_score"] = 1.0 - pd.to_numeric(
                df["churn_risk_score"], errors="coerce"
            ).fillna(0.5)

        # Primary category
        df["primary_category_id"] = (
            df.get("primary_category", "")
            .map(lambda x: self.category_vocab.get(x or "", 0))
            .fillna(0)
            .astype(int)
        )

        return df

    # ------------------------------------------------------------------
    # Training data (interactions + attributions)
    # ------------------------------------------------------------------

    async def build_training_dataset(
        self,
        interactions: List[Dict[str, Any]],
        attributions: List[Dict[str, Any]],
        products_df: pd.DataFrame,
        users_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Build training dataset from interactions and attributions.

        Each row is a (user, product, label) triple where label is
        the conversion weight (0 = no conversion, >0 = attributed revenue).

        Args:
            interactions: UserInteraction records.
            attributions: PurchaseAttribution records.
            products_df: Product features from build_product_features().
            users_df: User features from build_user_features().

        Returns:
            DataFrame with columns for TFRS training.
        """
        rows = []

        # Positive examples from purchase attributions
        for attr in attributions:
            user_id = attr.get("customer_id")
            revenue = attr.get("total_revenue", 0)
            contributing = attr.get("contributing_extensions", [])

            # Weight by attribution amount and extension count
            weight = float(revenue) / max(len(contributing), 1)

            # Find products in the order (from attribution metadata)
            for product in attr.get("purchase_products", []):
                rows.append(
                    {
                        "user_id": user_id,
                        "product_id": product.get("id"),
                        "label": weight,
                        "interaction_type": "purchase",
                    }
                )

        # Positive examples from add-to-cart interactions
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

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)

        # Merge with product features
        if "product_id" in products_df.columns:
            df = df.merge(
                products_df[
                    [
                        "product_id",
                        "embedding",
                        "price_bucket",
                        "product_type_id",
                        "vendor_id",
                        "log_price",
                    ]
                ],
                on="product_id",
                how="left",
            )

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
        # Product IDs
        self.product_id_vocab = {
            p["product_id"]: i + 1 for i, p in enumerate(products)  # 0 = OOV
        }

        # User IDs
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

        # Categories (from collections)
        cats = set()
        for p in products:
            for c in p.get("collections") or []:
                if isinstance(c, dict) and c.get("title"):
                    cats.add(c["title"])
        self.category_vocab = {c: i + 1 for i, c in enumerate(sorted(cats))}

        logger.info(
            f"Vocabularies built: {len(self.product_id_vocab)} products, "
            f"{len(self.user_id_vocab)} users, "
            f"{len(self.product_type_vocab)} types, "
            f"{len(self.vendor_vocab)} vendors"
        )
