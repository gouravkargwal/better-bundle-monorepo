"""
TFRS training pipeline.

Trains the two-tower model for a specific shop using:
- Product features (price, type, vendor, Vertex AI embeddings)
- User features (LTV, frequency, churn risk)
- Purchase attributions and interactions (training labels)

Saves trained model to disk for serving.
"""

import logging
import os
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

import tensorflow as tf
import numpy as np

from app.core.database.session import get_transaction_context
from app.core.database.models import (
    ProductData,
    UserFeatures,
    CustomerBehaviorFeatures,
    UserInteraction,
    PurchaseAttribution,
)
from app.core.logging import get_logger
from sqlalchemy import select

from .config import TfrsConfig
from .features import FeatureTransformer
from .model import BetterBundleModel, QueryTower, CandidateTower

logger = get_logger(__name__)


class TfrsTrainer:
    """Trains TFRS models per shop."""

    def __init__(self, config: Optional[TfrsConfig] = None):
        self.config = config or TfrsConfig()
        self.features = FeatureTransformer(self.config)

    async def train_for_shop(self, shop_id: str) -> Dict[str, Any]:
        """Full training pipeline for a single shop."""
        logger.info(f"🚀 Starting TFRS training for shop {shop_id}")

        start_time = time.time()

        # 1. Load data
        products = await self._load_products(shop_id)
        users = await self._load_users(shop_id)
        interactions = await self._load_interactions(shop_id)
        attributions = await self._load_attributions(shop_id)

        if len(products) < self.config.min_products_for_training:
            logger.warning(
                f"Shop {shop_id}: only {len(products)} products, "
                f"minimum {self.config.min_products_for_training} required. Skipping."
            )
            return {"status": "skipped", "reason": "insufficient_products"}

        logger.info(
            f"Loaded: {len(products)} products, "
            f"{len(users)} users, "
            f"{len(interactions)} interactions, "
            f"{len(attributions)} attributions"
        )

        # 2. Build vocabularies
        self.features.build_vocabularies(products, users)

        # 3. Build feature DataFrames
        products_df = await self.features.build_product_features(products)
        users_df = await self.features.build_user_features(users)
        train_df = await self.features.build_training_dataset(
            interactions, attributions, products_df, users_df
        )

        if len(train_df) < self.config.min_interactions_for_training:
            logger.warning(
                f"Shop {shop_id}: only {len(train_df)} training examples, "
                f"minimum {self.config.min_interactions_for_training} required. Skipping."
            )
            return {"status": "skipped", "reason": "insufficient_interactions"}

        logger.info(f"Training dataset: {len(train_df)} examples")

        # 4. Convert to TF Dataset
        train_ds, eval_ds = self._df_to_dataset(train_df)

        # 5. Build and train model
        product_ds = self._products_to_dataset(products_df)
        query_tower = QueryTower(self.config.user_embedding_dim)
        candidate_tower = CandidateTower(
            self.config.item_embedding_dim,
            self.config.text_embedding_dim,
        )
        model = BetterBundleModel(query_tower, candidate_tower, product_ds)

        model.compile(
            optimizer=tf.keras.optimizers.Adam(self.config.learning_rate),
        )

        # Train with early stopping
        early_stop = tf.keras.callbacks.EarlyStopping(
            monitor="total_loss",
            patience=3,
            restore_best_weights=True,
        )

        history = model.fit(
            train_ds,
            epochs=self.config.epochs,
            validation_data=eval_ds,
            callbacks=[early_stop],
            verbose=1,
        )

        # 6. Save model
        model_path = self._get_model_path(shop_id)
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        tf.saved_model.save(model, model_path)

        training_time = time.time() - start_time
        logger.info(
            f"✅ TFRS training complete for shop {shop_id}: "
            f"{training_time:.1f}s, "
            f"final loss: {history.history['total_loss'][-1]:.4f}"
        )

        return {
            "status": "success",
            "shop_id": shop_id,
            "products": len(products),
            "users": len(users),
            "training_examples": len(train_df),
            "epochs_trained": len(history.history["total_loss"]),
            "final_loss": float(history.history["total_loss"][-1]),
            "training_time_seconds": training_time,
            "model_path": model_path,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Data Loaders
    # ------------------------------------------------------------------

    async def _load_products(self, shop_id: str) -> List[Dict[str, Any]]:
        """Load products for a shop from ProductData."""
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
                    "price": p.price or 0,
                    "product_type": p.product_type or "",
                    "vendor": p.vendor or "",
                    "tags": p.tags or [],
                    "collections": p.collections or [],
                    "total_inventory": p.total_inventory or 0,
                    "is_active": p.is_active,
                }
                for p in products
            ]

    async def _load_users(self, shop_id: str) -> List[Dict[str, Any]]:
        """Load user features for a shop."""
        async with get_transaction_context() as session:
            # Try CustomerBehaviorFeatures first (richer), fall back to UserFeatures
            result = await session.execute(
                select(CustomerBehaviorFeatures)
                .where(CustomerBehaviorFeatures.shop_id == shop_id)
                .limit(10000)
            )
            users = result.scalars().all()

            if not users:
                result = await session.execute(
                    select(UserFeatures)
                    .where(UserFeatures.shop_id == shop_id)
                    .limit(10000)
                )
                users = result.scalars().all()

            return [
                {
                    "customer_id": u.customer_id,
                    "total_purchases": getattr(u, "total_purchases", 0),
                    "lifetime_value": getattr(u, "lifetime_value", 0),
                    "avg_order_value": getattr(u, "avg_order_value", 0),
                    "purchase_frequency_score": getattr(
                        u, "purchase_frequency_score", 0
                    ),
                    "recency_score": getattr(u, "recency_score", 0),
                    "churn_risk_score": getattr(u, "churn_risk_score", 1.0),
                    "primary_category": getattr(u, "primary_category", ""),
                    "category_diversity": getattr(u, "category_diversity", 0),
                }
                for u in users
            ]

    async def _load_interactions(self, shop_id: str) -> List[Dict[str, Any]]:
        """Load recent user interactions for a shop."""
        async with get_transaction_context() as session:
            from datetime import timedelta
            from app.shared.helpers import now_utc

            cutoff = now_utc() - timedelta(days=90)
            result = await session.execute(
                select(UserInteraction)
                .where(
                    UserInteraction.shop_id == shop_id,
                    UserInteraction.created_at >= cutoff,
                )
                .limit(50000)
            )
            interactions = result.scalars().all()
            return [
                {
                    "customer_id": i.customer_id,
                    "product_id": (
                        i.interaction_metadata.get("productId")
                        if i.interaction_metadata
                        else None
                    ),
                    "interaction_type": i.interaction_type,
                    "extension_type": i.extension_type,
                    "created_at": i.created_at.isoformat(),
                }
                for i in interactions
            ]

    async def _load_attributions(self, shop_id: str) -> List[Dict[str, Any]]:
        """Load purchase attributions for a shop."""
        async with get_transaction_context() as session:
            result = await session.execute(
                select(PurchaseAttribution)
                .where(PurchaseAttribution.shop_id == shop_id)
                .limit(10000)
            )
            attributions = result.scalars().all()
            return [
                {
                    "customer_id": a.customer_id,
                    "order_id": a.order_id,
                    "total_revenue": float(a.total_revenue or 0),
                    "attributed_revenue": a.attributed_revenue or {},
                    "contributing_extensions": a.contributing_extensions or [],
                    "purchase_products": (
                        a.attribution_metadata.get("products", [])
                        if a.attribution_metadata
                        else []
                    ),
                }
                for a in attributions
            ]

    # ------------------------------------------------------------------
    # Dataset Conversion
    # ------------------------------------------------------------------

    def _df_to_dataset(self, df: "pd.DataFrame") -> tuple:
        """Convert training DataFrame to TF datasets."""
        import pandas as pd

        # Fill missing values
        df = df.fillna(0)

        # Convert to TF dataset
        def gen():
            for _, row in df.iterrows():
                features = {}
                for col in df.columns:
                    val = row[col]
                    if isinstance(val, (list, np.ndarray)):
                        features[col] = np.array(val, dtype=np.float32)
                    elif isinstance(val, (int, float, np.integer, np.floating)):
                        features[col] = np.array(float(val), dtype=np.float32)
                    elif isinstance(val, str):
                        features[col] = np.array(val, dtype=np.string_)
                    elif isinstance(val, pd.Timestamp):
                        features[col] = np.array(val.timestamp(), dtype=np.float32)
                    elif val is None:
                        features[col] = np.array(0.0, dtype=np.float32)
                    else:
                        try:
                            features[col] = np.array(float(val), dtype=np.float32)
                        except (ValueError, TypeError):
                            features[col] = np.array(str(val), dtype=np.string_)

                label = features.pop("label", np.array(0.0, dtype=np.float32))
                yield features, label

        # Calculate split
        total = len(df)
        split = int(total * self.config.train_fraction)

        # Build datasets
        output_types = self._infer_output_types(df)

        full_ds = tf.data.Dataset.from_generator(gen, output_types=output_types)

        # Split into train/eval
        train_ds = full_ds.take(split).batch(self.config.batch_size).prefetch(2)
        eval_ds = full_ds.skip(split).batch(self.config.batch_size).prefetch(2)

        return train_ds, eval_ds

    def _infer_output_types(self, df):
        """Infer TF output types from DataFrame columns."""
        import pandas as pd

        feature_spec = {}
        for col in df.columns:
            if col == "label":
                continue
            val = df[col].iloc[0] if len(df) > 0 else None
            if isinstance(val, (list, np.ndarray)):
                feature_spec[col] = tf.float32
            elif isinstance(val, str):
                feature_spec[col] = tf.string
            else:
                feature_spec[col] = tf.float32

        return (feature_spec, tf.float32)

    def _products_to_dataset(self, products_df: "pd.DataFrame") -> tf.data.Dataset:
        """Convert product DataFrame to TF dataset for candidate retrieval."""

        def gen():
            for _, row in products_df.iterrows():
                features = {}
                for col in products_df.columns:
                    val = row[col]
                    if isinstance(val, (list, np.ndarray)):
                        features[col] = np.array(val, dtype=np.float32)
                    elif isinstance(val, (int, float)):
                        features[col] = np.array(float(val), dtype=np.float32)
                    elif isinstance(val, str):
                        features[col] = np.array(val, dtype=np.string_)
                    elif val is None:
                        features[col] = np.array(0.0, dtype=np.float32)
                    else:
                        features[col] = np.array(float(val), dtype=np.float32)
                yield features

        types = self._infer_output_types(products_df)
        return tf.data.Dataset.from_generator(gen, output_types=types)

    def _get_model_path(self, shop_id: str) -> str:
        """Get filesystem path for model storage."""
        base = os.getenv("TFRS_MODEL_PATH", self.config.model_base_path)
        return os.path.join(base, shop_id, "latest")
