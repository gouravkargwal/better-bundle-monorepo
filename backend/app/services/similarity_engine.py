"""
Similarity engine service for the ML API
"""

from typing import List, Dict, Any
from app.core.logging import get_logger
from app.core.config import settings

# Import from our new local structure
from app.services.analyzer import BundleAnalyzer
from app.models.requests import SimilarityConfig, BundleConfig

logger = get_logger(__name__)


class SimilarityEngine:
    """Service for similarity calculations and bundle analysis"""

    def __init__(self):
        """Initialize the similarity engine with configuration"""
        self.similarity_config = SimilarityConfig(
            text_weight=settings.SIMILARITY_TEXT_WEIGHT,
            numerical_weight=settings.SIMILARITY_NUMERICAL_WEIGHT,
            max_features=settings.SIMILARITY_MAX_FEATURES,
            min_similarity_threshold=settings.SIMILARITY_MIN_THRESHOLD,
            top_k_similar_products=settings.SIMILARITY_TOP_K,
        )

        self.bundle_config = BundleConfig(
            min_support=settings.BUNDLE_MIN_SUPPORT,
            min_confidence=settings.BUNDLE_MIN_CONFIDENCE,
            min_lift=settings.BUNDLE_MIN_LIFT,
            max_bundle_size=settings.BUNDLE_MAX_SIZE,
        )

        self.analyzer = BundleAnalyzer(self.similarity_config, self.bundle_config)
        logger.info("Similarity engine initialized with configuration")

    def analyze_bundles(self, products: List, orders: List) -> Dict[str, Any]:
        """
        Analyze bundles using the similarity engine

        Args:
            products: List of products
            orders: List of orders

        Returns:
            Dictionary containing bundles and analysis metadata
        """
        try:
            logger.info(
                f"Starting bundle analysis for {len(products)} products and {len(orders)} orders"
            )

            # Perform analysis using the existing analyzer
            analysis_results = self.analyzer.analyze_bundles(products, orders)

            logger.info(
                f"Bundle analysis completed. Generated {len(analysis_results.get('bundles', []))} bundles"
            )

            return analysis_results

        except Exception as e:
            logger.error(f"Error in bundle analysis: {str(e)}")
            raise

    def calculate_cosine_similarity(
        self, products: List, target_product_id: str = None, top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Calculate cosine similarity between products

        Args:
            products: List of products
            target_product_id: Optional target product ID
            top_k: Number of similar products to return

        Returns:
            Dictionary containing similarity results
        """
        try:
            logger.info(f"Calculating cosine similarity for {len(products)} products")

            # Perform similarity calculation
            similarity_results = self.analyzer.calculate_cosine_similarity(products)

            # Filter for target product if specified
            if target_product_id:
                target_similarities = next(
                    (
                        sim
                        for sim in similarity_results["product_similarities"]
                        if sim["product_id"] == target_product_id
                    ),
                    None,
                )
                if target_similarities:
                    similarities = target_similarities["similar_products"][:top_k]
                else:
                    similarities = []
            else:
                # Return top similarities for all products
                similarities = []
                for product_sim in similarity_results["product_similarities"]:
                    similarities.extend(product_sim["similar_products"][:top_k])

            return {
                "success": True,
                "similarities": similarities,
                "matrix": similarity_results["similarity_matrix"],
                "metadata": {
                    "total_products": len(products),
                    "target_product_id": target_product_id,
                    "top_k": top_k,
                },
            }

        except Exception as e:
            logger.error(f"Error in cosine similarity calculation: {str(e)}")
            raise

    def update_configuration(
        self,
        similarity_config: Dict[str, Any] = None,
        bundle_config: Dict[str, Any] = None,
    ) -> None:
        """
        Update the engine configuration

        Args:
            similarity_config: New similarity configuration
            bundle_config: New bundle configuration
        """
        try:
            if similarity_config:
                self.similarity_config = SimilarityConfig(**similarity_config)
                logger.info("Similarity configuration updated")

            if bundle_config:
                self.bundle_config = BundleConfig(**bundle_config)
                logger.info("Bundle configuration updated")

            # Create new analyzer with updated config
            self.analyzer = BundleAnalyzer(self.similarity_config, self.bundle_config)
            logger.info("Similarity engine configuration updated successfully")

        except Exception as e:
            logger.error(f"Error updating configuration: {str(e)}")
            raise

    def get_current_configuration(self) -> Dict[str, Any]:
        """Get current engine configuration"""
        return {
            "similarity": self.similarity_config.dict(),
            "bundle": self.bundle_config.dict(),
        }
