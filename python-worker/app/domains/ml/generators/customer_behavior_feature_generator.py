"""
Customer Behavior Feature Generator - OPTIMIZED FOR GORSE
Computes only behavioral metrics needed for categorical label creation
Eliminates redundant data and focuses on actionable segments
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from collections import Counter
from app.core.logging import get_logger
from app.domains.ml.adapters.adapter_factory import InteractionEventAdapterFactory
from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class CustomerBehaviorFeatureGenerator(BaseFeatureGenerator):
    """
    Simplified feature generator focused on behavioral patterns for Gorse labels

    Key principle: Only compute features that can be converted to categorical labels
    Everything else is noise for recommendations
    """

    def __init__(self):
        super().__init__()
        self.adapter_factory = InteractionEventAdapterFactory()

    async def generate_features(
        self, customer: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate behavioral features needed for Gorse label creation

        Args:
            customer: Customer data from CustomerData table
            context: Contains user_interactions, user_sessions, purchase_attributions

        Returns:
            Minimal feature set optimized for label conversion
        """
        try:
            customer_id = customer.get("customer_id", "")
            logger.debug(f"Computing behavior features for customer: {customer_id}")

            shop = context.get("shop", {})
            user_interactions = context.get("user_interactions", [])

            # If no interaction data, return minimal features
            if not user_interactions:
                return self._get_minimal_features(customer, shop)

            features = {
                "shop_id": shop.get("id", ""),
                "customer_id": customer_id,
            }

            # CORE METRICS (used for label creation)
            features.update(self._compute_engagement_metrics(user_interactions))
            features.update(self._compute_recency_metrics(user_interactions))
            features.update(self._compute_conversion_metrics(user_interactions))
            features.update(self._compute_browsing_style(user_interactions))
            features.update(self._compute_device_preference(user_interactions))

            # Timestamp
            from app.shared.helpers import now_utc

            features["last_computed_at"] = now_utc()

            return features

        except Exception as e:
            logger.error(f"Failed to compute behavior features: {str(e)}")
            return self._get_minimal_features(customer, context.get("shop", {}))

    def _compute_engagement_metrics(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compute engagement level for label: engagement:high/medium/low

        Based on:
        - Total interaction count
        - Interaction diversity (types of actions)
        - Session frequency
        """
        total_interactions = len(interactions)

        # Count different interaction types
        interaction_types = set()
        for interaction in interactions:
            interaction_types.add(interaction.get("interactionType", ""))

        # Engagement score (0-1 scale)
        # High: 50+ interactions with 5+ types
        # Medium: 10+ interactions with 3+ types
        # Low: < 10 interactions
        interaction_score = min(total_interactions / 50, 1.0)
        diversity_score = min(len(interaction_types) / 5.0, 1.0)
        engagement_score = interaction_score * 0.6 + diversity_score * 0.4

        return {
            "engagement_score": round(engagement_score, 3),
            "total_interaction_count": total_interactions,
            "interaction_type_count": len(interaction_types),
        }

    def _compute_recency_metrics(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compute recency for label: recency:active/recent/lapsing/dormant

        Based on days since last interaction
        """
        if not interactions:
            return {
                "recency_score": 0.0,
                "days_since_last_interaction": None,
            }

        # Find most recent interaction
        latest_time = None
        for interaction in interactions:
            created_at = self._parse_datetime(interaction.get("created_at"))
            if created_at:
                if latest_time is None or created_at > latest_time:
                    latest_time = created_at

        if not latest_time:
            return {
                "recency_score": 0.0,
                "days_since_last_interaction": None,
            }

        current_time = datetime.now(timezone.utc)
        days_since_last = (current_time - latest_time).days

        # Recency score (exponential decay)
        # 1.0 for today, 0.5 for 7 days ago, 0.1 for 30 days
        import math

        recency_score = math.exp(-days_since_last / 10)

        return {
            "recency_score": round(recency_score, 3),
            "days_since_last_interaction": days_since_last,
        }

    def _compute_conversion_metrics(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compute conversion propensity for label: conversion:ready/likely/unlikely

        Based on:
        - Browse-to-cart rate
        - Cart-to-purchase rate
        """
        views = 0
        cart_adds = 0
        purchases = 0

        for interaction in interactions:
            interaction_type = interaction.get("interactionType", "").lower()

            if "view" in interaction_type or "viewed" in interaction_type:
                views += 1
            elif "cart" in interaction_type and "add" in interaction_type:
                cart_adds += 1
            elif (
                "purchase" in interaction_type or "order_completed" in interaction_type
            ):
                purchases += 1

        # Calculate rates
        browse_to_cart_rate = (cart_adds / views) if views > 0 else 0.0
        cart_to_purchase_rate = (purchases / cart_adds) if cart_adds > 0 else 0.0

        # Conversion propensity score (weight cart-to-purchase more heavily)
        conversion_score = browse_to_cart_rate * 0.3 + cart_to_purchase_rate * 0.7

        return {
            "browse_to_cart_rate": round(browse_to_cart_rate, 3),
            "cart_to_purchase_rate": round(cart_to_purchase_rate, 3),
            "conversion_propensity_score": round(conversion_score, 3),
        }

    def _compute_browsing_style(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compute browsing style for label: style:decisive/impulse/researcher

        Based on:
        - View-to-cart speed
        - Number of views before purchase
        - Session depth
        """
        views = 0
        cart_adds = 0
        purchases = 0
        unique_products_viewed = set()

        for interaction in interactions:
            interaction_type = interaction.get("interactionType", "").lower()
            metadata = interaction.get("metadata", {})
            product_id = metadata.get("product_id")

            if "view" in interaction_type:
                views += 1
                if product_id:
                    unique_products_viewed.add(product_id)
            elif "cart" in interaction_type and "add" in interaction_type:
                cart_adds += 1
            elif "purchase" in interaction_type:
                purchases += 1

        # Calculate exploration ratio (views per purchase)
        exploration_ratio = (views / purchases) if purchases > 0 else views

        # Quick buyers: low ratio (< 5 views per purchase)
        # Researchers: high ratio (> 20 views per purchase)
        if exploration_ratio < 5:
            browsing_style = "decisive"
        elif exploration_ratio < 20:
            browsing_style = "moderate"
        else:
            browsing_style = "researcher"

        return {
            "browsing_style": browsing_style,
            "exploration_ratio": round(exploration_ratio, 2),
            "unique_products_viewed": len(unique_products_viewed),
        }

    def _compute_device_preference(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compute device preference for label: device:mobile/tablet/desktop

        Based on majority device type used
        """
        device_types = []

        for interaction in interactions:
            metadata = interaction.get("metadata", {})
            device_type = metadata.get("deviceType") or metadata.get("device_type")
            if device_type:
                device_types.append(str(device_type).lower())

        if not device_types:
            return {
                "primary_device": None,
                "device_consistency_score": 0.0,
            }

        # Find most common device
        device_counts = Counter(device_types)
        primary_device = device_counts.most_common(1)[0][0]

        # Device consistency (0-1, higher = more consistent)
        consistency = device_counts[primary_device] / len(device_types)

        return {
            "primary_device": primary_device,
            "device_consistency_score": round(consistency, 3),
        }

    def _get_minimal_features(
        self, customer: Dict[str, Any], shop: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return minimal features when no interaction data exists"""
        from app.shared.helpers import now_utc

        return {
            "shop_id": shop.get("id", ""),
            "customer_id": customer.get("customer_id", ""),
            "engagement_score": 0.0,
            "recency_score": 0.0,
            "conversion_propensity_score": 0.0,
            "total_interaction_count": 0,
            "interaction_type_count": 0,
            "days_since_last_interaction": None,
            "browse_to_cart_rate": None,
            "cart_to_purchase_rate": None,
            "browsing_style": None,
            "exploration_ratio": 0.0,
            "unique_products_viewed": 0,
            "primary_device": None,
            "device_consistency_score": 0.0,
            "last_computed_at": now_utc(),
        }

    def _parse_datetime(self, datetime_str: Any) -> Optional[datetime]:
        """Parse datetime string to datetime object"""
        if not datetime_str:
            return None

        try:
            if isinstance(datetime_str, str):
                return datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
            elif isinstance(datetime_str, datetime):
                return datetime_str
            return None
        except:
            return None
