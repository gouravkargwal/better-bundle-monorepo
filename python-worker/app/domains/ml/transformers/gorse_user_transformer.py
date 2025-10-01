"""
Gorse User Transformer - OPTIMIZED VERSION
Transforms user features to Gorse user objects with research-backed categorical labels

Key improvements:
- RFM segmentation (industry standard)
- Behavioral patterns (shopping style, intent)
- Conversion propensity
- Better actionable segments
"""

from typing import Dict, Any, List, Optional
from app.core.logging import get_logger

logger = get_logger(__name__)


class GorseUserTransformer:
    """Transform user features to Gorse user format with optimized labels"""

    def __init__(self):
        """Initialize user transformer"""
        pass

    def transform_to_gorse_user(
        self, user_features, shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Transform user features to Gorse user object with optimized labels

        Args:
            user_features: UserFeatures model or dict from database
            shop_id: Shop ID

        Returns:
            Gorse user object: {"UserId": "...", "Labels": [...]}
        """
        try:
            if hasattr(user_features, "__dict__"):
                user_dict = user_features.__dict__
            else:
                user_dict = user_features

            customer_id = user_dict.get("customer_id", "")
            if not customer_id:
                logger.warning("No customer_id found in user features")
                return None

            # Convert numeric features to optimized categorical labels
            labels = self._convert_to_optimized_labels(user_dict)

            user_object = {
                "UserId": f"shop_{shop_id}_{customer_id}",
                "Labels": labels,
                "Comment": f"Customer: {customer_id}",
            }

            logger.debug(
                f"Transformed user {customer_id} with {len(labels)} optimized labels"
            )

            return user_object

        except Exception as e:
            logger.error(f"Failed to transform user features: {str(e)}")
            return None

    def transform_batch_to_gorse_users(
        self, user_features_list: List[Any], shop_id: str
    ) -> List[Dict[str, Any]]:
        """Transform multiple user features to Gorse user objects"""
        gorse_users = []

        for user_features in user_features_list:
            gorse_user = self.transform_to_gorse_user(user_features, shop_id)
            if gorse_user:
                gorse_users.append(gorse_user)

        logger.info(f"Transformed {len(gorse_users)} users for shop {shop_id}")
        return gorse_users

    def _convert_to_optimized_labels(self, user_dict: Dict[str, Any]) -> List[str]:
        """
        Convert numeric user features to optimized categorical labels

        Based on e-commerce recommendation research and Gorse best practices
        Max 15 labels for optimal performance

        Args:
            user_dict: User features dictionary from database

        Returns:
            List of optimized categorical labels (max 15)
        """
        labels = []

        try:
            # 1. RFM SEGMENT (Most important - industry standard)
            rfm_segment = self._calculate_rfm_segment(
                days_since_last=user_dict.get("days_since_last_order"),
                frequency=user_dict.get("order_frequency_per_month"),
                monetary=user_dict.get("lifetime_value"),
            )
            labels.append(f"rfm:{rfm_segment}")

            # 2. PURCHASE INTENT (More actionable than raw recency)
            purchase_intent = self._calculate_purchase_intent(user_dict)
            labels.append(f"intent:{purchase_intent}")

            # 3. PREFERRED CATEGORY (Essential for content filtering)
            category = user_dict.get("preferred_category")
            if category and category != "unknown":
                clean_category = str(category).lower().replace(" ", "_")[:30]
                labels.append(f"category:{clean_category}")

            # 4. PREFERRED VENDOR (Good for brand affinity)
            vendor = user_dict.get("preferred_vendor")
            if vendor and vendor != "unknown":
                clean_vendor = str(vendor).lower().replace(" ", "_")[:30]
                labels.append(f"vendor:{clean_vendor}")

            # 5. PRICE SENSITIVITY (Better than simple price tier)
            price_sensitivity = self._calculate_price_sensitivity(
                avg_price=user_dict.get("avg_order_value"),
                discount_sens=user_dict.get("discount_sensitivity"),
            )
            labels.append(f"price_sens:{price_sensitivity}")

            # 6. BASKET SIZE PREFERENCE (Important for bundle recommendations)
            total_purchases = user_dict.get("total_purchases", 0) or 0
            distinct_products = user_dict.get("distinct_products_purchased", 0) or 0

            if total_purchases > 0:
                avg_items_per_order = distinct_products / total_purchases
                if avg_items_per_order >= 5:
                    labels.append("basket:large")
                elif avg_items_per_order >= 2:
                    labels.append("basket:medium")
                else:
                    labels.append("basket:single")
            else:
                labels.append("basket:new")

            # 7. SHOPPING STYLE (Behavioral pattern)
            shopping_style = self._calculate_shopping_style(
                browse_to_cart=user_dict.get("browse_to_cart_rate"),
                cart_to_purchase=user_dict.get("cart_to_purchase_rate"),
                avg_session_duration=user_dict.get("avg_session_duration"),
            )
            labels.append(f"style:{shopping_style}")

            # 8. PRODUCT EXPLORER vs REPEATER (Better than raw diversity)
            repeat_rate = self._calculate_repeat_purchase_rate(user_dict)
            if repeat_rate >= 0.7:
                labels.append("behavior:repeater")
            elif repeat_rate <= 0.3:
                labels.append("behavior:explorer")
            else:
                labels.append("behavior:mixed")

            # 9. TIME PREFERENCE (If temporal data available)
            most_active_hour = user_dict.get("most_active_hour")
            if most_active_hour is not None:
                if 6 <= most_active_hour < 12:
                    labels.append("time:morning")
                elif 12 <= most_active_hour < 17:
                    labels.append("time:afternoon")
                elif 17 <= most_active_hour < 21:
                    labels.append("time:evening")
                else:
                    labels.append("time:night")

            # 10. DEVICE PREFERENCE (Mobile vs desktop experiences)
            device = user_dict.get("device_type", "").lower()
            if device in ["mobile", "phone", "smartphone"]:
                labels.append("device:mobile")
            elif device == "tablet":
                labels.append("device:tablet")
            elif device in ["desktop", "computer", "pc"]:
                labels.append("device:desktop")

            # 11. RISK PROFILE (Combined risk assessment)
            risk_profile = self._calculate_risk_profile(
                refund_rate=user_dict.get("refund_rate"),
                customer_health=user_dict.get("customer_health_score"),
            )
            labels.append(f"risk:{risk_profile}")

            # Engagement level
            engagement = float(user_dict.get("engagement_score", 0) or 0)
            if engagement >= 0.7:
                labels.append("engagement:high")
            elif engagement >= 0.4:
                labels.append("engagement:medium")
            else:
                labels.append("engagement:low")

            # Browsing style
            browsing_style = user_dict.get("browsing_style")
            if browsing_style:
                labels.append(f"style:{browsing_style}")

            # Device preference
            device = user_dict.get("primary_device")
            if device:
                labels.append(f"device:{device}")

            # 13. CONVERSION PROPENSITY (Key for recommendation prioritization)
            conversion_prop = self._calculate_conversion_propensity(user_dict)
            labels.append(f"conversion:{conversion_prop}")

            # 14. CUSTOMER MATURITY (Better than lifecycle)
            days_since_first = user_dict.get("days_since_first_order", 0) or 0
            total_purchases = user_dict.get("total_purchases", 0) or 0

            if total_purchases == 0:
                labels.append("maturity:new")
            elif total_purchases >= 10 and days_since_first >= 180:
                labels.append("maturity:established")
            elif total_purchases >= 3:
                labels.append("maturity:growing")
            else:
                labels.append("maturity:exploring")

            # 15. GEOGRAPHIC SEGMENT (Only if relevant)
            geo = user_dict.get("geographic_region")
            if geo and isinstance(geo, str) and geo != "unknown":
                if "," in geo:
                    country = geo.split(",")[-1].strip().lower()[:10]
                    labels.append(f"geo:{country}")

        except Exception as e:
            logger.error(
                f"Error converting user features to optimized labels: {str(e)}"
            )

        return labels[:15]

    def _calculate_rfm_segment(
        self,
        days_since_last: Optional[int],
        frequency: Optional[float],
        monetary: Optional[float],
    ) -> str:
        """
        Calculate RFM segment - gold standard for customer segmentation

        Args:
            days_since_last: Days since last order
            frequency: Order frequency per month
            monetary: Lifetime value

        Returns:
            RFM segment: champions, loyal, potential, at_risk, lost
        """
        # Score recency (1-5)
        if days_since_last is None:
            r_score = 1
        elif days_since_last <= 7:
            r_score = 5
        elif days_since_last <= 30:
            r_score = 4
        elif days_since_last <= 90:
            r_score = 3
        elif days_since_last <= 180:
            r_score = 2
        else:
            r_score = 1

        # Score frequency (1-5)
        freq = frequency or 0
        if freq >= 2:
            f_score = 5
        elif freq >= 1:
            f_score = 4
        elif freq >= 0.5:
            f_score = 3
        elif freq > 0:
            f_score = 2
        else:
            f_score = 1

        # Score monetary (1-5)
        ltv = monetary or 0
        if ltv >= 1000:
            m_score = 5
        elif ltv >= 500:
            m_score = 4
        elif ltv >= 100:
            m_score = 3
        elif ltv > 0:
            m_score = 2
        else:
            m_score = 1

        # Map to segments
        rfm_total = r_score + f_score + m_score
        if rfm_total >= 13:
            return "champions"
        elif rfm_total >= 11:
            return "loyal"
        elif rfm_total >= 9:
            return "potential"
        elif rfm_total >= 7:
            return "at_risk"
        else:
            return "lost"

    def _calculate_purchase_intent(self, user_dict: Dict[str, Any]) -> str:
        """
        Calculate immediate purchase intent

        Predicts likelihood of immediate purchase based on recency and conversion rates
        """
        days_since = user_dict.get("days_since_last_order", 999) or 999
        cart_to_purchase = float(user_dict.get("cart_to_purchase_rate", 0) or 0)

        if days_since <= 7 and cart_to_purchase >= 0.5:
            return "high"
        elif days_since <= 30 and cart_to_purchase >= 0.3:
            return "medium"
        elif days_since <= 90:
            return "low"
        else:
            return "dormant"

    def _calculate_price_sensitivity(
        self, avg_price: Optional[float], discount_sens: Optional[float]
    ) -> str:
        """
        Calculate price sensitivity combining AOV and discount behavior
        """
        aov = avg_price or 0
        discount = discount_sens or 0

        # Deal seeker: loves discounts, lower AOV
        if discount >= 0.7 and aov < 50:
            return "deal_seeker"
        # Value: moderate price, some discount usage
        elif aov < 100 and discount >= 0.3:
            return "value"
        # Premium: high AOV, low discount sensitivity
        elif aov >= 150 and discount < 0.3:
            return "premium"
        # Luxury: very high AOV, doesn't care about discounts
        elif aov >= 300:
            return "luxury"
        else:
            return "moderate"

    def _calculate_shopping_style(
        self,
        browse_to_cart: Optional[float],
        cart_to_purchase: Optional[float],
        avg_session_duration: Optional[float],
    ) -> str:
        """
        Determine shopping behavior style
        """
        b2c = browse_to_cart or 0
        c2p = cart_to_purchase or 0

        # Decisive: high conversion at all stages
        if c2p >= 0.7 and b2c >= 0.3:
            return "decisive"
        # Impulse: quick decisions, less browsing
        elif b2c < 0.1 or (avg_session_duration and avg_session_duration < 60):
            return "impulse"
        # Researcher: browses extensively before buying
        else:
            return "researcher"

    def _calculate_repeat_purchase_rate(self, user_dict: Dict[str, Any]) -> float:
        """
        Calculate how often customer buys same/similar products
        """
        total_purchases = user_dict.get("total_purchases", 0) or 0
        distinct_products = user_dict.get("distinct_products_purchased", 0) or 0

        if total_purchases == 0 or distinct_products == 0:
            return 0.0

        # If they bought 10 items but only 3 distinct = high repeat rate
        return 1.0 - (distinct_products / total_purchases)

    def _calculate_risk_profile(
        self, refund_rate: Optional[float], customer_health: Optional[int]
    ) -> str:
        """
        Calculate overall customer risk profile
        """
        refund = refund_rate or 0
        health = customer_health or 50

        # High risk: high refunds or low health
        if refund >= 0.3 or health < 40:
            return "high"
        # Medium risk: moderate refunds or health
        elif refund >= 0.1 or health < 70:
            return "medium"
        # Low risk: good customer
        else:
            return "low"

    def _calculate_conversion_propensity(self, user_dict: Dict[str, Any]) -> str:
        """
        Predict likelihood of next purchase
        """
        browse_to_cart = float(user_dict.get("browse_to_cart_rate", 0) or 0)
        cart_to_purchase = float(user_dict.get("cart_to_purchase_rate", 0) or 0)
        days_since = user_dict.get("days_since_last_order", 999) or 999

        # Weight cart-to-purchase more heavily
        score = browse_to_cart * 0.3 + cart_to_purchase * 0.7

        # Apply recency factor
        recency_factor = 1.0 if days_since <= 30 else 0.5

        final_score = score * recency_factor

        if final_score >= 0.5:
            return "ready"
        elif final_score >= 0.25:
            return "likely"
        else:
            return "unlikely"
