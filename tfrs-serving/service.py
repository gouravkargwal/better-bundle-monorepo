"""
BentoML service for BetterBundle TFRS recommendation model.

Loaded by the bentoml-serving container to serve predictions.
Handles batch inference for the two-tower retrieval + ranking model.

New-style BentoML (>=1.4): service is a class decorated with @bentoml.service,
API methods are decorated with @bentoml.api. JSON I/O is inferred from the
`dict` type hints on the methods.
"""

import logging

import bentoml

logger = logging.getLogger(__name__)

# Models are imported at startup from /models/<shop_id> via startup.py
# Each shop gets its own model: betterbundle-tfrs-<shop_id>:latest


@bentoml.service
class BetterBundleTfrs:
    """
    TFRS recommendation serving service.

    Each shop gets its own model: betterbundle-tfrs-<shop_id>:latest
    """

    @bentoml.api
    def predict(self, features: dict) -> dict:
        """
        Predict recommendation scores for a batch of (user, product) pairs.

        Expected input:
        {
            "shop_id": "shop_123",
            "features": {
                "user_id": ["user_1", ...],
                "product_id": ["prod_1", ...],
                "total_purchases": [3, ...],
                "lifetime_value": [150.0, ...],
                "avg_order_value": [50.0, ...],
                "purchase_frequency_score": [0.6, ...],
                "recency_score": [0.8, ...],
                "retention_score": [0.5, ...],
                "customer_tier": [2, ...],
                "time_of_day": [0, ...],
                "is_weekend": [0, ...],
                "context_id": [0, ...],
                "text_embedding": [[0.1, 0.2, ...], ...],
                "image_embedding": [[0.3, 0.4, ...], ...],
                "price_bucket": [3, ...],
                "product_type_id": [5, ...],
                "vendor_id": [12, ...],
                "tag_ids": [[1, 3, 5], ...],
                "collection_ids": [[2, 4], ...],
                "log_price": [4.6, ...],
                "inventory_score": [2.3, ...],
                "is_on_sale": [0, ...],
                "has_images": [1, ...]
            }
        }

        Returns:
        {
            "scores": [0.85, 0.32, ...],
            "user_embeddings": [[...], [...], ...],
            "item_embeddings": [[...], [...], ...]
        }
        """
        shop_id = features.pop("shop_id", None)
        if not shop_id:
            return {"error": "shop_id is required in features", "scores": []}

        if not features:
            return {"error": "No features provided", "scores": []}

        # Load the saved model for this shop (new-style BentoML >=1.4)
        # ponytail: per-request load is O(load) per call; cache at module scope if QPS grows
        model_tag = f"betterbundle-tfrs-{shop_id}:latest"
        try:
            model = bentoml.tensorflow.load_model(model_tag)
        except bentoml.exceptions.NotFound:
            return {"error": f"No model for shop {shop_id}", "scores": []}

        result = model(features)

        return {
            "scores": (
                result["score"].tolist()
                if hasattr(result["score"], "tolist")
                else result["score"]
            ),
            "user_embeddings": (
                result["user_embedding"].tolist()
                if hasattr(result["user_embedding"], "tolist")
                else result["user_embedding"]
            ),
            "item_embeddings": (
                result["item_embedding"].tolist()
                if hasattr(result["item_embedding"], "tolist")
                else result["item_embedding"]
            ),
        }

    @bentoml.api
    def health(self) -> dict:
        """Health check endpoint."""
        return {"status": "healthy", "model": "betterbundle-tfrs"}
