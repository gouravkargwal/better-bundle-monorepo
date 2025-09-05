"""
Customer feature generator for ML feature engineering
"""

from typing import Dict, Any, List, Optional
import statistics

from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.domains.shopify.models import (
    ShopifyCustomer,
    ShopifyShop,
    ShopifyOrder,
    BehavioralEvent,
)

from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class CustomerFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for Shopify customers"""

    async def generate_features(
        self, customer: ShopifyCustomer, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate features for a customer

        Args:
            customer: The customer to generate features for
            context: Additional context data (shop, orders, events, etc.)

        Returns:
            Dictionary of generated features
        """
        try:
            logger.debug(f"Computing features for customer: {customer.id}")

            features = {}
            shop = context.get("shop")
            orders = context.get("orders", [])
            events = context.get("events", [])

            # Basic customer features
            features.update(self._compute_basic_customer_features(customer))

            # Order history features
            if orders:
                customer_orders = [o for o in orders if o.customer_id == customer.id]
                features.update(
                    self._compute_order_history_features(customer, customer_orders)
                )

            # Behavioral features
            if events:
                customer_events = [e for e in events if e.customer_id == customer.id]
                features.update(
                    self._compute_behavioral_features(customer, customer_events)
                )

            # Address features
            features.update(self._compute_address_features(customer))

            # Time-based features
            features.update(self._compute_customer_time_features(customer))

            # Engagement features
            features.update(self._compute_engagement_features(customer))

            # Validate and clean features
            features = self.validate_features(features)

            logger.debug(
                f"Computed {len(features)} features for customer: {customer.id}"
            )
            return features

        except Exception as e:
            logger.error(
                f"Failed to compute customer features for {customer.id}: {str(e)}"
            )
            return {}

    def _compute_basic_customer_features(
        self, customer: ShopifyCustomer
    ) -> Dict[str, Any]:
        """Compute basic customer features"""
        return {
            "customer_id": customer.id,
            "accepts_marketing": 1 if customer.accepts_marketing else 0,
            "orders_count": customer.orders_count,
            "total_spent": customer.total_spent,
            "state_encoded": self._encode_categorical_feature(customer.state or ""),
            "note_encoded": self._encode_categorical_feature(customer.note or ""),
            "verified_email": 1 if customer.verified_email else 0,
            "multipass_identifier": self._encode_categorical_feature(
                customer.multipass_identifier or ""
            ),
            "tax_exempt": 1 if customer.tax_exempt else 0,
            "phone_encoded": self._encode_categorical_feature(customer.phone or ""),
            "tags_encoded": self._encode_categorical_feature(
                "|".join(customer.tags or [])
            ),
            "last_order_id": self._encode_categorical_feature(
                customer.last_order_id or ""
            ),
            "currency_encoded": self._encode_categorical_feature(
                customer.currency or ""
            ),
        }

    def _compute_order_history_features(
        self, customer: ShopifyCustomer, orders: List[ShopifyOrder]
    ) -> Dict[str, Any]:
        """Compute order history features"""
        if not orders:
            return {
                "total_orders": 0,
                "total_spent": 0,
                "average_order_value": 0,
                "days_since_last_order": 0,
                "order_frequency": 0,
                "order_consistency": 0,
            }

        total_spent = sum(order.total_price for order in orders)
        order_dates = [order.created_at for order in orders]
        order_dates.sort()

        # Calculate time between orders
        time_between_orders = []
        for i in range(1, len(order_dates)):
            days_diff = (order_dates[i] - order_dates[i - 1]).days
            time_between_orders.append(days_diff)

        return {
            "total_orders": len(orders),
            "total_spent": total_spent,
            "average_order_value": total_spent / len(orders),
            "days_since_last_order": (
                (now_utc() - order_dates[-1]).days if order_dates else 0
            ),
            "order_frequency": (
                statistics.mean(time_between_orders) if time_between_orders else 0
            ),
            "order_consistency": (
                1
                - (
                    statistics.stdev(time_between_orders)
                    / statistics.mean(time_between_orders)
                )
                if time_between_orders and statistics.mean(time_between_orders) > 0
                else 0
            ),
        }

    def _compute_behavioral_features(
        self, customer: ShopifyCustomer, events: List[BehavioralEvent]
    ) -> Dict[str, Any]:
        """Compute rich behavioral features from customer events"""
        if not events:
            return {
                "event_count": 0,
                "unique_event_types": 0,
                "last_event_days": 0,
                "event_frequency": 0,
                "engagement_score": 0,
                "page_views": 0,
                "product_views": 0,
                "cart_additions": 0,
                "collection_views": 0,
                "search_queries": 0,
                "checkout_starts": 0,
                "checkout_completions": 0,
                "unique_products_viewed": 0,
                "unique_collections_viewed": 0,
                "total_cart_value": 0.0,
                "average_product_price_viewed": 0.0,
                "search_diversity": 0.0,
                "conversion_rate": 0.0,
                "cart_abandonment_rate": 0.0,
                "browsing_intensity": 0.0,
                "purchase_intent_score": 0.0,
                # Enhanced session-based features
                "session_depth_avg": 0.0,
                "session_duration_avg": 0.0,
                "bounce_rate": 0.0,
                "page_views_per_session": 0.0,
                "unique_products_per_session": 0.0,
                "cart_interaction_rate": 0.0,
                "search_refinement_count": 0,
                "collection_browsing_depth": 0,
                "device_type_encoded": 0,
                "screen_resolution_tier": 0,
                "browser_language_encoded": 0,
                "referrer_type_encoded": 0,
                "journey_type_encoded": 0,
                "product_discovery_method_encoded": 0,
                "price_sensitivity": 0.0,
                "category_exploration_breadth": 0.0,
                "time_spent_on_product_pages": 0.0,
                "return_visitor": 0,
                "session_frequency": 0.0,
                "purchase_intent_urgency": 0.0,
                "price_comparison_behavior": 0.0,
                "research_depth": 0.0,
                "loyalty_to_brand": 0.0,
            }

        # Basic event metrics
        event_types = [event.event_type for event in events]
        event_dates = [event.occurred_at for event in events]
        event_dates.sort()

        # Calculate time between events
        time_between_events = []
        for i in range(1, len(event_dates)):
            days_diff = (event_dates[i] - event_dates[i - 1]).days
            time_between_events.append(days_diff)

        # Event type counts
        page_views = sum(1 for event in events if event.is_page_viewed)
        product_views = sum(1 for event in events if event.is_product_viewed)
        cart_additions = sum(1 for event in events if event.is_product_added_to_cart)
        collection_views = sum(1 for event in events if event.is_collection_viewed)
        search_queries = sum(1 for event in events if event.is_search_submitted)
        checkout_starts = sum(1 for event in events if event.is_checkout_started)
        checkout_completions = sum(1 for event in events if event.is_checkout_completed)

        # Enhanced session-based analysis
        session_features = self._compute_session_features(events)
        temporal_features = self._compute_temporal_features(events)
        device_features = self._compute_device_features(events)
        journey_features = self._compute_journey_features(events)

        # Unique items viewed
        unique_products = set()
        unique_collections = set()
        search_terms = set()
        cart_values = []
        product_prices = []

        for event in events:
            # Track unique products viewed
            product_id = event.get_product_id()
            if product_id:
                unique_products.add(product_id)

            # Track unique collections viewed
            collection_id = event.get_collection_id()
            if collection_id:
                unique_collections.add(collection_id)

            # Track search terms
            search_query = event.get_search_query()
            if search_query:
                search_terms.add(search_query.lower().strip())

            # Track cart values
            cart_value = event.get_cart_value()
            if cart_value is not None:
                cart_values.append(cart_value)

            # Track product prices viewed
            product_price = event.get_product_price()
            if product_price is not None:
                product_prices.append(product_price)

        # Calculate derived metrics
        total_cart_value = sum(cart_values) if cart_values else 0.0
        average_product_price_viewed = (
            statistics.mean(product_prices) if product_prices else 0.0
        )
        search_diversity = (
            len(search_terms) / max(search_queries, 1) if search_queries > 0 else 0.0
        )

        # Conversion metrics
        conversion_rate = (
            checkout_completions / max(product_views, 1) if product_views > 0 else 0.0
        )
        cart_abandonment_rate = (
            (checkout_starts - checkout_completions) / max(checkout_starts, 1)
            if checkout_starts > 0
            else 0.0
        )

        # Engagement metrics
        browsing_intensity = (product_views + collection_views + page_views) / max(
            len(events), 1
        )
        purchase_intent_score = (
            (cart_additions + checkout_starts) / max(product_views, 1)
            if product_views > 0
            else 0.0
        )

        # Overall engagement score (normalized 0-1)
        engagement_score = min(
            (len(events) + len(unique_products) + len(unique_collections)) / 20.0, 1.0
        )

        return {
            # Basic metrics
            "event_count": len(events),
            "unique_event_types": len(set(event_types)),
            "last_event_days": (now_utc() - event_dates[-1]).days if event_dates else 0,
            "event_frequency": (
                statistics.mean(time_between_events) if time_between_events else 0
            ),
            "engagement_score": engagement_score,
            # Event type counts
            "page_views": page_views,
            "product_views": product_views,
            "cart_additions": cart_additions,
            "collection_views": collection_views,
            "search_queries": search_queries,
            "checkout_starts": checkout_starts,
            "checkout_completions": checkout_completions,
            # Unique items
            "unique_products_viewed": len(unique_products),
            "unique_collections_viewed": len(unique_collections),
            # Financial metrics
            "total_cart_value": total_cart_value,
            "average_product_price_viewed": average_product_price_viewed,
            # Behavioral metrics
            "search_diversity": search_diversity,
            "conversion_rate": conversion_rate,
            "cart_abandonment_rate": cart_abandonment_rate,
            "browsing_intensity": browsing_intensity,
            "purchase_intent_score": purchase_intent_score,
            # Enhanced session-based features
            **session_features,
            **temporal_features,
            **device_features,
            **journey_features,
        }

    def _compute_address_features(self, customer: ShopifyCustomer) -> Dict[str, Any]:
        """Compute address-related features"""
        if not customer.default_address:
            return {
                "has_address": 0,
                "country_encoded": 0,
                "province_encoded": 0,
                "city_encoded": 0,
            }

        address = customer.default_address
        return {
            "has_address": 1,
            "country_encoded": self._encode_categorical_feature(address.country or ""),
            "province_encoded": self._encode_categorical_feature(
                address.province or ""
            ),
            "city_encoded": self._encode_categorical_feature(address.city or ""),
        }

    def _compute_customer_time_features(
        self, customer: ShopifyCustomer
    ) -> Dict[str, Any]:
        """Compute time-based features for customer"""
        return self._compute_time_based_features(
            customer.created_at, customer.updated_at
        )

    def _compute_engagement_features(self, customer: ShopifyCustomer) -> Dict[str, Any]:
        """Compute customer engagement features"""
        engagement_score = 0

        # Marketing acceptance
        if customer.accepts_marketing:
            engagement_score += 1

        # Email verification
        if customer.verified_email:
            engagement_score += 1

        # Order history
        if customer.orders_count > 0:
            engagement_score += 1

        # Spending history
        if customer.total_spent > 0:
            engagement_score += 1

        # Address provided
        if customer.default_address:
            engagement_score += 1

        return {
            "engagement_score": engagement_score,
            "engagement_tier": (
                "high"
                if engagement_score >= 4
                else "medium" if engagement_score >= 2 else "low"
            ),
        }

    def _compute_session_features(
        self, events: List[BehavioralEvent]
    ) -> Dict[str, Any]:
        """Compute session-based behavioral features"""
        if not events:
            return {
                "session_depth_avg": 0.0,
                "session_duration_avg": 0.0,
                "bounce_rate": 0.0,
                "page_views_per_session": 0.0,
                "unique_products_per_session": 0.0,
                "cart_interaction_rate": 0.0,
                "search_refinement_count": 0,
                "collection_browsing_depth": 0,
            }

        # Group events by session (using clientId and time proximity)
        sessions = self._group_events_by_session(events)

        session_depths = []
        session_durations = []
        bounce_sessions = 0
        total_page_views = 0
        total_products_viewed = 0
        total_cart_interactions = 0
        search_refinements = 0
        collection_depths = []

        for session in sessions:
            session_depths.append(len(session))

            # Calculate session duration
            if len(session) > 1:
                duration = (
                    session[-1].occurred_at - session[0].occurred_at
                ).total_seconds() / 60
                session_durations.append(duration)
            else:
                bounce_sessions += 1
                session_durations.append(0)

            # Count page views and products in session
            page_views_in_session = sum(1 for e in session if e.is_page_viewed)
            products_in_session = len(
                set(e.get_product_id() for e in session if e.get_product_id())
            )
            cart_interactions_in_session = sum(
                1 for e in session if e.is_product_added_to_cart
            )

            total_page_views += page_views_in_session
            total_products_viewed += products_in_session
            total_cart_interactions += cart_interactions_in_session

            # Search refinements (multiple searches in same session)
            searches_in_session = sum(1 for e in session if e.is_search_submitted)
            if searches_in_session > 1:
                search_refinements += searches_in_session - 1

            # Collection browsing depth
            collections_in_session = sum(1 for e in session if e.is_collection_viewed)
            collection_depths.append(collections_in_session)

        num_sessions = len(sessions)

        return {
            "session_depth_avg": (
                statistics.mean(session_depths) if session_depths else 0.0
            ),
            "session_duration_avg": (
                statistics.mean(session_durations) if session_durations else 0.0
            ),
            "bounce_rate": bounce_sessions / num_sessions if num_sessions > 0 else 0.0,
            "page_views_per_session": (
                total_page_views / num_sessions if num_sessions > 0 else 0.0
            ),
            "unique_products_per_session": (
                total_products_viewed / num_sessions if num_sessions > 0 else 0.0
            ),
            "cart_interaction_rate": total_cart_interactions / max(total_page_views, 1),
            "search_refinement_count": search_refinements,
            "collection_browsing_depth": (
                statistics.mean(collection_depths) if collection_depths else 0.0
            ),
        }

    def _compute_temporal_features(
        self, events: List[BehavioralEvent]
    ) -> Dict[str, Any]:
        """Compute temporal and seasonality features"""
        if not events:
            return {
                "hour_of_day_encoded": 0,
                "day_of_week_encoded": 0,
                "month_encoded": 0,
                "season_encoded": 0,
                "is_weekend": 0,
                "is_holiday_season": 0,
                "time_since_last_visit_hours": 0.0,
                "visit_frequency_days": 0.0,
                "peak_shopping_hours": 0,
            }

        # Analyze temporal patterns
        hours = [event.occurred_at.hour for event in events]
        days_of_week = [event.occurred_at.weekday() for event in events]
        months = [event.occurred_at.month for event in events]

        # Most common patterns
        most_common_hour = max(set(hours), key=hours.count) if hours else 12
        most_common_day = (
            max(set(days_of_week), key=days_of_week.count) if days_of_week else 0
        )
        most_common_month = max(set(months), key=months.count) if months else 6

        # Weekend activity
        weekend_events = sum(
            1 for day in days_of_week if day >= 5
        )  # Saturday=5, Sunday=6
        is_weekend_shopper = 1 if weekend_events > len(events) * 0.3 else 0

        # Holiday season (Nov-Dec)
        holiday_events = sum(1 for month in months if month in [11, 12])
        is_holiday_shopper = 1 if holiday_events > 0 else 0

        # Visit frequency
        if len(events) > 1:
            time_span = (events[-1].occurred_at - events[0].occurred_at).days
            visit_frequency = time_span / len(events) if len(events) > 0 else 0
        else:
            visit_frequency = 0

        # Time since last visit
        time_since_last = (
            (now_utc() - events[-1].occurred_at).total_seconds() / 3600 if events else 0
        )

        # Peak shopping hours (9-17)
        peak_hour_events = sum(1 for hour in hours if 9 <= hour <= 17)
        peak_shopping = 1 if peak_hour_events > len(events) * 0.5 else 0

        return {
            "hour_of_day_encoded": most_common_hour,
            "day_of_week_encoded": most_common_day,
            "month_encoded": most_common_month,
            "season_encoded": self._get_season(most_common_month),
            "is_weekend": is_weekend_shopper,
            "is_holiday_season": is_holiday_shopper,
            "time_since_last_visit_hours": time_since_last,
            "visit_frequency_days": visit_frequency,
            "peak_shopping_hours": peak_shopping,
        }

    def _compute_device_features(self, events: List[BehavioralEvent]) -> Dict[str, Any]:
        """Compute device and browser features"""
        if not events:
            return {
                "device_type_encoded": 0,
                "screen_resolution_tier": 0,
                "browser_language_encoded": 0,
                "referrer_type_encoded": 0,
            }

        # Extract device info from event data (assuming it's in event_data)
        device_types = []
        screen_resolutions = []
        languages = []
        referrers = []

        for event in events:
            if event.event_data:
                # Device type from user agent
                user_agent = (
                    event.event_data.get("context", {})
                    .get("navigator", {})
                    .get("userAgent", "")
                )
                device_type = self._classify_device(user_agent)
                device_types.append(device_type)

                # Screen resolution
                window = event.event_data.get("context", {}).get("window", {})
                width = window.get("innerWidth", 0)
                height = window.get("innerHeight", 0)
                resolution_tier = self._classify_resolution(width, height)
                screen_resolutions.append(resolution_tier)

                # Language
                language = (
                    event.event_data.get("context", {})
                    .get("navigator", {})
                    .get("language", "en-US")
                )
                languages.append(language)

                # Referrer
                referrer = (
                    event.event_data.get("context", {})
                    .get("document", {})
                    .get("referrer", "")
                )
                referrer_type = self._classify_referrer(referrer)
                referrers.append(referrer_type)

        # Get most common values
        most_common_device = (
            max(set(device_types), key=device_types.count) if device_types else 0
        )
        most_common_resolution = (
            max(set(screen_resolutions), key=screen_resolutions.count)
            if screen_resolutions
            else 0
        )
        most_common_language = (
            max(set(languages), key=languages.count) if languages else "en-US"
        )
        most_common_referrer = (
            max(set(referrers), key=referrers.count) if referrers else 0
        )

        return {
            "device_type_encoded": most_common_device,
            "screen_resolution_tier": most_common_resolution,
            "browser_language_encoded": self._encode_categorical_feature(
                most_common_language
            ),
            "referrer_type_encoded": most_common_referrer,
        }

    def _compute_journey_features(
        self, events: List[BehavioralEvent]
    ) -> Dict[str, Any]:
        """Compute user journey and intent features"""
        if not events:
            return {
                "journey_type_encoded": 0,
                "product_discovery_method_encoded": 0,
                "price_sensitivity": 0.0,
                "category_exploration_breadth": 0.0,
                "time_spent_on_product_pages": 0.0,
                "return_visitor": 0,
                "session_frequency": 0.0,
                "purchase_intent_urgency": 0.0,
                "price_comparison_behavior": 0.0,
                "research_depth": 0.0,
                "loyalty_to_brand": 0.0,
            }

        # Analyze journey patterns
        event_sequence = [event.event_type for event in events]

        # Journey type classification
        journey_type = self._classify_journey_type(event_sequence)

        # Product discovery method
        discovery_method = self._classify_discovery_method(events)

        # Price sensitivity (based on price comparison behavior)
        price_sensitivity = self._calculate_price_sensitivity(events)

        # Category exploration breadth
        categories_viewed = set()
        for event in events:
            if event.event_data:
                product = event.event_data.get("productVariant", {}).get("product", {})
                if product.get("type"):
                    categories_viewed.add(product["type"])
        category_breadth = len(categories_viewed) / max(len(events), 1)

        # Time spent on product pages (estimated)
        product_view_events = [e for e in events if e.is_product_viewed]
        time_on_products = len(product_view_events) * 30  # Assume 30 seconds per view

        # Return visitor (has multiple sessions)
        sessions = self._group_events_by_session(events)
        return_visitor = 1 if len(sessions) > 1 else 0

        # Session frequency
        if len(events) > 1:
            time_span_days = (events[-1].occurred_at - events[0].occurred_at).days
            session_frequency = (
                len(sessions) / max(time_span_days, 1) * 7
            )  # sessions per week
        else:
            session_frequency = 0

        # Purchase intent urgency (based on checkout behavior)
        checkout_events = sum(
            1 for e in events if e.is_checkout_started or e.is_checkout_completed
        )
        purchase_intent_urgency = checkout_events / max(len(events), 1)

        # Price comparison behavior
        price_comparison = self._calculate_price_comparison_behavior(events)

        # Research depth (based on search and product view patterns)
        research_depth = (
            sum(1 for e in events if e.is_search_submitted)
            + sum(1 for e in events if e.is_product_viewed)
        ) / max(len(events), 1)

        # Brand loyalty (based on vendor consistency)
        vendors = []
        for event in events:
            if event.event_data:
                product = event.event_data.get("productVariant", {}).get("product", {})
                if product.get("vendor"):
                    vendors.append(product["vendor"])
        brand_loyalty = len(set(vendors)) / max(len(vendors), 1) if vendors else 0

        return {
            "journey_type_encoded": journey_type,
            "product_discovery_method_encoded": discovery_method,
            "price_sensitivity": price_sensitivity,
            "category_exploration_breadth": category_breadth,
            "time_spent_on_product_pages": time_on_products,
            "return_visitor": return_visitor,
            "session_frequency": session_frequency,
            "purchase_intent_urgency": purchase_intent_urgency,
            "price_comparison_behavior": price_comparison,
            "research_depth": research_depth,
            "loyalty_to_brand": 1 - brand_loyalty,  # Invert so higher = more loyal
        }

    def _group_events_by_session(
        self, events: List[BehavioralEvent]
    ) -> List[List[BehavioralEvent]]:
        """Group events by session using time proximity and clientId"""
        if not events:
            return []

        # Sort events by time
        sorted_events = sorted(events, key=lambda e: e.occurred_at)

        sessions = []
        current_session = [sorted_events[0]]

        for i in range(1, len(sorted_events)):
            current_event = sorted_events[i]
            previous_event = sorted_events[i - 1]

            # If more than 30 minutes gap, start new session
            time_gap = (
                current_event.occurred_at - previous_event.occurred_at
            ).total_seconds() / 60

            if time_gap > 30:  # 30 minutes session timeout
                sessions.append(current_session)
                current_session = [current_event]
            else:
                current_session.append(current_event)

        sessions.append(current_session)
        return sessions

    def _get_season(self, month: int) -> int:
        """Convert month to season (0=spring, 1=summer, 2=fall, 3=winter)"""
        if month in [3, 4, 5]:
            return 0  # Spring
        elif month in [6, 7, 8]:
            return 1  # Summer
        elif month in [9, 10, 11]:
            return 2  # Fall
        else:
            return 3  # Winter

    def _classify_device(self, user_agent: str) -> int:
        """Classify device type from user agent (0=mobile, 1=tablet, 2=desktop)"""
        user_agent_lower = user_agent.lower()
        if any(
            mobile in user_agent_lower for mobile in ["mobile", "android", "iphone"]
        ):
            return 0  # Mobile
        elif any(tablet in user_agent_lower for tablet in ["tablet", "ipad"]):
            return 1  # Tablet
        else:
            return 2  # Desktop

    def _classify_resolution(self, width: int, height: int) -> int:
        """Classify screen resolution tier (0=low, 1=medium, 2=high)"""
        if width < 768:
            return 0  # Low (mobile)
        elif width < 1200:
            return 1  # Medium (tablet)
        else:
            return 2  # High (desktop)

    def _classify_referrer(self, referrer: str) -> int:
        """Classify referrer type (0=direct, 1=search, 2=social, 3=other)"""
        if not referrer:
            return 0  # Direct
        elif any(
            search in referrer.lower()
            for search in ["google", "bing", "yahoo", "search"]
        ):
            return 1  # Search
        elif any(
            social in referrer.lower()
            for social in ["facebook", "twitter", "instagram", "pinterest"]
        ):
            return 2  # Social
        else:
            return 3  # Other

    def _classify_journey_type(self, event_sequence: List[str]) -> int:
        """Classify journey type (0=browser, 1=searcher, 2=direct_buyer)"""
        search_count = event_sequence.count("search_submitted")
        product_views = event_sequence.count("product_viewed")
        cart_adds = event_sequence.count("product_added_to_cart")
        checkouts = event_sequence.count("checkout_started")

        if checkouts > 0 and len(event_sequence) < 5:
            return 2  # Direct buyer
        elif search_count > product_views * 0.3:
            return 1  # Searcher
        else:
            return 0  # Browser

    def _classify_discovery_method(self, events: List[BehavioralEvent]) -> int:
        """Classify product discovery method (0=search, 1=collection, 2=direct)"""
        search_events = sum(1 for e in events if e.is_search_submitted)
        collection_events = sum(1 for e in events if e.is_collection_viewed)

        if search_events > collection_events:
            return 0  # Search
        elif collection_events > 0:
            return 1  # Collection
        else:
            return 2  # Direct

    def _calculate_price_sensitivity(self, events: List[BehavioralEvent]) -> float:
        """Calculate price sensitivity based on price comparison behavior"""
        prices_viewed = []
        for event in events:
            price = event.get_product_price()
            if price is not None:
                prices_viewed.append(price)

        if len(prices_viewed) < 2:
            return 0.0

        # Price sensitivity = coefficient of variation
        mean_price = statistics.mean(prices_viewed)
        if mean_price == 0:
            return 0.0

        std_price = statistics.stdev(prices_viewed)
        return std_price / mean_price

    def _calculate_price_comparison_behavior(
        self, events: List[BehavioralEvent]
    ) -> float:
        """Calculate price comparison behavior score"""
        # Count how many times user views multiple products in same category
        category_views = {}
        for event in events:
            if event.event_data:
                product = event.event_data.get("productVariant", {}).get("product", {})
                category = product.get("type")
                if category:
                    if category not in category_views:
                        category_views[category] = 0
                    category_views[category] += 1

        # Calculate comparison behavior
        total_comparisons = sum(max(0, views - 1) for views in category_views.values())
        total_views = sum(category_views.values())

        return total_comparisons / max(total_views, 1)
