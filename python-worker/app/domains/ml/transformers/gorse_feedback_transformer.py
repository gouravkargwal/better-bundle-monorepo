from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from app.core.logging import get_logger
from app.shared.helpers.datetime_utils import now_utc, parse_iso_timestamp
import math

logger = get_logger(__name__)


class GorseFeedbackTransformer:
    """Transform interactions to Gorse feedback format with state-of-the-art weighting"""

    def __init__(self):
        """Initialize feedback transformer"""
        # Configure feedback types and their confidence weights based on research
        self.feedback_weights = {
            # Explicit feedback (highest confidence)
            "purchase": 1.0,
            "high_value_purchase": 1.2,  # Premium purchases get bonus
            "refund": -0.8,
            # High-intent implicit feedback
            "checkout_completed": 0.9,
            "checkout_started": 0.7,
            "product_added_to_cart": 0.6,
            "ready_to_buy": 0.8,  # From optimized features
            # Medium-intent implicit feedback
            "product_viewed": 0.3,
            "search_clicked": 0.4,
            "recommendation_clicked": 0.5,
            "strong_affinity": 0.65,  # From optimized features
            "progressing_interest": 0.55,  # From optimized features
            # Low-intent implicit feedback
            "product_impression": 0.1,
            "search_impression": 0.05,
            "basic_interest": 0.25,  # From optimized features
            # Negative signals
            "product_removed_from_cart": -0.2,
            "bounce": -0.1,
            "session_bounce": -0.15,
            # Session-based feedback
            "high_engagement_session": 0.4,
            "conversion_session": 0.8,
            "research_session": 0.3,
            # Search-product feedback
            "search_conversion": 0.75,
            "search_engagement": 0.45,
            "search_relevance": 0.35,
        }

    def transform_order_to_feedback(self, order, shop_id: str) -> List[Dict[str, Any]]:
        """
        Transform order to Gorse feedback with advanced weighting strategies

        Creates weighted feedback based on purchase value, customer quality, and temporal factors
        """
        try:
            feedback_list = []

            if hasattr(order, "__dict__"):
                order_dict = order.__dict__
            else:
                order_dict = order

            customer_id = order_dict.get("customer_id", "")
            order_date = order_dict.get("order_date", now_utc())
            line_items = order_dict.get("line_items", [])
            financial_status = order_dict.get("financial_status", "")
            total_amount = float(order_dict.get("total_amount", 0.0))
            total_refunded = float(order_dict.get("total_refunded_amount", 0.0))

            if not customer_id:
                return feedback_list

            # Calculate order-level confidence factors
            order_confidence = self._calculate_order_confidence(order_dict)
            temporal_decay = self._calculate_temporal_decay(order_date)

            for item in line_items:
                if isinstance(item, dict):
                    product_id = item.get("product_id", "")
                    quantity = item.get("quantity", 1)
                    line_total = float(item.get("line_total", 0.0))
                else:
                    product_id = getattr(item, "product_id", "")
                    quantity = getattr(item, "quantity", 1)
                    line_total = float(getattr(item, "line_total", 0.0))

                if not product_id:
                    continue

                # Calculate item-level confidence
                item_confidence = self._calculate_item_confidence(
                    line_total, total_amount, quantity
                )

                # Combine all confidence factors
                final_confidence = order_confidence * temporal_decay * item_confidence

                timestamp = (
                    order_date.isoformat()
                    if hasattr(order_date, "isoformat")
                    else str(order_date)
                )

                if financial_status == "refunded" and total_refunded > 0:
                    # Negative feedback for refunds (weighted by refund amount)
                    refund_weight = self._calculate_refund_weight(
                        line_total, total_refunded
                    )

                    feedback = {
                        "FeedbackType": "refund",
                        "UserId": f"shop_{shop_id}_{customer_id}",
                        "ItemId": f"shop_{shop_id}_{product_id}",
                        "Timestamp": timestamp,
                        "Value": -refund_weight,  # Negative feedback weighted by amount
                        "Comment": f"Refunded: ${line_total:.2f} (weight: {refund_weight:.2f})",
                    }
                else:
                    # Determine purchase feedback type based on value
                    if line_total >= 200:
                        feedback_type = "high_value_purchase"
                    else:
                        feedback_type = "purchase"

                    # Scale feedback value by confidence (0.1 to 1.0+ range)
                    scaled_value = max(
                        0.1, final_confidence * self.feedback_weights[feedback_type]
                    )

                    feedback = {
                        "FeedbackType": feedback_type,
                        "UserId": f"shop_{shop_id}_{customer_id}",
                        "ItemId": f"shop_{shop_id}_{product_id}",
                        "Timestamp": timestamp,
                        "Value": round(scaled_value, 3),
                        "Comment": f"Purchase: {quantity}x ${line_total:.2f} (conf: {final_confidence:.2f})",
                    }

                feedback_list.append(feedback)

            return feedback_list

        except Exception as e:
            logger.error(f"Failed to transform order to feedback: {str(e)}")
            return []

    def transform_optimized_interaction_features_to_feedback(
        self, interaction_features, shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Transform ALL optimized interaction features to ultra-high-quality Gorse feedback

        Uses ALL 10 optimized interaction features for maximum signal quality
        """
        try:
            if hasattr(interaction_features, "__dict__"):
                features_dict = interaction_features.__dict__
            else:
                features_dict = interaction_features

            customer_id = features_dict.get("customer_id", "")
            product_id = features_dict.get("product_id", "")

            if not customer_id or not product_id:
                return None

            # === USE ALL 10 OPTIMIZED INTERACTION FEATURES ===

            interaction_strength = float(
                features_dict.get("interaction_strength_score", 0) or 0
            )
            customer_product_affinity = float(
                features_dict.get("customer_product_affinity", 0) or 0
            )
            engagement_progression = float(
                features_dict.get("engagement_progression_score", 0) or 0
            )
            conversion_likelihood = float(
                features_dict.get("conversion_likelihood", 0) or 0
            )
            purchase_intent = float(features_dict.get("purchase_intent_score", 0) or 0)
            interaction_recency = float(
                features_dict.get("interaction_recency_score", 0) or 0
            )
            relationship_maturity = features_dict.get(
                "relationship_maturity", "no_relationship"
            )
            interaction_frequency = float(
                features_dict.get("interaction_frequency_score", 0) or 0
            )
            customer_loyalty = float(
                features_dict.get("customer_product_loyalty", 0) or 0
            )
            interaction_value = float(
                features_dict.get("total_interaction_value", 0) or 0
            )

            # Skip very weak relationships
            if interaction_strength < 0.05 and customer_product_affinity < 0.05:
                return None

            # Calculate comprehensive feedback value using ALL 10 features
            base_value = (
                interaction_strength * 0.20  # Core interaction strength
                + customer_product_affinity * 0.20  # Customer-product affinity
                + engagement_progression * 0.15  # Funnel progression quality
                + conversion_likelihood * 0.15  # Conversion potential
                + purchase_intent * 0.10  # Purchase intent signals
                + interaction_recency * 0.10  # Temporal relevance
                + interaction_frequency * 0.05  # Interaction quality
                + customer_loyalty * 0.05  # Loyalty bonus
            )

            # Apply relationship maturity boost
            maturity_boosts = {
                "loyal_customer": 0.3,
                "returning_customer": 0.2,
                "engaged_browser": 0.1,
                "new_interest": 0.05,
                "no_relationship": 0.0,
            }
            maturity_boost = maturity_boosts.get(relationship_maturity, 0.0)

            # Apply commercial value factor
            if interaction_value > 0:
                value_factor = min(math.log10(interaction_value + 1) / 3.0, 0.2)
            else:
                value_factor = 0

            # Final comprehensive feedback value
            final_value = base_value + maturity_boost + value_factor
            final_value = max(0.1, min(final_value, 1.2))  # Clamp to reasonable range

            # Determine sophisticated feedback type based on ALL features
            if interaction_value > 100:
                feedback_type = "high_value_purchase"
            elif conversion_likelihood >= 0.8 and purchase_intent >= 0.7:
                feedback_type = "ready_to_buy"
            elif customer_product_affinity >= 0.7:
                feedback_type = "strong_affinity"
            elif engagement_progression >= 0.6:
                feedback_type = "progressing_interest"
            else:
                feedback_type = "basic_interest"

            feedback = {
                "FeedbackType": feedback_type,
                "UserId": f"shop_{shop_id}_{customer_id}",
                "ItemId": f"shop_{shop_id}_{product_id}",
                "Timestamp": now_utc().isoformat(),
                "Value": round(final_value, 3),
                "Comment": f"Comprehensive feedback using all 10 optimized features (strength: {interaction_strength:.2f}, affinity: {customer_product_affinity:.2f}, value: {final_value:.3f})",
            }

            return feedback

        except Exception as e:
            logger.error(
                f"Failed to transform optimized interaction features: {str(e)}"
            )
            return None

    def transform_session_features_to_feedback(
        self, session_features, shop_id: str
    ) -> List[Dict[str, Any]]:
        """
        Transform optimized session features to session-based feedback

        Creates feedback based on session quality and behavior patterns
        """
        feedback_list = []

        try:
            if hasattr(session_features, "__dict__"):
                session_dict = session_features.__dict__
            else:
                session_dict = session_features

            customer_id = session_dict.get("customer_id", "")
            session_id = session_dict.get("session_id", "")

            if not customer_id or not session_id:
                return feedback_list

            # Use optimized session features
            session_duration = float(
                session_dict.get("session_duration_minutes", 0) or 0
            )
            interaction_intensity = float(
                session_dict.get("interaction_intensity", 0) or 0
            )
            bounce_session = session_dict.get("bounce_session", False)
            conversion_funnel_stage = session_dict.get(
                "conversion_funnel_stage", "unknown"
            )
            purchase_intent_score = float(
                session_dict.get("purchase_intent_score", 0) or 0
            )

            # Get products from session (if available)
            session_products = session_dict.get("session_products", [])

            # Determine session feedback type
            if conversion_funnel_stage == "purchase":
                session_feedback_type = "conversion_session"
                session_value = 0.8
            elif bounce_session:
                session_feedback_type = "session_bounce"
                session_value = -0.15
            elif interaction_intensity >= 0.7:
                session_feedback_type = "high_engagement_session"
                session_value = 0.4
            elif session_duration >= 5.0:  # 5+ minutes
                session_feedback_type = "research_session"
                session_value = 0.3
            else:
                return feedback_list  # Skip low-quality sessions

            # Apply temporal decay
            session_timestamp = session_dict.get("session_start_time", now_utc())
            temporal_decay = self._calculate_temporal_decay(session_timestamp)
            final_session_value = session_value * temporal_decay

            # Create feedback for each product in session
            for product_id in session_products:
                if not product_id:
                    continue

                feedback = {
                    "FeedbackType": session_feedback_type,
                    "UserId": f"shop_{shop_id}_{customer_id}",
                    "ItemId": f"shop_{shop_id}_{product_id}",
                    "Timestamp": (
                        session_timestamp.isoformat()
                        if hasattr(session_timestamp, "isoformat")
                        else str(session_timestamp)
                    ),
                    "Value": round(final_session_value, 3),
                    "Comment": f"Session feedback: {session_feedback_type} (duration: {session_duration:.1f}min, intensity: {interaction_intensity:.2f})",
                }
                feedback_list.append(feedback)

            return feedback_list

        except Exception as e:
            logger.error(f"Failed to transform session features: {str(e)}")
            return []

    def transform_search_product_features_to_feedback(
        self, search_features, shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Transform optimized search-product features to search-based feedback

        Creates feedback based on search relevance and conversion patterns
        """
        try:
            if hasattr(search_features, "__dict__"):
                search_dict = search_features.__dict__
            else:
                search_dict = search_features

            search_query = search_dict.get("search_query", "")
            product_id = search_dict.get("product_id", "")
            # Note: For search feedback, we'll use search query as "user" for search-to-product recommendations

            if not search_query or not product_id:
                return None

            # Use optimized search-product features
            search_click_rate = float(search_dict.get("search_click_rate", 0) or 0)
            search_conversion_rate = float(
                search_dict.get("search_conversion_rate", 0) or 0
            )
            search_relevance_score = float(
                search_dict.get("search_relevance_score", 0) or 0
            )
            total_search_interactions = int(
                search_dict.get("total_search_interactions", 0) or 0
            )
            search_to_purchase_count = int(
                search_dict.get("search_to_purchase_count", 0) or 0
            )
            semantic_match_score = float(
                search_dict.get("semantic_match_score", 0) or 0
            )
            search_intent_alignment = search_dict.get(
                "search_intent_alignment", "no_intent"
            )

            # Skip very weak search-product relationships
            if search_relevance_score < 0.1 and search_click_rate < 0.05:
                return None

            # Determine search feedback type and value
            if search_to_purchase_count >= 2:  # Multiple conversions
                feedback_type = "search_conversion"
                base_value = 0.75
            elif search_conversion_rate >= 0.3:  # High conversion rate
                feedback_type = "search_conversion"
                base_value = 0.75 * search_conversion_rate
            elif search_click_rate >= 0.2:  # Good engagement
                feedback_type = "search_engagement"
                base_value = 0.45 * search_click_rate
            elif search_relevance_score >= 0.5:  # Good relevance
                feedback_type = "search_relevance"
                base_value = 0.35 * search_relevance_score
            else:
                return None  # Skip low-quality search relationships

            # Apply semantic match bonus
            semantic_bonus = semantic_match_score * 0.1

            # Apply intent alignment bonus
            intent_bonuses = {
                "high_intent": 0.15,
                "medium_intent": 0.10,
                "browsing_intent": 0.05,
                "low_intent": 0.02,
                "no_intent": 0.0,
            }
            intent_bonus = intent_bonuses.get(search_intent_alignment, 0.0)

            # Calculate final feedback value
            final_value = base_value + semantic_bonus + intent_bonus
            final_value = max(0.05, min(final_value, 1.0))

            # Apply temporal decay based on recency
            search_timestamp = search_dict.get("last_computed_at", now_utc())
            temporal_decay = self._calculate_temporal_decay(search_timestamp)
            final_value *= temporal_decay

            feedback = {
                "FeedbackType": feedback_type,
                "UserId": f"shop_{shop_id}_search_{hash(search_query) % 10000}",  # Hash search query for user ID
                "ItemId": f"shop_{shop_id}_{product_id}",
                "Timestamp": (
                    search_timestamp.isoformat()
                    if hasattr(search_timestamp, "isoformat")
                    else str(search_timestamp)
                ),
                "Value": round(final_value, 3),
                "Comment": f"Search feedback: '{search_query}' -> {product_id} (relevance: {search_relevance_score:.2f}, intent: {search_intent_alignment})",
            }

            return feedback

        except Exception as e:
            logger.error(f"Failed to transform search-product features: {str(e)}")
            return None

    def transform_product_pair_features_to_similarity_feedback(
        self, pair_features, shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Transform product-pair features to similarity feedback for related products

        Creates "similar_to" feedback based on co-purchase and affinity patterns
        """
        try:
            if hasattr(pair_features, "__dict__"):
                pair_dict = pair_features.__dict__
            else:
                pair_dict = pair_features

            product_id1 = pair_dict.get("product_id1", "")
            product_id2 = pair_dict.get("product_id2", "")

            if not product_id1 or not product_id2:
                return None

            # Use optimized product-pair features
            co_purchase_strength = float(pair_dict.get("co_purchase_strength", 0) or 0)
            pair_affinity_score = float(pair_dict.get("pair_affinity_score", 0) or 0)
            cross_sell_potential = float(pair_dict.get("cross_sell_potential", 0) or 0)
            pair_confidence_level = pair_dict.get("pair_confidence_level", "very_low")

            # Skip weak product relationships
            if pair_affinity_score < 0.3 or pair_confidence_level == "very_low":
                return None

            # Calculate similarity feedback value
            confidence_multipliers = {
                "high": 1.0,
                "medium": 0.8,
                "low": 0.6,
                "very_low": 0.3,
            }
            confidence_mult = confidence_multipliers.get(pair_confidence_level, 0.3)

            similarity_value = (
                co_purchase_strength * 0.4
                + pair_affinity_score * 0.4
                + cross_sell_potential * 0.2
            ) * confidence_mult

            similarity_value = max(0.1, min(similarity_value, 1.0))

            # Create bidirectional similarity feedback
            feedback_list = []

            # Product 1 -> Product 2 similarity
            feedback1 = {
                "FeedbackType": "similar_to",
                "UserId": f"shop_{shop_id}_{product_id1}_similarity",
                "ItemId": f"shop_{shop_id}_{product_id2}",
                "Timestamp": now_utc().isoformat(),
                "Value": round(similarity_value, 3),
                "Comment": f"Product similarity: {product_id1} -> {product_id2} (affinity: {pair_affinity_score:.2f}, confidence: {pair_confidence_level})",
            }

            # Product 2 -> Product 1 similarity
            feedback2 = {
                "FeedbackType": "similar_to",
                "UserId": f"shop_{shop_id}_{product_id2}_similarity",
                "ItemId": f"shop_{shop_id}_{product_id1}",
                "Timestamp": now_utc().isoformat(),
                "Value": round(similarity_value, 3),
                "Comment": f"Product similarity: {product_id2} -> {product_id1} (affinity: {pair_affinity_score:.2f}, confidence: {pair_confidence_level})",
            }

            return [feedback1, feedback2]

        except Exception as e:
            logger.error(f"Failed to transform product-pair features: {str(e)}")
            return None

    # ===== CONFIDENCE CALCULATION METHODS =====

    def _calculate_order_confidence(self, order_dict: Dict[str, Any]) -> float:
        """Calculate order-level confidence based on order characteristics"""
        confidence_factors = []

        # Order value factor (higher value = higher confidence)
        total_amount = float(order_dict.get("total_amount", 0.0))
        value_confidence = min(total_amount / 200.0, 1.0)  # $200+ = max confidence
        confidence_factors.append(value_confidence)

        # Payment method confidence
        payment_gateway = order_dict.get("payment_gateway_names", [""])
        if any(
            "stripe" in str(pg).lower() or "paypal" in str(pg).lower()
            for pg in payment_gateway
        ):
            payment_confidence = 1.0  # Trusted payment methods
        else:
            payment_confidence = 0.8
        confidence_factors.append(payment_confidence)

        # Processing status confidence
        fulfillment_status = order_dict.get("fulfillment_status", "")
        if fulfillment_status == "fulfilled":
            fulfillment_confidence = 1.0
        elif fulfillment_status == "partial":
            fulfillment_confidence = 0.8
        else:
            fulfillment_confidence = 0.6
        confidence_factors.append(fulfillment_confidence)

        # Return average confidence
        return sum(confidence_factors) / len(confidence_factors)

    def _calculate_item_confidence(
        self, line_total: float, order_total: float, quantity: int
    ) -> float:
        """Calculate item-level confidence within order"""
        # Item value proportion (items that make up more of the order = higher confidence)
        value_proportion = line_total / max(order_total, 1.0)
        proportion_confidence = min(
            value_proportion * 2.0, 1.0
        )  # 50%+ of order = max confidence

        # Quantity confidence (multiple items = higher confidence)
        quantity_confidence = min(quantity / 3.0, 1.0)  # 3+ items = max confidence

        # Combine factors
        item_confidence = (proportion_confidence * 0.7) + (quantity_confidence * 0.3)
        return max(0.1, item_confidence)  # Minimum 0.1 confidence

    def _calculate_temporal_decay(self, timestamp: Any) -> float:
        """Calculate temporal decay factor - recent interactions are more relevant"""
        if not timestamp:
            return 0.5  # Default for missing timestamps

        try:
            if isinstance(timestamp, str):
                event_time = parse_iso_timestamp(timestamp)
            elif isinstance(timestamp, datetime):
                event_time = timestamp
            else:
                return 0.5
        except:
            return 0.5

        # Calculate days since interaction
        days_ago = (now_utc() - event_time).days

        # Exponential decay: 1.0 for today, 0.5 for 30 days ago, 0.1 for 90 days ago
        decay_factor = math.exp(-days_ago / 60.0)  # 60-day half-life
        return max(0.05, min(decay_factor, 1.0))  # Clamp between 0.05 and 1.0

    def _calculate_refund_weight(
        self, line_total: float, total_refunded: float
    ) -> float:
        """Calculate negative weight for refunded items"""
        if total_refunded <= 0:
            return 0.0

        # Proportion of this item that was refunded
        refund_proportion = min(line_total / max(total_refunded, 1.0), 1.0)

        # Higher refund amounts get stronger negative signals
        refund_weight = 0.8 * refund_proportion
        return min(refund_weight, 0.9)  # Cap negative weight

    # ===== BATCH TRANSFORMATION METHODS =====

    def transform_batch_orders_to_feedback(
        self, orders_list: List[Any], shop_id: str
    ) -> List[Dict[str, Any]]:
        """Transform multiple orders to Gorse feedback objects with batching optimization"""
        all_feedback = []

        for order in orders_list:
            feedback_list = self.transform_order_to_feedback(order, shop_id)
            all_feedback.extend(feedback_list)

        # Sort by timestamp for better Gorse ingestion
        all_feedback.sort(key=lambda x: x.get("Timestamp", ""))

        return all_feedback

    def transform_optimized_features_batch_to_feedback(
        self, interaction_features_list: List[Any], shop_id: str
    ) -> List[Dict[str, Any]]:
        """Transform batch of ALL optimized interaction features to ultra-high-quality feedback"""
        feedback_list = []

        for interaction_features in interaction_features_list:
            feedback = self.transform_optimized_interaction_features_to_feedback(
                interaction_features, shop_id
            )
            if feedback:
                feedback_list.append(feedback)

        # Sort by feedback value (highest quality first)
        feedback_list.sort(key=lambda x: x.get("Value", 0), reverse=True)

        return feedback_list

    def transform_session_features_batch_to_feedback(
        self, session_features_list: List[Any], shop_id: str
    ) -> List[Dict[str, Any]]:
        """Transform batch of session features to session-based feedback"""
        all_feedback = []

        for session_features in session_features_list:
            feedback_list = self.transform_session_features_to_feedback(
                session_features, shop_id
            )
            all_feedback.extend(feedback_list)

        return all_feedback

    def transform_search_features_batch_to_feedback(
        self, search_features_list: List[Any], shop_id: str
    ) -> List[Dict[str, Any]]:
        """Transform batch of search-product features to search-based feedback"""
        feedback_list = []

        for search_features in search_features_list:
            feedback = self.transform_search_product_features_to_feedback(
                search_features, shop_id
            )
            if feedback:
                feedback_list.append(feedback)

        return feedback_list

    def transform_product_pair_batch_to_similarity_feedback(
        self, pair_features_list: List[Any], shop_id: str
    ) -> List[Dict[str, Any]]:
        """Transform batch of product-pair features to similarity feedback"""
        all_feedback = []

        for pair_features in pair_features_list:
            feedback = self.transform_product_pair_features_to_similarity_feedback(
                pair_features, shop_id
            )
            if feedback:
                if isinstance(feedback, list):
                    all_feedback.extend(feedback)
                else:
                    all_feedback.append(feedback)

        return all_feedback

    # ===== COMPREHENSIVE FEEDBACK GENERATION =====

    def generate_comprehensive_feedback(
        self,
        orders: List[Any] = None,
        interaction_features: List[Any] = None,
        session_features: List[Any] = None,
        search_features: List[Any] = None,
        pair_features: List[Any] = None,
        shop_id: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Generate comprehensive feedback using ALL available optimized features

        This is the main method that combines all feedback types for maximum Gorse performance
        """
        all_feedback = []

        try:
            # 1. Order-based feedback (explicit signals)
            if orders:
                order_feedback = self.transform_batch_orders_to_feedback(
                    orders, shop_id
                )
                all_feedback.extend(order_feedback)

            # 2. Interaction-based feedback (implicit signals using ALL 10 optimized features)
            if interaction_features:
                interaction_feedback = (
                    self.transform_optimized_features_batch_to_feedback(
                        interaction_features, shop_id
                    )
                )
                all_feedback.extend(interaction_feedback)

            # 3. Session-based feedback (behavioral patterns)
            if session_features:
                session_feedback = self.transform_session_features_batch_to_feedback(
                    session_features, shop_id
                )
                all_feedback.extend(session_feedback)

            # 4. Search-based feedback (search-to-product relevance)
            if search_features:
                search_feedback = self.transform_search_features_batch_to_feedback(
                    search_features, shop_id
                )
                all_feedback.extend(search_feedback)

            # 5. Product similarity feedback (item-to-item relationships)
            if pair_features:
                similarity_feedback = (
                    self.transform_product_pair_batch_to_similarity_feedback(
                        pair_features, shop_id
                    )
                )
                all_feedback.extend(similarity_feedback)

            # Sort and deduplicate
            all_feedback = self.deduplicate_feedback(all_feedback)
            all_feedback.sort(key=lambda x: x.get("Timestamp", ""))

            # Filter high quality feedback
            high_quality_feedback = self.filter_high_quality_feedback(
                all_feedback, min_confidence=0.1
            )

            return high_quality_feedback

        except Exception as e:
            logger.error(f"Failed to generate comprehensive feedback: {str(e)}")
            return []

    # ===== QUALITY CONTROL METHODS =====

    def filter_high_quality_feedback(
        self, feedback_list: List[Dict[str, Any]], min_confidence: float = 0.1
    ) -> List[Dict[str, Any]]:
        """Filter feedback to only include high-quality signals"""
        return [
            feedback
            for feedback in feedback_list
            if abs(feedback.get("Value", 0)) >= min_confidence
        ]

    def deduplicate_feedback(
        self, feedback_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate feedback entries, keeping the highest value"""
        feedback_map = {}

        for feedback in feedback_list:
            key = (
                feedback.get("UserId"),
                feedback.get("ItemId"),
                feedback.get("FeedbackType"),
            )

            if key not in feedback_map or abs(feedback.get("Value", 0)) > abs(
                feedback_map[key].get("Value", 0)
            ):
                feedback_map[key] = feedback

        return list(feedback_map.values())

    def validate_feedback_distribution(
        self, feedback_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate feedback distribution and provide insights"""
        if not feedback_list:
            return {"status": "empty", "insights": []}

        # Analyze feedback types
        type_distribution = {}
        value_distribution = {"positive": 0, "negative": 0, "neutral": 0}

        for feedback in feedback_list:
            feedback_type = feedback.get("FeedbackType", "unknown")
            value = feedback.get("Value", 0)

            type_distribution[feedback_type] = (
                type_distribution.get(feedback_type, 0) + 1
            )

            if value > 0.1:
                value_distribution["positive"] += 1
            elif value < -0.1:
                value_distribution["negative"] += 1
            else:
                value_distribution["neutral"] += 1

        insights = []
        total_feedback = len(feedback_list)

        # Generate insights
        if value_distribution["positive"] / total_feedback > 0.9:
            insights.append("High positive feedback ratio - good user engagement")

        if value_distribution["negative"] / total_feedback > 0.1:
            insights.append(
                "Significant negative feedback - review product/service quality"
            )

        if len(type_distribution) > 10:
            insights.append(
                "High feedback type diversity - comprehensive user behavior capture"
            )

        return {
            "status": "analyzed",
            "total_feedback": total_feedback,
            "type_distribution": type_distribution,
            "value_distribution": value_distribution,
            "insights": insights,
        }
