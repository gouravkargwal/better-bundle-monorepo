"""
TFRS two-tower recommendation model with rich features.

Enhanced with:
- Query tower: user features + cart context + time/day + customer_tier
- Candidate tower: text + image embeddings, tags, collections, price signals
- Context-aware ranking
"""

import logging
from typing import Dict, Any, Optional, List

import tensorflow as tf
import tensorflow_recommenders as tfrs

logger = logging.getLogger(__name__)


class QueryTower(tf.keras.Model):
    """User query tower — encodes user + context features into an embedding.

    Features:
    - User ID + purchase history (LTV, frequency, recency)
    - Customer tier (new/regular/VIP)
    - Context: time of day, day of week, weekend flag, placement context
    - Cart contents (if available during serving)
    """

    def __init__(self, embedding_dim: int = 64):
        super().__init__()
        self.embedding_dim = embedding_dim

        # User ID embedding
        self.user_embedding = tf.keras.Sequential(
            [
                tf.keras.layers.IntegerLookup(mask_token=None, oov_token=0),
                tf.keras.layers.Embedding(embedding_dim * 10, embedding_dim),
            ]
        )

        # Customer tier embedding (0=new, 1=regular, 2=VIP, 3=wholesale)
        self.tier_embedding = tf.keras.layers.Embedding(4, 4)

        # Context embeddings
        self.time_embedding = tf.keras.layers.Embedding(
            4, 2
        )  # morning/afternoon/evening/night
        self.weekend_embedding = tf.keras.layers.Embedding(2, 1)  # weekday/weekend
        self.context_embedding = tf.keras.layers.Embedding(
            10, 4
        )  # checkout/post_purchase/etc

        # Numeric feature processing
        self.numeric_dense = tf.keras.Sequential(
            [
                tf.keras.layers.Dense(64, activation="relu"),
                tf.keras.layers.BatchNormalization(),
                tf.keras.layers.Dropout(0.2),
                tf.keras.layers.Dense(32, activation="relu"),
            ]
        )

        # Final projection
        self.projection = tf.keras.Sequential(
            [
                tf.keras.layers.Dense(embedding_dim, activation=None),
                tf.keras.layers.Lambda(lambda x: tf.math.l2_normalize(x, axis=1)),
            ]
        )

    def call(self, features: Dict[str, tf.Tensor]) -> tf.Tensor:
        embeddings = []

        # User ID
        if "user_id" in features:
            user_ids = tf.strings.to_number(
                tf.strings.strip(features["user_id"]), tf.int64
            )
            embeddings.append(self.user_embedding(user_ids))

        # Purchase history numerics
        numeric_features = []
        for col in [
            "total_purchases",
            "lifetime_value",
            "avg_order_value",
            "purchase_frequency_score",
            "recency_score",
            "retention_score",
        ]:
            if col in features:
                numeric_features.append(
                    tf.reshape(tf.cast(features[col], tf.float32), [-1, 1])
                )
        if numeric_features:
            embeddings.append(self.numeric_dense(tf.concat(numeric_features, axis=1)))

        # Customer tier
        if "customer_tier" in features:
            embeddings.append(
                self.tier_embedding(tf.cast(features["customer_tier"], tf.int32))
            )

        # Time of day (categorical)
        if "time_of_day" in features:
            embeddings.append(
                self.time_embedding(tf.cast(features["time_of_day"], tf.int32))
            )

        # Weekend flag
        if "is_weekend" in features:
            embeddings.append(
                self.weekend_embedding(tf.cast(features["is_weekend"], tf.int32))
            )

        # Context (checkout vs post_purchase etc)
        if "context_id" in features:
            embeddings.append(
                self.context_embedding(tf.cast(features["context_id"], tf.int32))
            )

        if not embeddings:
            return tf.zeros(
                [tf.shape(next(iter(features.values())))[0], self.embedding_dim]
            )

        combined = tf.concat(embeddings, axis=1)
        return self.projection(self._ensure_dim(combined))

    def _ensure_dim(self, x: tf.Tensor) -> tf.Tensor:
        if x.shape[-1] < self.embedding_dim:
            pad = self.embedding_dim - x.shape[-1]
            return tf.pad(x, [[0, 0], [0, pad]])
        return x


class CandidateTower(tf.keras.Model):
    """Product candidate tower — encodes rich product features.

    Features:
    - Product ID + text embedding (title/desc) + image embedding
    - Price signals: bucket, log price, on-sale flag
    - Categorical: product type, vendor
    - Tags + collections (multi-hot via mean embedding)
    - Inventory score
    """

    def __init__(
        self,
        embedding_dim: int = 64,
        text_embedding_dim: int = 128,
        image_embedding_dim: int = 128,
        tag_embedding_dim: int = 16,
        collection_embedding_dim: int = 16,
    ):
        super().__init__()
        self.embedding_dim = embedding_dim

        # Product ID
        self.product_embedding = tf.keras.Sequential(
            [
                tf.keras.layers.IntegerLookup(mask_token=None, oov_token=0),
                tf.keras.layers.Embedding(embedding_dim * 10, embedding_dim),
            ]
        )

        # Text embedding projection (Vertex AI → dense)
        self.text_projection = tf.keras.Sequential(
            [
                tf.keras.layers.Dense(64, activation="relu"),
                tf.keras.layers.Dense(32, activation="relu"),
            ]
        )

        # Image embedding projection (Vertex AI → dense)
        self.image_projection = tf.keras.Sequential(
            [
                tf.keras.layers.Dense(32, activation="relu"),
                tf.keras.layers.Dense(16, activation="relu"),
            ]
        )

        # Categorical: product type, vendor
        self.type_embedding = tf.keras.layers.Embedding(100, 8)
        self.vendor_embedding = tf.keras.layers.Embedding(500, 16)

        # Tags: multi-hot → mean embedding
        self.tag_embedding = tf.keras.layers.Embedding(500, tag_embedding_dim)
        self.collection_embedding = tf.keras.layers.Embedding(
            500, collection_embedding_dim
        )

        # Price signals
        self.price_bucket_emb = tf.keras.layers.Embedding(10, 4)

        # Numeric: log_price, inventory_score, is_on_sale, has_images
        self.numeric_dense = tf.keras.Sequential(
            [
                tf.keras.layers.Dense(16, activation="relu"),
            ]
        )

        # Final projection
        self.projection = tf.keras.Sequential(
            [
                tf.keras.layers.Dense(embedding_dim, activation=None),
                tf.keras.layers.Lambda(lambda x: tf.math.l2_normalize(x, axis=1)),
            ]
        )

    def call(self, features: Dict[str, tf.Tensor]) -> tf.Tensor:
        embeddings = []

        # Product ID
        if "product_id" in features:
            product_ids = tf.strings.to_number(
                tf.strings.strip(features["product_id"]), tf.int64
            )
            embeddings.append(self.product_embedding(product_ids))

        # Text embedding (Vertex AI from title+description)
        if "text_embedding" in features:
            embeddings.append(
                self.text_projection(tf.cast(features["text_embedding"], tf.float32))
            )

        # Image embedding (Vertex AI multimodal)
        if "image_embedding" in features:
            embeddings.append(
                self.image_projection(tf.cast(features["image_embedding"], tf.float32))
            )

        # Price signals
        if "price_bucket" in features:
            embeddings.append(
                self.price_bucket_emb(tf.cast(features["price_bucket"], tf.int32))
            )

        # Product type + vendor
        if "product_type_id" in features:
            embeddings.append(
                self.type_embedding(tf.cast(features["product_type_id"], tf.int32))
            )
        if "vendor_id" in features:
            embeddings.append(
                self.vendor_embedding(tf.cast(features["vendor_id"], tf.int32))
            )

        # Tags (multi-hot → mean pooling)
        if "tag_ids" in features:
            tag_ids = tf.cast(features["tag_ids"], tf.int32)
            tag_embs = self.tag_embedding(tag_ids)
            embeddings.append(tf.reduce_mean(tag_embs, axis=1))

        # Collections (multi-hot → mean pooling)
        if "collection_ids" in features:
            coll_ids = tf.cast(features["collection_ids"], tf.int32)
            coll_embs = self.collection_embedding(coll_ids)
            embeddings.append(tf.reduce_mean(coll_embs, axis=1))

        # Numeric flags
        numeric_feats = []
        for col in ["log_price", "inventory_score", "is_on_sale", "has_images"]:
            if col in features:
                numeric_feats.append(
                    tf.reshape(tf.cast(features[col], tf.float32), [-1, 1])
                )
        if numeric_feats:
            embeddings.append(self.numeric_dense(tf.concat(numeric_feats, axis=1)))

        if not embeddings:
            return tf.zeros(
                [tf.shape(next(iter(features.values())))[0], self.embedding_dim]
            )

        combined = tf.concat(embeddings, axis=1)
        return self.projection(combined)


class RankingModel(tf.keras.Model):
    """Cross tower — scores (user, candidate) pairs after retrieval."""

    def __init__(self, hidden_units: List[int] = None):
        super().__init__()
        hidden_units = hidden_units or [64, 32, 16]

        self.dense_layers = tf.keras.Sequential()
        for units in hidden_units:
            self.dense_layers.add(tf.keras.layers.Dense(units, activation="relu"))
            self.dense_layers.add(tf.keras.layers.BatchNormalization())
            self.dense_layers.add(tf.keras.layers.Dropout(0.2))
        self.dense_layers.add(tf.keras.layers.Dense(1, activation="sigmoid"))

    def call(self, user_emb: tf.Tensor, item_emb: tf.Tensor) -> tf.Tensor:
        concat = tf.concat([user_emb, item_emb], axis=1)
        return self.dense_layers(concat)


class BetterBundleModel(tfrs.Model):
    """Two-tower retrieval + ranking model with rich features."""

    def __init__(
        self,
        query_tower: QueryTower,
        candidate_tower: CandidateTower,
        products: tf.data.Dataset,
    ):
        super().__init__()
        self.query_tower = query_tower
        self.candidate_tower = candidate_tower
        self.ranking_model = RankingModel()

        self.retrieval_task = tfrs.tasks.Retrieval(
            metrics=tfrs.metrics.FactorizedTopK(
                candidates=products.batch(128).map(self.candidate_tower),
                k=100,
            ),
            loss=tfrs.losses.CachedCrossEntropyLoss(),
        )

        self.ranking_task = tfrs.tasks.Ranking(
            loss=tf.keras.losses.MeanSquaredError(),
            metrics=[
                tf.keras.metrics.RootMeanSquaredError(),
                tf.keras.metrics.MeanAbsoluteError(),
            ],
        )

    def call(self, features: Dict[str, tf.Tensor]) -> Dict[str, tf.Tensor]:
        user_emb = self.query_tower(features)
        item_emb = self.candidate_tower(features)
        score = self.ranking_model(user_emb, item_emb)

        return {
            "user_embedding": user_emb,
            "item_embedding": item_emb,
            "score": tf.squeeze(score, axis=-1),
        }

    def compute_loss(self, features, training=False) -> tf.Tensor:
        user_emb = self.query_tower(features)
        item_emb = self.candidate_tower(features)

        retrieval_loss = self.retrieval_task(
            user_emb,
            item_emb,
            candidate_candidate_sampling_probability=features.get(
                "sampling_probability", None
            ),
        )

        labels = tf.cast(
            features.get("label", tf.zeros([tf.shape(user_emb)[0]])), tf.float32
        )
        predicted_score = tf.squeeze(self.ranking_model(user_emb, item_emb), axis=-1)
        ranking_loss = self.ranking_task(labels=labels, predictions=predicted_score)

        return retrieval_loss + 0.5 * ranking_loss
