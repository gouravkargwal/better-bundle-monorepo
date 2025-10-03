"""
Gorse Interaction Transformer - STATE-OF-THE-ART VERSION
Transforms session and search-product features to Gorse labels and feedback

Key improvements:
- Session-based behavioral pattern recognition
- Search-to-product relevance modeling
- Product-pair similarity feedback generation
- Advanced temporal and contextual signals
- Quality-aware interaction filtering
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from app.core.logging import get_logger
from app.shared.helpers import now_utc
import math
import hashlib

logger = get_logger(__name__)


class GorseInteractionTransformer:
    """Transform session and search-product features to Gorse labels and feedback"""

    def __init__(self):
        """Initialize interaction transformer"""
        self.session_feedback_weights = {
            "conversion_session": 0.9,
            "high_engagement_session": 0.6,
            "research_session": 0.4,
            "bounce_session": -0.2,
            "abandoned_cart_session": -0.1,
        }

        self.search_feedback_weights = {
            "search_conversion": 0.8,
            "search_click": 0.5,
            "search_engagement": 0.4,
            "search_relevance": 0.3,
            "search_impression": 0.1,
        }

    # ===== SESSION FEATURE TRANSFORMATION =====

    def transform_session_features_to_labels(self, session_features) -> List[str]:
        """
        Transform session features to actionable labels for user profiling

        Uses optimized session features to create behavioral labels
        """
        labels = []

        try:
            if hasattr(session_features, "__dict__"):
                session_dict = session_features.__dict__
            else:
                session_dict = session_features

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

            # Session Duration Labels
            if session_duration >= 20.0:
                labels.append("session_duration:very_long")
            elif session_duration >= 10.0:
                labels.append("session_duration:long")
            elif session_duration >= 5.0:
                labels.append("session_duration:medium")
            elif session_duration >= 2.0:
                labels.append("session_duration:short")
            else:
                labels.append("session_duration:very_short")

            # Interaction Intensity Labels
            if interaction_intensity >= 0.8:
                labels.append("intensity:very_high")
            elif interaction_intensity >= 0.6:
                labels.append("intensity:high")
            elif interaction_intensity >= 0.4:
                labels.append("intensity:moderate")
            elif interaction_intensity >= 0.2:
                labels.append("intensity:low")
            else:
                labels.append("intensity:minimal")

            # Bounce Behavior
            if bounce_session:
                labels.append("behavior:bouncer")
            else:
                labels.append("behavior:engaged")

            # Conversion Funnel Stage
            labels.append(f"funnel:{conversion_funnel_stage}")

            # Purchase Intent Level
            if purchase_intent_score >= 0.8:
                labels.append("intent:ready_to_buy")
            elif purchase_intent_score >= 0.6:
                labels.append("intent:high_interest")
            elif purchase_intent_score >= 0.4:
                labels.append("intent:considering")
            elif purchase_intent_score >= 0.2:
                labels.append("intent:browsing")
            else:
                labels.append("intent:casual")

            # Session Quality Classification
            session_quality = self._calculate_session_quality(session_dict)
            labels.append(f"session_quality:{session_quality}")

            # Session Type Classification
            session_type = self._classify_session_type(session_dict)
            labels.append(f"session_type:{session_type}")

        except Exception as e:
            logger.error(f"Error transforming session features to labels: {str(e)}")

        return labels[:8]  # Limit to 8 session labels

    def _calculate_session_quality(self, session_dict: Dict[str, Any]) -> str:
        """Calculate overall session quality score"""
        session_duration = float(session_dict.get("session_duration_minutes", 0) or 0)
        interaction_intensity = float(session_dict.get("interaction_intensity", 0) or 0)
        bounce_session = session_dict.get("bounce_session", False)
        purchase_intent_score = float(session_dict.get("purchase_intent_score", 0) or 0)

        # Quality score calculation
        duration_score = min(session_duration / 15.0, 1.0)  # 15+ minutes = max
        intensity_score = interaction_intensity
        bounce_penalty = -0.3 if bounce_session else 0.0
        intent_bonus = purchase_intent_score * 0.2

        quality_score = (
            (duration_score * 0.3)
            + (intensity_score * 0.4)
            + bounce_penalty
            + intent_bonus
        )

        if quality_score >= 0.8:
            return "premium"
        elif quality_score >= 0.6:
            return "high"
        elif quality_score >= 0.4:
            return "good"
        elif quality_score >= 0.2:
            return "fair"
        else:
            return "poor"

    def _classify_session_type(self, session_dict: Dict[str, Any]) -> str:
        """Classify session type based on behavioral patterns"""
        session_duration = float(session_dict.get("session_duration_minutes", 0) or 0)
        interaction_intensity = float(session_dict.get("interaction_intensity", 0) or 0)
        bounce_session = session_dict.get("bounce_session", False)
        conversion_funnel_stage = session_dict.get("conversion_funnel_stage", "unknown")
        purchase_intent_score = float(session_dict.get("purchase_intent_score", 0) or 0)

        # Classification logic
        if conversion_funnel_stage == "purchase":
            return "conversion"
        elif bounce_session:
            return "bounce"
        elif session_duration >= 10 and interaction_intensity <= 0.3:
            return "research"
        elif interaction_intensity >= 0.7 and purchase_intent_score >= 0.6:
            return "high_intent"
        elif session_duration <= 2 and interaction_intensity >= 0.6:
            return "quick_decision"
        elif session_duration >= 5:
            return "exploration"
        else:
            return "casual_browse"

    # ===== SEARCH-PRODUCT FEATURE TRANSFORMATION =====

    def transform_search_product_features_to_labels(self, search_features) -> List[str]:
        """
        Transform search-product features to relevance and quality labels

        Uses optimized search-product features for search optimization
        """
        labels = []

        try:
            if hasattr(search_features, "__dict__"):
                search_dict = search_features.__dict__
            else:
                search_dict = search_features

            # Use optimized search-product features
            search_click_rate = float(search_dict.get("search_click_rate", 0) or 0)
            search_conversion_rate = float(
                search_dict.get("search_conversion_rate", 0) or 0
            )
            search_relevance_score = float(
                search_dict.get("search_relevance_score", 0) or 0
            )
            semantic_match_score = float(
                search_dict.get("semantic_match_score", 0) or 0
            )
            search_intent_alignment = search_dict.get(
                "search_intent_alignment", "no_intent"
            )
            avg_search_position = float(search_dict.get("avg_search_position", 0) or 0)

            # Click Rate Performance
            if search_click_rate >= 0.3:
                labels.append("click_performance:excellent")
            elif search_click_rate >= 0.2:
                labels.append("click_performance:high")
            elif search_click_rate >= 0.1:
                labels.append("click_performance:good")
            elif search_click_rate >= 0.05:
                labels.append("click_performance:fair")
            else:
                labels.append("click_performance:poor")

            # Conversion Performance
            if search_conversion_rate >= 0.15:
                labels.append("search_conversion:excellent")
            elif search_conversion_rate >= 0.10:
                labels.append("search_conversion:high")
            elif search_conversion_rate >= 0.05:
                labels.append("search_conversion:good")
            elif search_conversion_rate >= 0.02:
                labels.append("search_conversion:fair")
            else:
                labels.append("search_conversion:poor")

            # Relevance Quality
            if search_relevance_score >= 0.8:
                labels.append("relevance:highly_relevant")
            elif search_relevance_score >= 0.6:
                labels.append("relevance:relevant")
            elif search_relevance_score >= 0.4:
                labels.append("relevance:moderately_relevant")
            elif search_relevance_score >= 0.2:
                labels.append("relevance:somewhat_relevant")
            else:
                labels.append("relevance:low_relevance")

            # Semantic Match Quality
            if semantic_match_score >= 0.9:
                labels.append("semantic:perfect_match")
            elif semantic_match_score >= 0.7:
                labels.append("semantic:strong_match")
            elif semantic_match_score >= 0.5:
                labels.append("semantic:good_match")
            elif semantic_match_score >= 0.3:
                labels.append("semantic:weak_match")
            else:
                labels.append("semantic:no_match")

            # Search Intent Alignment
            labels.append(f"intent_align:{search_intent_alignment}")

            # Search Position Performance
            if avg_search_position <= 3:
                labels.append("position:top_result")
            elif avg_search_position <= 10:
                labels.append("position:first_page")
            elif avg_search_position <= 20:
                labels.append("position:second_page")
            else:
                labels.append("position:deep_result")

            # Overall Search Quality
            search_quality = self._calculate_search_quality(search_dict)
            labels.append(f"search_quality:{search_quality}")

        except Exception as e:
            logger.error(
                f"Error transforming search-product features to labels: {str(e)}"
            )

        return labels[:8]  # Limit to 8 search labels

    def _calculate_search_quality(self, search_dict: Dict[str, Any]) -> str:
        """Calculate overall search quality score"""
        search_click_rate = float(search_dict.get("search_click_rate", 0) or 0)
        search_conversion_rate = float(
            search_dict.get("search_conversion_rate", 0) or 0
        )
        search_relevance_score = float(
            search_dict.get("search_relevance_score", 0) or 0
        )
        semantic_match_score = float(search_dict.get("semantic_match_score", 0) or 0)

        # Quality calculation
        quality_score = (
            search_click_rate * 0.25
            + search_conversion_rate * 0.35
            + search_relevance_score * 0.25
            + semantic_match_score * 0.15
        )

        if quality_score >= 0.8:
            return "excellent"
        elif quality_score >= 0.6:
            return "high"
        elif quality_score >= 0.4:
            return "good"
        elif quality_score >= 0.2:
            return "fair"
        else:
            return "poor"

    # ===== PRODUCT-PAIR FEATURE TRANSFORMATION =====

    def transform_product_pair_features_to_labels(self, pair_features) -> List[str]:
        """
        Transform product-pair features to similarity and relationship labels

        Uses optimized product-pair features for recommendation enhancement
        """
        labels = []

        try:
            if hasattr(pair_features, "__dict__"):
                pair_dict = pair_features.__dict__
            else:
                pair_dict = pair_features

            # Use optimized product-pair features
            co_purchase_strength = float(pair_dict.get("co_purchase_strength", 0) or 0)
            pair_affinity_score = float(pair_dict.get("pair_affinity_score", 0) or 0)
            cross_sell_potential = float(pair_dict.get("cross_sell_potential", 0) or 0)
            pair_confidence_level = pair_dict.get("pair_confidence_level", "very_low")
            temporal_co_occurrence = float(
                pair_dict.get("temporal_co_occurrence", 0) or 0
            )

            # Co-purchase Strength
            if co_purchase_strength >= 0.8:
                labels.append("co_purchase:very_strong")
            elif co_purchase_strength >= 0.6:
                labels.append("co_purchase:strong")
            elif co_purchase_strength >= 0.4:
                labels.append("co_purchase:moderate")
            elif co_purchase_strength >= 0.2:
                labels.append("co_purchase:weak")
            else:
                labels.append("co_purchase:very_weak")

            # Pair Affinity
            if pair_affinity_score >= 0.8:
                labels.append("affinity:very_high")
            elif pair_affinity_score >= 0.6:
                labels.append("affinity:high")
            elif pair_affinity_score >= 0.4:
                labels.append("affinity:moderate")
            elif pair_affinity_score >= 0.2:
                labels.append("affinity:low")
            else:
                labels.append("affinity:minimal")

            # Cross-sell Potential
            if cross_sell_potential >= 0.7:
                labels.append("cross_sell:high_potential")
            elif cross_sell_potential >= 0.5:
                labels.append("cross_sell:good_potential")
            elif cross_sell_potential >= 0.3:
                labels.append("cross_sell:moderate_potential")
            elif cross_sell_potential >= 0.1:
                labels.append("cross_sell:low_potential")
            else:
                labels.append("cross_sell:no_potential")

            # Confidence Level
            labels.append(f"confidence:{pair_confidence_level}")

            # Temporal Co-occurrence
            if temporal_co_occurrence >= 0.8:
                labels.append("temporal:frequently_together")
            elif temporal_co_occurrence >= 0.6:
                labels.append("temporal:often_together")
            elif temporal_co_occurrence >= 0.4:
                labels.append("temporal:sometimes_together")
            else:
                labels.append("temporal:rarely_together")

            # Overall Relationship Strength
            relationship_strength = self._calculate_relationship_strength(pair_dict)
            labels.append(f"relationship:{relationship_strength}")

        except Exception as e:
            logger.error(
                f"Error transforming product-pair features to labels: {str(e)}"
            )

        return labels[:6]  # Limit to 6 pair labels

    def _calculate_relationship_strength(self, pair_dict: Dict[str, Any]) -> str:
        """Calculate overall product relationship strength"""
        co_purchase_strength = float(pair_dict.get("co_purchase_strength", 0) or 0)
        pair_affinity_score = float(pair_dict.get("pair_affinity_score", 0) or 0)
        cross_sell_potential = float(pair_dict.get("cross_sell_potential", 0) or 0)

        # Confidence level weight
        confidence_weights = {"high": 1.0, "medium": 0.8, "low": 0.6, "very_low": 0.3}
        confidence_level = pair_dict.get("pair_confidence_level", "very_low")
        confidence_weight = confidence_weights.get(confidence_level, 0.3)

        # Relationship strength calculation
        strength_score = (
            co_purchase_strength * 0.4
            + pair_affinity_score * 0.4
            + cross_sell_potential * 0.2
        ) * confidence_weight

        if strength_score >= 0.8:
            return "very_strong"
        elif strength_score >= 0.6:
            return "strong"
        elif strength_score >= 0.4:
            return "moderate"
        elif strength_score >= 0.2:
            return "weak"
        else:
            return "very_weak"

    # ===== ADVANCED FEEDBACK GENERATION =====

    def generate_contextual_feedback(
        self,
        session_features: Optional[Any] = None,
        search_features: Optional[Any] = None,
        pair_features: Optional[Any] = None,
        shop_id: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Generate contextual feedback using session, search, and pair features

        Creates sophisticated feedback that captures contextual relationships
        """
        all_feedback = []

        try:
            # Session-based contextual feedback
            if session_features:
                session_feedback = self._generate_session_contextual_feedback(
                    session_features, shop_id
                )
                all_feedback.extend(session_feedback)

            # Search-based contextual feedback
            if search_features:
                search_feedback = self._generate_search_contextual_feedback(
                    search_features, shop_id
                )
                all_feedback.extend(search_feedback)

            # Pair-based contextual feedback
            if pair_features:
                pair_feedback = self._generate_pair_contextual_feedback(
                    pair_features, shop_id
                )
                all_feedback.extend(pair_feedback)

            return all_feedback

        except Exception as e:
            logger.error(f"Failed to generate contextual feedback: {str(e)}")
            return []

    def _generate_session_contextual_feedback(
        self, session_features, shop_id: str
    ) -> List[Dict[str, Any]]:
        """Generate session-based contextual feedback"""
        feedback_list = []

        try:
            if hasattr(session_features, "__dict__"):
                session_dict = session_features.__dict__
            else:
                session_dict = session_features

            customer_id = session_dict.get("customer_id", "")
            session_products = session_dict.get("session_products", [])

            if not customer_id or not session_products:
                return feedback_list

            # Session quality assessment
            session_quality = self._calculate_session_quality(session_dict)
            session_type = self._classify_session_type(session_dict)

            # Determine feedback type and value
            if session_type == "conversion":
                feedback_type = "conversion_session"
                base_value = 0.9
            elif session_type == "high_intent":
                feedback_type = "high_engagement_session"
                base_value = 0.7
            elif session_type == "research":
                feedback_type = "research_session"
                base_value = 0.4
            elif session_type == "bounce":
                feedback_type = "bounce_session"
                base_value = -0.2
            else:
                feedback_type = "standard_session"
                base_value = 0.3

            # Apply quality modifier
            quality_modifiers = {
                "premium": 1.2,
                "high": 1.1,
                "good": 1.0,
                "fair": 0.8,
                "poor": 0.6,
            }
            quality_modifier = quality_modifiers.get(session_quality, 1.0)
            final_value = base_value * quality_modifier

            # Create feedback for each product in session
            for product_id in session_products[:10]:  # Limit to 10 products per session
                if not product_id:
                    continue

                feedback = {
                    "FeedbackType": feedback_type,
                    "UserId": f"shop_{shop_id}_{customer_id}",
                    "ItemId": f"shop_{shop_id}_{product_id}",
                    "Timestamp": now_utc().isoformat(),
                    "Value": round(final_value, 3),
                    "Comment": f"Session contextual: {session_type} session with {session_quality} quality",
                }
                feedback_list.append(feedback)

            return feedback_list

        except Exception as e:
            logger.error(f"Failed to generate session contextual feedback: {str(e)}")
            return []

    def _generate_search_contextual_feedback(
        self, search_features, shop_id: str
    ) -> List[Dict[str, Any]]:
        """Generate search-based contextual feedback"""
        feedback_list = []

        try:
            if hasattr(search_features, "__dict__"):
                search_dict = search_features.__dict__
            else:
                search_dict = search_features

            search_query = search_dict.get("search_query", "")
            product_id = search_dict.get("product_id", "")

            if not search_query or not product_id:
                return feedback_list

            # Search quality assessment
            search_quality = self._calculate_search_quality(search_dict)
            search_conversion_rate = float(
                search_dict.get("search_conversion_rate", 0) or 0
            )
            search_click_rate = float(search_dict.get("search_click_rate", 0) or 0)

            # Determine feedback type and value
            if search_conversion_rate >= 0.1:
                feedback_type = "search_conversion"
                base_value = 0.8
            elif search_click_rate >= 0.2:
                feedback_type = "search_engagement"
                base_value = 0.5
            else:
                feedback_type = "search_relevance"
                base_value = 0.3

            # Apply quality modifier
            quality_modifiers = {
                "excellent": 1.2,
                "high": 1.1,
                "good": 1.0,
                "fair": 0.8,
                "poor": 0.6,
            }
            quality_modifier = quality_modifiers.get(search_quality, 1.0)
            final_value = base_value * quality_modifier

            # Create search contextual user ID
            search_user_id = f"shop_{shop_id}_search_{hashlib.md5(search_query.encode()).hexdigest()[:8]}"

            feedback = {
                "FeedbackType": feedback_type,
                "UserId": search_user_id,
                "ItemId": f"shop_{shop_id}_{product_id}",
                "Timestamp": now_utc().isoformat(),
                "Value": round(final_value, 3),
                "Comment": f"Search contextual: '{search_query}' -> {product_id} ({search_quality} quality)",
            }
            feedback_list.append(feedback)

            return feedback_list

        except Exception as e:
            logger.error(f"Failed to generate search contextual feedback: {str(e)}")
            return []

    def _generate_pair_contextual_feedback(
        self, pair_features, shop_id: str
    ) -> List[Dict[str, Any]]:
        """Generate product-pair contextual feedback for similarity"""
        feedback_list = []

        try:
            if hasattr(pair_features, "__dict__"):
                pair_dict = pair_features.__dict__
            else:
                pair_dict = pair_features

            product_id1 = pair_dict.get("product_id1", "")
            product_id2 = pair_dict.get("product_id2", "")

            if not product_id1 or not product_id2:
                return feedback_list

            # Relationship strength assessment
            relationship_strength = self._calculate_relationship_strength(pair_dict)
            pair_affinity_score = float(pair_dict.get("pair_affinity_score", 0) or 0)

            # Skip weak relationships
            if relationship_strength in ["very_weak", "weak"]:
                return feedback_list

            # Determine similarity feedback value
            strength_values = {"very_strong": 0.9, "strong": 0.7, "moderate": 0.5}
            similarity_value = strength_values.get(relationship_strength, 0.3)

            # Create bidirectional similarity feedback with contextual users
            similarity_user_1 = f"shop_{shop_id}_{product_id1}_similarity"
            similarity_user_2 = f"shop_{shop_id}_{product_id2}_similarity"

            # Product 1 -> Product 2 similarity
            feedback1 = {
                "FeedbackType": "product_similarity",
                "UserId": similarity_user_1,
                "ItemId": f"shop_{shop_id}_{product_id2}",
                "Timestamp": now_utc().isoformat(),
                "Value": round(similarity_value, 3),
                "Comment": f"Pair contextual: {product_id1} -> {product_id2} ({relationship_strength} relationship)",
            }

            # Product 2 -> Product 1 similarity
            feedback2 = {
                "FeedbackType": "product_similarity",
                "UserId": similarity_user_2,
                "ItemId": f"shop_{shop_id}_{product_id1}",
                "Timestamp": now_utc().isoformat(),
                "Value": round(similarity_value, 3),
                "Comment": f"Pair contextual: {product_id2} -> {product_id1} ({relationship_strength} relationship)",
            }

            feedback_list.extend([feedback1, feedback2])
            return feedback_list

        except Exception as e:
            logger.error(f"Failed to generate pair contextual feedback: {str(e)}")
            return []

    # ===== BATCH TRANSFORMATION METHODS =====

    def transform_session_features_batch_to_labels(
        self, session_features_list: List[Any]
    ) -> List[Dict[str, List[str]]]:
        """Transform batch of session features to labels"""
        all_labels = []

        for session_features in session_features_list:
            try:
                labels = self.transform_session_features_to_labels(session_features)
                if labels:
                    session_id = (
                        getattr(session_features, "session_id", "unknown")
                        if hasattr(session_features, "session_id")
                        else session_features.get("session_id", "unknown")
                    )
                    all_labels.append({"session_id": session_id, "labels": labels})
            except Exception as e:
                logger.error(f"Failed to transform session features: {str(e)}")
                continue

        return all_labels

    def transform_search_product_features_batch_to_labels(
        self, search_features_list: List[Any]
    ) -> List[Dict[str, Any]]:
        """Transform batch of search-product features to labels"""
        all_labels = []

        for search_features in search_features_list:
            try:
                labels = self.transform_search_product_features_to_labels(
                    search_features
                )
                if labels:
                    if hasattr(search_features, "__dict__"):
                        search_dict = search_features.__dict__
                    else:
                        search_dict = search_features

                    all_labels.append(
                        {
                            "search_query": search_dict.get("search_query", ""),
                            "product_id": search_dict.get("product_id", ""),
                            "labels": labels,
                        }
                    )
            except Exception as e:
                logger.error(f"Failed to transform search-product features: {str(e)}")
                continue

        return all_labels

    def transform_product_pair_features_batch_to_labels(
        self, pair_features_list: List[Any]
    ) -> List[Dict[str, Any]]:
        """Transform batch of product-pair features to labels"""
        all_labels = []

        for pair_features in pair_features_list:
            try:
                labels = self.transform_product_pair_features_to_labels(pair_features)
                if labels:
                    if hasattr(pair_features, "__dict__"):
                        pair_dict = pair_features.__dict__
                    else:
                        pair_dict = pair_features

                    all_labels.append(
                        {
                            "product_id1": pair_dict.get("product_id1", ""),
                            "product_id2": pair_dict.get("product_id2", ""),
                            "labels": labels,
                        }
                    )
            except Exception as e:
                logger.error(f"Failed to transform product-pair features: {str(e)}")
                continue

        return all_labels

    # ===== QUALITY CONTROL =====

    def validate_interaction_features_quality(
        self,
        session_labels: List[Dict[str, Any]] = None,
        search_labels: List[Dict[str, Any]] = None,
        pair_labels: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Validate quality of interaction feature transformations"""
        validation_report = {
            "session_validation": {},
            "search_validation": {},
            "pair_validation": {},
            "overall_quality": "unknown",
        }

        # Session validation
        if session_labels:
            validation_report["session_validation"] = {
                "total_sessions": len(session_labels),
                "avg_labels_per_session": sum(
                    len(s.get("labels", [])) for s in session_labels
                )
                / len(session_labels),
                "quality_distribution": self._analyze_session_quality_distribution(
                    session_labels
                ),
            }

        # Search validation
        if search_labels:
            validation_report["search_validation"] = {
                "total_search_products": len(search_labels),
                "avg_labels_per_search": sum(
                    len(s.get("labels", [])) for s in search_labels
                )
                / len(search_labels),
                "relevance_distribution": self._analyze_search_relevance_distribution(
                    search_labels
                ),
            }

        # Pair validation
        if pair_labels:
            validation_report["pair_validation"] = {
                "total_pairs": len(pair_labels),
                "avg_labels_per_pair": sum(
                    len(p.get("labels", [])) for p in pair_labels
                )
                / len(pair_labels),
                "relationship_distribution": self._analyze_pair_relationship_distribution(
                    pair_labels
                ),
            }

        # Overall quality assessment
        total_features = (
            len(session_labels or [])
            + len(search_labels or [])
            + len(pair_labels or [])
        )
        if total_features >= 1000:
            validation_report["overall_quality"] = "comprehensive"
        elif total_features >= 500:
            validation_report["overall_quality"] = "good"
        elif total_features >= 100:
            validation_report["overall_quality"] = "adequate"
        else:
            validation_report["overall_quality"] = "limited"

        return validation_report

    def _analyze_session_quality_distribution(
        self, session_labels: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Analyze session quality distribution"""
        quality_counts = {"premium": 0, "high": 0, "good": 0, "fair": 0, "poor": 0}

        for session in session_labels:
            labels = session.get("labels", [])
            for label in labels:
                if label.startswith("session_quality:"):
                    quality = label.split(":")[1]
                    if quality in quality_counts:
                        quality_counts[quality] += 1

        return quality_counts

    def _analyze_search_relevance_distribution(
        self, search_labels: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Analyze search relevance distribution"""
        relevance_counts = {
            "highly_relevant": 0,
            "relevant": 0,
            "moderately_relevant": 0,
            "somewhat_relevant": 0,
            "low_relevance": 0,
        }

        for search in search_labels:
            labels = search.get("labels", [])
            for label in labels:
                if label.startswith("relevance:"):
                    relevance = label.split(":")[1]
                    if relevance in relevance_counts:
                        relevance_counts[relevance] += 1

        return relevance_counts

    def _analyze_pair_relationship_distribution(
        self, pair_labels: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Analyze pair relationship distribution"""
        relationship_counts = {
            "very_strong": 0,
            "strong": 0,
            "moderate": 0,
            "weak": 0,
            "very_weak": 0,
        }

        for pair in pair_labels:
            labels = pair.get("labels", [])
            for label in labels:
                if label.startswith("relationship:"):
                    relationship = label.split(":")[1]
                    if relationship in relationship_counts:
                        relationship_counts[relationship] += 1

        return relationship_counts
