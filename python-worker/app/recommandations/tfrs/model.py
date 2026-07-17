"""
TFRS two-tower recommendation model.

Uses TensorFlow Recommenders to build a retrieval + ranking model.
- Query tower: user features + past purchase embeddings
- Candidate tower: product features + Vertex AI text embeddings
- Retrieval task: find top-N candidates
- Ranking task: score candidates by predicted conversion
"""

import logging
from typing import Dict, Any, Optional, List

import tensorflow as tf
import tensorflow_recommenders as tfrs

logger = logging.getLogger(__name__)


class QueryTower(tf.keras.Model):
    """User query tower — encodes user features into an embedding."""

    def __init__(self, embedding_dim: int = 64):
        super().__init__()
        self.embedding_dim = embedding_dim

        # User ID embedding (sparse)
        self.user_embedding = tf.keras.Sequential(
            [
                tf.keras.layers.IntegerLookup(mask_token=None, oov_token=0),
                tf.keras.layers.Embedding(embedding_dim * 10, embedding_dim),
            ]
        )

        # Numeric feature processing
        self.numeric_dense = tf.keras.Sequential(
            [
                tf.keras.layers.Dense(64, activation="relu"),
                tf.keras.layers.BatchNormalization(),
                tf.keras.layers.Dropout(0.2),
                tf.keras.layers.Dense(32, activation="relu"),
            ]
        )

        # Final projection to embedding space
        self.projection = tf.keras.Sequential(
            [
                tf.keras.layers.Dense(embedding_dim, activation=None),
                tf.keras.layers.Lambda(lambda x: tf.math.l2_normalize(x, axis=1)),
            ]
        )

    def call(self, features: Dict[str, tf.Tensor]) -> tf.Tensor:
        """Forward pass: user features → user embedding."""
        embeddings = []

        # User ID embedding
        if "user_id" in features:
            user_ids = tf.strings.to_number(
                tf.strings.strip(features["user_id"]), tf.int64
            )
            embeddings.append(self.user_embedding(user_ids))

        # Numeric features
        numeric_features = []
        for col in [
            "log_price",
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
            numeric_concat = tf.concat(numeric_features, axis=1)
            embeddings.append(self.numeric_dense(numeric_concat))

        # Concatenate all embeddings
        if not embeddings:
            return tf.zeros(
                [tf.shape(next(iter(features.values())))[0], self.embedding_dim]
            )

        combined = tf.concat(embeddings, axis=1)

        # Project to embedding dimension
        return self.projection(self._ensure_dim(combined))

    def _ensure_dim(self, x: tf.Tensor) -> tf.Tensor:
        """Ensure minimum dimensions for projection layer."""
        if x.shape[-1] < self.embedding_dim:
            pad = self.embedding_dim - x.shape[-1]
            return tf.pad(x, [[0, 0], [0, pad]])
        return x


class CandidateTower(tf.keras.Model):
    """Product candidate tower — encodes product features into an embedding."""

    def __init__(self, embedding_dim: int = 64, text_embedding_dim: int = 128):
        super().__init__()
        self.embedding_dim = embedding_dim
        self.text_embedding_dim = text_embedding_dim

        # Product ID embedding
        self.product_embedding = tf.keras.Sequential(
            [
                tf.keras.layers.IntegerLookup(mask_token=None, oov_token=0),
                tf.keras.layers.Embedding(embedding_dim * 10, embedding_dim),
            ]
        )

        # Text embedding from Vertex AI (pre-computed, frozen during training)
        self.text_projection = tf.keras.Sequential(
            [
                tf.keras.layers.Dense(64, activation="relu"),
                tf.keras.layers.Dense(32, activation="relu"),
            ]
        )

        # Categorical features
        self.type_embedding = tf.keras.layers.Embedding(100, 8)
        self.vendor_embedding = tf.keras.layers.Embedding(500, 16)

        # Final projection
        self.projection = tf.keras.Sequential(
            [
                tf.keras.layers.Dense(embedding_dim, activation=None),
                tf.keras.layers.Lambda(lambda x: tf.math.l2_normalize(x, axis=1)),
            ]
        )

    def call(self, features: Dict[str, tf.Tensor]) -> tf.Tensor:
        """Forward pass: product features → product embedding."""
        embeddings = []

        # Product ID embedding
        if "product_id" in features:
            product_ids = tf.strings.to_number(
                tf.strings.strip(features["product_id"]), tf.int64
            )
            embeddings.append(self.product_embedding(product_ids))

        # Text embedding (from Vertex AI)
        if "embedding" in features:
            text_emb = tf.cast(features["embedding"], tf.float32)
            embeddings.append(self.text_projection(text_emb))

        # Price bucket
        if "price_bucket" in features:
            price_emb = tf.keras.layers.Embedding(10, 4)(
                tf.cast(features["price_bucket"], tf.int32)
            )
            embeddings.append(price_emb)

        # Product type
        if "product_type_id" in features:
            type_emb = self.type_embedding(
                tf.cast(features["product_type_id"], tf.int32)
            )
            embeddings.append(type_emb)

        # Vendor
        if "vendor_id" in features:
            vendor_emb = self.vendor_embedding(tf.cast(features["vendor_id"], tf.int32))
            embeddings.append(vendor_emb)

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
        """Score a (user, item) pair."""
        concat = tf.concat([user_emb, item_emb], axis=1)
        return self.dense_layers(concat)


class BetterBundleModel(tfrs.Model):
    """Two-tower retrieval + ranking model for BetterBundle."""

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

        # Retrieval task: find top candidates
        self.retrieval_task = tfrs.tasks.Retrieval(
            metrics=tfrs.metrics.FactorizedTopK(
                candidates=products.batch(128).map(self.candidate_tower),
                k=100,  # Evaluate top-100 accuracy
            ),
            loss=tfrs.losses.CachedCrossEntropyLoss(),
        )

        # Ranking task: score retrieved candidates
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

    def compute_loss(
        self,
        features: Dict[str, tf.Tensor],
        training: bool = False,
    ) -> tf.Tensor:
        # Get embeddings
        user_emb = self.query_tower(features)
        item_emb = self.candidate_tower(features)

        # Retrieval loss (candidate selection)
        retrieval_loss = self.retrieval_task(
            user_emb,
            item_emb,
            candidate_candidate_sampling_probability=features.get(
                "sampling_probability", None
            ),
        )

        # Ranking loss (conversion prediction)
        labels = tf.cast(
            features.get("label", tf.zeros([tf.shape(user_emb)[0]])), tf.float32
        )
        predicted_score = tf.squeeze(self.ranking_model(user_emb, item_emb), axis=-1)
        ranking_loss = self.ranking_task(
            labels=labels,
            predictions=predicted_score,
        )

        # Combined loss (retrieval + ranking weighted)
        return retrieval_loss + 0.5 * ranking_loss

    def get_config(self):
        return {
            "query_tower": self.query_tower,
            "candidate_tower": self.candidate_tower,
        }
