"""
Bundle Analyzer for cosine similarity and bundle analysis
"""

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from typing import List, Dict, Any
import logging
from datetime import datetime

from .models import ProductData, OrderData, SimilarityConfig, BundleConfig

logger = logging.getLogger(__name__)


class BundleAnalyzer:
    """
    Analyzer class for bundle analysis using cosine similarity and co-purchase patterns
    """
    
    def __init__(self, similarity_config: SimilarityConfig = None, bundle_config: BundleConfig = None):
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
            ngram_range=self.similarity_config.ngram_range
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
            
            features.append({
                "product_id": product.product_id,
                "title": product.title,
                "category": product.category or "unknown",
                "price": product.price,
                "price_normalized": price_normalized,
                "text_content": text_content,
                "has_image": 1 if product.image_url else 0,
                "tag_count": len(product.tags) if product.tags else 0,
            })
        
        return pd.DataFrame(features)
    
    def calculate_cosine_similarity(self, products: List[ProductData]) -> Dict[str, Any]:
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
                tfidf_matrix = self.vectorizer.fit_transform(
                    df["text_content"].fillna("")
                )
                text_similarity = cosine_similarity(tfidf_matrix)
            
            # Numerical features similarity
            numerical_features = df[
                ["price_normalized", "has_image", "tag_count"]
            ].values
            numerical_similarity = cosine_similarity(numerical_features)
            
            # Combine similarities (weighted average)
            if text_similarity is not None:
                combined_similarity = (
                    self.similarity_config.text_weight * text_similarity +
                    self.similarity_config.numerical_weight * numerical_similarity
                )
            else:
                combined_similarity = numerical_similarity
            
            # Get top similar products for each product
            similarities = []
            for i, product in enumerate(products):
                product_similarities = []
                for j, other_product in enumerate(products):
                    if i != j:
                        similarity_score = combined_similarity[i][j]
                        if similarity_score >= self.similarity_config.min_similarity_threshold:
                            product_similarities.append({
                                "product_id": other_product.product_id,
                                "title": other_product.title,
                                "similarity_score": float(similarity_score),
                                "category": other_product.category,
                                "price": other_product.price,
                            })
                
                # Sort by similarity score
                product_similarities.sort(
                    key=lambda x: x["similarity_score"], reverse=True
                )
                
                similarities.append({
                    "product_id": product.product_id,
                    "title": product.title,
                    "similar_products": product_similarities[
                        :self.similarity_config.top_k_similar_products
                    ],
                })
            
            return {
                "similarity_matrix": combined_similarity.tolist(),
                "product_similarities": similarities,
                "feature_matrix": df.to_dict("records"),
            }
            
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {str(e)}")
            raise Exception(f"Similarity calculation failed: {str(e)}")
    
    def analyze_co_purchase_patterns(
        self, products: List[ProductData], orders: List[OrderData]
    ) -> Dict[str, Any]:
        """
        Analyze which products are frequently purchased together
        
        Args:
            products: List of product data
            orders: List of order data
            
        Returns:
            Dictionary containing co-purchase analysis results
        """
        try:
            # Create product ID mapping
            product_ids = {p.product_id for p in products}
            
            # Count co-purchases
            co_purchase_counts = {}
            product_frequencies = {pid: 0 for pid in product_ids}
            
            for order in orders:
                order_products = set()
                for item in order.line_items:
                    product_id = item.get("productId") or item.get("product_id")
                    if product_id in product_ids:
                        order_products.add(product_id)
                        product_frequencies[product_id] += 1
                
                # Count pairs
                order_products_list = list(order_products)
                for i in range(len(order_products_list)):
                    for j in range(i + 1, len(order_products_list)):
                        pair = tuple(
                            sorted([order_products_list[i], order_products_list[j]])
                        )
                        co_purchase_counts[pair] = co_purchase_counts.get(pair, 0) + 1
            
            # Calculate metrics
            total_orders = len(orders)
            bundles = []
            
            for (
                product1_id,
                product2_id,
            ), co_purchase_count in co_purchase_counts.items():
                if co_purchase_count >= 1:  # Minimum threshold
                    # Calculate support, confidence, and lift
                    support = co_purchase_count / total_orders
                    confidence1 = (
                        co_purchase_count / product_frequencies[product1_id]
                        if product_frequencies[product1_id] > 0
                        else 0
                    )
                    confidence2 = (
                        co_purchase_count / product_frequencies[product2_id]
                        if product_frequencies[product2_id] > 0
                        else 0
                    )
                    confidence = max(confidence1, confidence2)
                    
                    # Calculate lift
                    expected_freq = (
                        product_frequencies[product1_id]
                        * product_frequencies[product2_id]
                    ) / (total_orders**2)
                    lift = (
                        (co_purchase_count / total_orders) / expected_freq
                        if expected_freq > 0
                        else 0
                    )
                    
                    # Apply thresholds
                    if (support >= self.bundle_config.min_support and 
                        confidence >= self.bundle_config.min_confidence and 
                        lift >= self.bundle_config.min_lift):
                        
                        bundles.append({
                            "product1_id": product1_id,
                            "product2_id": product2_id,
                            "co_purchase_count": co_purchase_count,
                            "support": support,
                            "confidence": confidence,
                            "lift": lift,
                            "strength": self.calculate_strength(confidence, lift),
                        })
            
            # Sort by lift and confidence
            bundles.sort(key=lambda x: x["lift"] * x["confidence"], reverse=True)
            
            return {
                "bundles": bundles,
                "product_frequencies": product_frequencies,
                "total_orders": total_orders,
            }
            
        except Exception as e:
            logger.error(f"Error analyzing co-purchase patterns: {str(e)}")
            return {"bundles": [], "product_frequencies": {}, "total_orders": 0}
    
    def analyze_bundles(
        self, products: List[ProductData], orders: List[OrderData]
    ) -> Dict[str, Any]:
        """
        Analyze bundles using both co-purchase patterns and cosine similarity
        
        Args:
            products: List of product data
            orders: List of order data
            
        Returns:
            Dictionary containing enhanced bundle analysis results
        """
        try:
            # Calculate cosine similarity
            similarity_results = self.calculate_cosine_similarity(products)
            
            # Analyze co-purchase patterns
            co_purchase_patterns = self.analyze_co_purchase_patterns(products, orders)
            
            # Combine similarity and co-purchase analysis
            enhanced_bundles = self.combine_analyses(
                similarity_results, co_purchase_patterns, products
            )
            
            return {
                "bundles": enhanced_bundles,
                "similarity_matrix": similarity_results["similarity_matrix"],
                "co_purchase_patterns": co_purchase_patterns,
                "metadata": {
                    "total_products": len(products),
                    "total_orders": len(orders),
                    "analysis_timestamp": datetime.now().isoformat(),
                    "analysis_method": "cosine_similarity + co_purchase",
                    "config": {
                        "similarity": self.similarity_config.dict(),
                        "bundle": self.bundle_config.dict()
                    }
                },
            }
            
        except Exception as e:
            logger.error(f"Error analyzing bundles: {str(e)}")
            raise Exception(f"Bundle analysis failed: {str(e)}")
    
    def combine_analyses(
        self,
        similarity_results: Dict,
        co_purchase_results: Dict,
        products: List[ProductData],
    ) -> List[Dict[str, Any]]:
        """
        Combine cosine similarity and co-purchase analysis for enhanced bundle recommendations
        
        Args:
            similarity_results: Results from cosine similarity analysis
            co_purchase_results: Results from co-purchase analysis
            products: List of product data
            
        Returns:
            List of enhanced bundle recommendations
        """
        try:
            enhanced_bundles = []
            product_map = {p.product_id: p for p in products}
            
            # Process co-purchase bundles
            for bundle in co_purchase_results.get("bundles", []):
                product1 = product_map.get(bundle["product1_id"])
                product2 = product_map.get(bundle["product2_id"])
                
                if product1 and product2:
                    # Find similarity score between these products
                    similarity_score = self.get_similarity_score(
                        bundle["product1_id"],
                        bundle["product2_id"],
                        similarity_results["product_similarities"],
                    )
                    
                    # Calculate combined score
                    combined_score = (
                        self.bundle_config.lift_weight * bundle["lift"]
                        + self.bundle_config.confidence_weight * bundle["confidence"]
                        + self.bundle_config.similarity_weight * similarity_score
                    )
                    
                    enhanced_bundle = {
                        "id": f"bundle-{bundle['product1_id']}-{bundle['product2_id']}",
                        "product_ids": [bundle["product1_id"], bundle["product2_id"]],
                        "products": [
                            {
                                "id": product1.product_id,
                                "title": product1.title,
                                "price": product1.price,
                                "category": product1.category,
                            },
                            {
                                "id": product2.product_id,
                                "title": product2.title,
                                "price": product2.price,
                                "category": product2.category,
                            },
                        ],
                        "co_purchase_count": bundle["co_purchase_count"],
                        "confidence": bundle["confidence"],
                        "lift": bundle["lift"],
                        "support": bundle["support"],
                        "similarity_score": similarity_score,
                        "combined_score": combined_score,
                        "strength": bundle["strength"],
                        "total_price": product1.price + product2.price,
                        "revenue_potential": (product1.price + product2.price)
                        * bundle["co_purchase_count"],
                    }
                    
                    enhanced_bundles.append(enhanced_bundle)
            
            # Sort by combined score
            enhanced_bundles.sort(key=lambda x: x["combined_score"], reverse=True)
            
            return enhanced_bundles
            
        except Exception as e:
            logger.error(f"Error combining analyses: {str(e)}")
            return []
    
    def get_similarity_score(
        self, product1_id: str, product2_id: str, similarities: List[Dict]
    ) -> float:
        """
        Get similarity score between two products
        
        Args:
            product1_id: First product ID
            product2_id: Second product ID
            similarities: List of product similarities
            
        Returns:
            Similarity score between the two products
        """
        for product_sim in similarities:
            if product_sim["product_id"] == product1_id:
                for similar_product in product_sim["similar_products"]:
                    if similar_product["product_id"] == product2_id:
                        return similar_product["similarity_score"]
        return 0.0
    
    def calculate_strength(self, confidence: float, lift: float) -> str:
        """
        Calculate bundle strength based on confidence and lift
        
        Args:
            confidence: Confidence score
            lift: Lift score
            
        Returns:
            Strength category (Strong, Medium, Weak)
        """
        score = confidence * lift
        if score >= 0.5:
            return "Strong"
        elif score >= 0.2:
            return "Medium"
        else:
            return "Weak"
    
    def get_similar_products(
        self, 
        target_product_id: str, 
        products: List[ProductData], 
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get similar products for a specific product
        
        Args:
            target_product_id: ID of the target product
            products: List of all products
            top_k: Number of similar products to return
            
        Returns:
            List of similar products with scores
        """
        try:
            similarity_results = self.calculate_cosine_similarity(products)
            
            # Find target product similarities
            target_similarities = next(
                (
                    sim
                    for sim in similarity_results["product_similarities"]
                    if sim["product_id"] == target_product_id
                ),
                None,
            )
            
            if target_similarities:
                return target_similarities["similar_products"][:top_k]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error getting similar products: {str(e)}")
            return []
