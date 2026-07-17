"""
TFRS configuration.

Hyperparameters and model settings for the two-tower recommendation model.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TfrsConfig:
    """Configuration for TFRS model training and serving."""

    # Embedding dimensions
    user_embedding_dim: int = 64
    item_embedding_dim: int = 64

    # Tower hidden layers (query tower = user, candidate tower = item)
    query_tower_units: List[int] = field(default_factory=lambda: [128, 64, 32])
    candidate_tower_units: List[int] = field(default_factory=lambda: [128, 64, 32])

    # Ranking tower (scores retrieved candidates)
    ranking_tower_units: List[int] = field(default_factory=lambda: [64, 32, 16])

    # Training hyperparameters
    learning_rate: float = 0.001
    batch_size: int = 256
    epochs: int = 10
    train_fraction: float = 0.8

    # Retrieval settings
    num_candidates: int = 100  # Retrieve this many candidates before ranking
    num_recommendations: int = 10  # Return top-N after ranking

    # Feature settings
    max_description_length: int = 200
    text_embedding_dim: int = 128
    image_embedding_dim: int = 128  # Vertex AI multimodal embedding dim
    tag_embedding_dim: int = 16
    collection_embedding_dim: int = 16

    # Model storage
    model_base_path: str = "models/tfrs"
    model_format: str = "saved_model"

    # Training schedule (minutes between full retrains)
    training_interval_minutes: int = 360  # 6 hours

    # Feature columns
    product_feature_columns: List[str] = field(
        default_factory=lambda: [
            "product_id",
            "title",
            "description",
            "price",
            "product_type",
            "vendor",
            "tags",
            "collections",
            "total_inventory",
        ]
    )

    user_feature_columns: List[str] = field(
        default_factory=lambda: [
            "customer_id",
            "total_purchases",
            "lifetime_value",
            "avg_order_value",
            "purchase_frequency_score",
            "recency_score",
            "churn_risk_score",
            "primary_category",
            "category_diversity",
        ]
    )

    # Minimum data requirements before training
    min_products_for_training: int = 10
    min_users_for_training: int = 3
    min_interactions_for_training: int = 20

    # Co-purchase signal
    max_co_purchase_examples: int = (
        50000  # Max co-purchase pairs to include in training
    )
