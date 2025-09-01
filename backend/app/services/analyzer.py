"""
Bundle Analyzer service for the ML API
Handles product similarity calculations using cosine similarity and TF-IDF
"""

import logging
import numpy as np
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler
from app.models.requests import ProductData, OrderData, SimilarityConfig, BundleConfig

logger = logging.getLogger(__name__)


class BundleAnalyzer:
    """
    Analyzer class for bundle analysis using cosine similarity and co-purchase patterns
    """

    def __init__(
        self,
        similarity_config: SimilarityConfig = None,
        bundle_config: BundleConfig = None,
    ):
        """
        Initialize the analyzer with configuration

        Args:
            similarity_config: Configuration for similarity calculations
            bundle_config: Configuration for bundle analysis
        """
        self.similarity_config = similarity_config or SimilarityConfig()
        self.bundle_config = bundle_config or BundleConfig()

        # Initialize vectorizer with config
        self.vectorizer = TfidfVectorizer(
            max_features=self.similarity_config.max_features,
            stop_words="english",
            ngram_range=self.similarity_config.ngram_range,
        )
        self.scaler = StandardScaler()

    def extract_product_features(self, products: List[ProductData]) -> pd.DataFrame:
        """
        Extract features from product data for similarity calculation

        Args:
            products: List of product data

        Returns:
            DataFrame with extracted features
        """
        features = []

        for product in products:
            # Combine text features
            text_features = []
            if product.title:
                text_features.append(product.title.lower())
            if product.category:
                text_features.append(product.category.lower())
            if product.description:
                text_features.append(product.description.lower())
            if product.tags:
                text_features.extend([tag.lower() for tag in product.tags])

            text_content = " ".join(text_features)

            # Numerical features
            price_normalized = np.log1p(product.price) if product.price > 0 else 0

            features.append(
                {
                    "product_id": product.product_id,
                    "title": product.title,
                    "category": product.category or "unknown",
                    "price": product.price,
                    "price_normalized": price_normalized,
                    "text_content": text_content,
                    "has_image": 1 if product.image_url else 0,
                    "tag_count": len(product.tags) if product.tags else 0,
                }
            )

        return pd.DataFrame(features)

    def calculate_cosine_similarity(
        self, products: List[ProductData]
    ) -> Dict[str, Any]:
        """
        Calculate cosine similarity between products

        Args:
            products: List of product data

        Returns:
            Dictionary containing similarity results
        """
        try:
            # Extract features
            df = self.extract_product_features(products)

            # Text-based similarity using TF-IDF
            text_similarity = None
            if not df["text_content"].empty and df["text_content"].str.strip().any():
                text_features = self.vectorizer.fit_transform(df["text_content"])
                text_similarity = cosine_similarity(text_features)

            # Numerical features similarity
            numerical_features = df[
                ["price_normalized", "has_image", "tag_count"]
            ].values
            numerical_similarity = cosine_similarity(
                self.scaler.fit_transform(numerical_features)
            )

            # Combine similarities with weights
            if text_similarity is not None:
                combined_similarity = (
                    self.similarity_config.text_weight * text_similarity
                    + self.similarity_config.numerical_weight * numerical_similarity
                )
            else:
                combined_similarity = numerical_similarity

            # Get top similar products for each product
            product_similarities = []
            for i, product_id in enumerate(df["product_id"]):
                similarities = []
                for j, other_product_id in enumerate(df["product_id"]):
                    if i != j:
                        similarities.append(
                            {
                                "product_id": other_product_id,
                                "similarity": combined_similarity[i][j],
                            }
                        )

                # Sort by similarity and filter by threshold
                similarities.sort(key=lambda x: x["similarity"], reverse=True)
                filtered_similarities = [
                    s
                    for s in similarities
                    if s["similarity"]
                    >= self.similarity_config.min_similarity_threshold
                ][: self.similarity_config.top_k_similar_products]

                product_similarities.append(
                    {
                        "product_id": product_id,
                        "similar_products": filtered_similarities,
                    }
                )

            return {
                "product_similarities": product_similarities,
                "similarity_matrix": combined_similarity.tolist(),
                "metadata": {
                    "total_products": len(products),
                    "text_weight": self.similarity_config.text_weight,
                    "numerical_weight": self.similarity_config.numerical_weight,
                    "min_threshold": self.similarity_config.min_similarity_threshold,
                },
            }

        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {str(e)}")
            raise

    def analyze_bundles(
        self, products: List[ProductData], orders: List[OrderData]
    ) -> Dict[str, Any]:
        """
        Analyze product bundles using co-purchase patterns and similarity

        Args:
            products: List of product data
            orders: List of order data

        Returns:
            Dictionary containing bundle analysis results
        """
        try:
            logger.info(
                f"Starting bundle analysis for {len(products)} products and {len(orders)} orders"
            )

            # Calculate product similarities
            similarity_results = self.calculate_cosine_similarity(products)

            # Analyze co-purchase patterns
            co_purchase_patterns = self._analyze_co_purchase_patterns(products, orders)

            # Generate bundles
            bundles = self._generate_bundles(
                products, similarity_results, co_purchase_patterns
            )

            return {
                "bundles": bundles,
                "similarity_matrix": similarity_results["similarity_matrix"],
                "metadata": {
                    "total_products": len(products),
                    "total_orders": len(orders),
                    "bundles_generated": len(bundles),
                    "analysis_timestamp": datetime.now().isoformat(),
                },
            }

        except Exception as e:
            logger.error(f"Error in bundle analysis: {str(e)}")
            raise

    def _analyze_co_purchase_patterns(
        self, products: List[ProductData], orders: List[OrderData]
    ) -> Dict[str, Any]:
        """Analyze co-purchase patterns from order data"""
        try:
            logger.info(
                f"Co-purchase analysis: Starting with {len(products)} products and {len(orders)} orders"
            )

            # Create product ID set for quick lookup
            product_ids = {p.product_id for p in products}
            logger.info(
                f"Co-purchase analysis: Product IDs for lookup: {len(product_ids)}"
            )

            # Analyze co-purchase patterns
            co_purchase_counts = {}
            product_frequencies = {p.product_id: 0 for p in products}

            for order_idx, order in enumerate(orders):
                order_products = set()

                # Debug: Log raw line items structure
                if order_idx < 3:  # Log first 3 orders for debugging
                    logger.info(
                        f"Co-purchase analysis: Order {order_idx + 1} raw lineItems: {type(order.line_items)} - {order.line_items}"
                    )

                for item in order.line_items:
                    # Handle different product ID formats and ensure it's a string
                    product_id = None

                    # Debug: Log individual item structure
                    if order_idx < 3:
                        logger.info(
                            f"Co-purchase analysis: Order {order_idx + 1} item: {type(item)} - {item}"
                        )

                    if isinstance(item, dict):
                        # Try different possible field names for product ID
                        product_id = (
                            item.get("productId")
                            or item.get("product_id")
                            or item.get("id")
                            or item.get("variantId")
                            or item.get("variant_id")
                        )
                        # Handle nested objects like {"productId": {"id": "gid://..."}}
                        if isinstance(product_id, dict):
                            product_id = (
                                product_id.get("id")
                                or product_id.get("gid")
                                or product_id.get("_id")
                            )
                    elif hasattr(item, "productId"):
                        product_id = getattr(item, "productId")
                        if isinstance(product_id, dict):
                            product_id = product_id.get("id")
                    elif hasattr(item, "product_id"):
                        product_id = getattr(item, "product_id")
                    elif hasattr(item, "id"):
                        product_id = getattr(item, "id")
                    elif hasattr(item, "variantId"):
                        product_id = getattr(item, "variantId")
                        if isinstance(product_id, dict):
                            product_id = product_id.get("id")

                    if product_id is not None:
                        product_id = str(product_id)  # Ensure it's a string
                        if product_id in product_ids:
                            order_products.add(product_id)
                            product_frequencies[product_id] += 1
                        else:
                            if order_idx < 3:
                                logger.info(
                                    f"Co-purchase analysis: Product ID {product_id} not found in product lookup set"
                                )
                    else:
                        if order_idx < 3:
                            logger.info(
                                f"Co-purchase analysis: Could not extract product ID from item: {item}"
                            )

                # Count co-purchases
                if len(order_products) > 1:
                    for i, product1 in enumerate(order_products):
                        for product2 in list(order_products)[i + 1 :]:
                            pair = tuple(sorted([product1, product2]))
                            co_purchase_counts[pair] = (
                                co_purchase_counts.get(pair, 0) + 1
                            )

                if order_idx < 5:  # Log first 5 orders for debugging
                    logger.info(
                        f"Co-purchase analysis: Order {order_idx + 1} - {len(order_products)} products: {list(order_products)[:5]}"
                    )

            logger.info(
                f"Co-purchase analysis: Found {len(co_purchase_counts)} co-purchase patterns"
            )
            logger.info(
                f"Co-purchase analysis: Product frequencies: {dict(list(product_frequencies.items())[:5])}..."
            )

            return {
                "co_purchase_counts": co_purchase_counts,
                "product_frequencies": product_frequencies,
                "total_orders": len(orders),
            }

        except Exception as e:
            logger.error(f"Error analyzing co-purchase patterns: {str(e)}")
            return {
                "co_purchase_counts": {},
                "product_frequencies": {},
                "total_orders": 0,
            }

    def _generate_bundles(
        self,
        products: List[ProductData],
        similarity_results: Dict[str, Any],
        co_purchase_patterns: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Generate product bundles based on similarity and co-purchase patterns"""
        try:
            bundles = []
            co_purchase_counts = co_purchase_patterns.get("co_purchase_counts", {})

            # Generate bundles from co-purchase patterns
            for (product1, product2), count in co_purchase_counts.items():
                if (
                    count
                    >= self.bundle_config.min_support
                    * co_purchase_patterns["total_orders"]
                ):
                    # Calculate bundle metrics
                    bundle = {
                        "product_ids": [product1, product2],
                        "co_purchase_count": count,
                        "support": count / co_purchase_patterns["total_orders"],
                        "confidence": count
                        / co_purchase_patterns["product_frequencies"][product1],
                        "lift": self._calculate_lift(
                            product1, product2, count, co_purchase_patterns
                        ),
                        "similarity_score": self._get_similarity_score(
                            product1, product2, similarity_results
                        ),
                    }

                    # Apply filters
                    if (
                        bundle["confidence"] >= self.bundle_config.min_confidence
                        and bundle["lift"] >= self.bundle_config.min_lift
                    ):
                        bundles.append(bundle)

            # Sort bundles by score
            bundles.sort(
                key=lambda x: (
                    x["lift"] * self.bundle_config.lift_weight
                    + x["confidence"] * self.bundle_config.confidence_weight
                    + x["similarity_score"] * self.bundle_config.similarity_weight
                ),
                reverse=True,
            )

            return bundles

        except Exception as e:
            logger.error(f"Error generating bundles: {str(e)}")
            return []

    def _calculate_lift(
        self,
        product1: str,
        product2: str,
        co_purchase_count: int,
        co_purchase_patterns: Dict[str, Any],
    ) -> float:
        """Calculate lift for a product pair"""
        try:
            total_orders = co_purchase_patterns["total_orders"]
            freq1 = co_purchase_patterns["product_frequencies"][product1]
            freq2 = co_purchase_patterns["product_frequencies"][product2]

            if freq1 == 0 or freq2 == 0:
                return 0.0

            expected = (freq1 * freq2) / total_orders
            if expected == 0:
                return 0.0

            return co_purchase_count / expected

        except Exception:
            return 0.0

    def _get_similarity_score(
        self,
        product1: str,
        product2: str,
        similarity_results: Dict[str, Any],
    ) -> float:
        """Get similarity score between two products"""
        try:
            # Find product indices
            product_similarities = similarity_results["product_similarities"]

            for ps in product_similarities:
                if ps["product_id"] == product1:
                    for similar in ps["similar_products"]:
                        if similar["product_id"] == product2:
                            return similar["similarity"]

            return 0.0

        except Exception:
            return 0.0
