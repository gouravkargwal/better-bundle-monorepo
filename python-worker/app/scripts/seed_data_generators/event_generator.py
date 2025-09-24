"""
Behavioral event generator for creating realistic user journey data.
"""

import random
from datetime import datetime
from typing import Dict, Any, List
from .base_generator import BaseGenerator


class EventGenerator(BaseGenerator):
    """Generates realistic behavioral events for user journeys."""

    def generate_events(
        self, product_variant_ids: List[str], customer_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Generate comprehensive behavioral events for realistic user journeys."""
        events = []

        # Generate client IDs for sessions
        client_ids = [self.generate_client_id() for _ in range(8)]

        # Alice's journey (VIP customer - multiple sessions)
        events.extend(
            self._generate_alice_journey(
                client_ids[0], product_variant_ids, customer_ids[0]
            )
        )

        # Bob's journey (new customer - browsing only)
        events.extend(
            self._generate_bob_journey(
                client_ids[1], product_variant_ids, customer_ids[1]
            )
        )

        # Charlie's journey (moderate buyer - electronics focused)
        events.extend(
            self._generate_charlie_journey(
                client_ids[2], product_variant_ids, customer_ids[2]
            )
        )

        # Dana's journey (abandoned cart)
        events.extend(
            self._generate_dana_journey(
                client_ids[3], product_variant_ids, customer_ids[3]
            )
        )

        # Eve's journey (cross-category buyer)
        events.extend(
            self._generate_eve_journey(
                client_ids[4], product_variant_ids, customer_ids[4]
            )
        )

        # Frank's journey (tech enthusiast)
        events.extend(
            self._generate_frank_journey(
                client_ids[5], product_variant_ids, customer_ids[5]
            )
        )

        # Grace's journey (fashion lover)
        events.extend(
            self._generate_grace_journey(
                client_ids[6], product_variant_ids, customer_ids[6]
            )
        )

        # Henry's journey (bargain hunter)
        events.extend(
            self._generate_henry_journey(
                client_ids[7], product_variant_ids, customer_ids[7]
            )
        )

        # Additional anonymous sessions for edge cases
        events.extend(self._generate_anonymous_sessions(product_variant_ids))

        return events

    def _generate_alice_journey(
        self, client_id: str, product_variant_ids: List[str], customer_id: str
    ) -> List[Dict[str, Any]]:
        """Generate Alice's comprehensive shopping journey (VIP customer)."""
        events = []
        seq = 1

        # Session 1: Initial browsing and first purchase (5 days ago)
        events.append(
            self._create_event(
                "page_viewed", client_id, seq, {}, self.past_date(5), "mobile"
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "search_submitted",
                client_id,
                seq,
                {"searchResult": {"query": "hoodie"}},
                self.past_date(5),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "collection_viewed",
                client_id,
                seq,
                self._build_collection_data(
                    "summer-essentials", [0, 1, 2], product_variant_ids
                ),
                self.past_date(5),
                "mobile",
            )
        )
        seq += 1

        # View products
        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(0, product_variant_ids),
                self.past_date(5),
                "mobile",
            )
        )
        seq += 1

        # Phoenix recommendations (product page recommendations)
        events.append(
            self._create_event(
                "recommendation_viewed",
                client_id,
                seq,
                self._build_recommendation_data(
                    "phoenix", "product_page", [1, 2, 3], product_variant_ids
                ),
                self.past_date(5),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "recommendation_clicked",
                client_id,
                seq,
                self._build_recommendation_click_data(1, product_variant_ids),
                self.past_date(5),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(1, product_variant_ids),
                self.past_date(5),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(2, product_variant_ids),
                self.past_date(5),
                "mobile",
            )
        )
        seq += 1

        # Add to cart and purchase
        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(0, product_variant_ids),
                self.past_date(5),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "cart_viewed",
                client_id,
                seq,
                self._build_cart_view_data([0], product_variant_ids),
                self.past_date(5),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "checkout_started",
                client_id,
                seq,
                self._build_checkout_data([0], product_variant_ids),
                self.past_date(5),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "checkout_completed",
                client_id,
                seq,
                self._build_checkout_completed_data([0], product_variant_ids),
                self.past_date(5),
                "mobile",
                customer_id,
            )
        )
        seq += 1

        # Apollo post-purchase upsell events
        events.append(
            self._create_event(
                "upsell_viewed",
                client_id,
                seq,
                self._build_upsell_data(
                    "apollo", "post_purchase", [1, 2, 3], product_variant_ids
                ),
                self.past_date(5),
                "mobile",
                customer_id,
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "upsell_clicked",
                client_id,
                seq,
                self._build_recommendation_click_data(1, product_variant_ids),
                self.past_date(5),
                "mobile",
                customer_id,
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "customer_linked",
                client_id,
                seq,
                {"customerId": customer_id},
                self.past_date(5),
                "mobile",
            )
        )
        seq += 1

        # Session 2: Return visit and accessories purchase (3 days ago)
        events.append(
            self._create_event(
                "page_viewed", client_id, seq, {}, self.past_date(3), "desktop"
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(5, product_variant_ids),
                self.past_date(3),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(6, product_variant_ids),
                self.past_date(3),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(5, product_variant_ids),
                self.past_date(3),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(6, product_variant_ids),
                self.past_date(3),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "checkout_completed",
                client_id,
                seq,
                self._build_checkout_completed_data([5, 6], product_variant_ids),
                self.past_date(3),
                "desktop",
                customer_id,
            )
        )
        seq += 1

        # Session 3: Electronics purchase (1 day ago)
        events.append(
            self._create_event(
                "page_viewed", client_id, seq, {}, self.past_date(1), "mobile"
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "collection_viewed",
                client_id,
                seq,
                self._build_collection_data("tech-gear", [10, 11], product_variant_ids),
                self.past_date(1),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(10, product_variant_ids),
                self.past_date(1),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(11, product_variant_ids),
                self.past_date(1),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(10, product_variant_ids),
                self.past_date(1),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(11, product_variant_ids),
                self.past_date(1),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "checkout_completed",
                client_id,
                seq,
                self._build_checkout_completed_data([10, 11], product_variant_ids),
                self.past_date(1),
                "mobile",
                customer_id,
            )
        )
        seq += 1

        return events

    def _generate_bob_journey(
        self, client_id: str, product_variant_ids: List[str], customer_id: str
    ) -> List[Dict[str, Any]]:
        """Generate Bob's journey (new customer - browsing only)."""
        events = []
        seq = 1

        # Browse electronics but don't purchase
        events.append(
            self._create_event(
                "page_viewed", client_id, seq, {}, self.past_date(4), "desktop"
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "search_submitted",
                client_id,
                seq,
                {"searchResult": {"query": "wireless earbuds"}},
                self.past_date(4),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(10, product_variant_ids),
                self.past_date(4),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(11, product_variant_ids),
                self.past_date(4),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(12, product_variant_ids),
                self.past_date(4),
                "desktop",
            )
        )
        seq += 1

        # Register but don't purchase
        events.append(
            self._create_event(
                "customer_linked",
                client_id,
                seq,
                {"customerId": customer_id},
                self.past_date(4),
                "desktop",
            )
        )
        seq += 1

        return events

    def _generate_charlie_journey(
        self, client_id: str, product_variant_ids: List[str], customer_id: str
    ) -> List[Dict[str, Any]]:
        """Generate Charlie's journey (moderate buyer - electronics focused)."""
        events = []
        seq = 1

        # Electronics purchase
        events.append(
            self._create_event(
                "page_viewed", client_id, seq, {}, self.past_date(7), "desktop"
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "collection_viewed",
                client_id,
                seq,
                self._build_collection_data(
                    "tech-gear", [10, 11, 12], product_variant_ids
                ),
                self.past_date(7),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(10, product_variant_ids),
                self.past_date(7),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(12, product_variant_ids),
                self.past_date(7),
                "desktop",
            )
        )
        seq += 1

        # Venus cross-sell events (frequently bought together)
        events.append(
            self._create_event(
                "cross_sell_viewed",
                client_id,
                seq,
                self._build_cross_sell_data(
                    "venus", "product_page", [13, 14], product_variant_ids
                ),
                self.past_date(7),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "cross_sell_clicked",
                client_id,
                seq,
                self._build_recommendation_click_data(13, product_variant_ids),
                self.past_date(7),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(10, product_variant_ids),
                self.past_date(7),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(12, product_variant_ids),
                self.past_date(7),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "checkout_completed",
                client_id,
                seq,
                self._build_checkout_completed_data([10, 12], product_variant_ids),
                self.past_date(7),
                "desktop",
                customer_id,
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "customer_linked",
                client_id,
                seq,
                {"customerId": customer_id},
                self.past_date(7),
                "desktop",
            )
        )
        seq += 1

        # Return visit for accessories
        events.append(
            self._create_event(
                "page_viewed", client_id, seq, {}, self.past_date(4), "mobile"
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(5, product_variant_ids),
                self.past_date(4),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(7, product_variant_ids),
                self.past_date(4),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(5, product_variant_ids),
                self.past_date(4),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(7, product_variant_ids),
                self.past_date(4),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "checkout_completed",
                client_id,
                seq,
                self._build_checkout_completed_data([5, 7], product_variant_ids),
                self.past_date(4),
                "mobile",
                customer_id,
            )
        )
        seq += 1

        return events

    def _generate_dana_journey(
        self, client_id: str, product_variant_ids: List[str], customer_id: str
    ) -> List[Dict[str, Any]]:
        """Generate Dana's journey (abandoned cart)."""
        events = []
        seq = 1

        # Browse and add to cart but abandon
        events.append(
            self._create_event(
                "page_viewed", client_id, seq, {}, self.past_date(2), "mobile"
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "search_submitted",
                client_id,
                seq,
                {"searchResult": {"query": "scarf"}},
                self.past_date(2),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(7, product_variant_ids),
                self.past_date(2),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(7, product_variant_ids),
                self.past_date(2),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "cart_viewed",
                client_id,
                seq,
                self._build_cart_view_data([7], product_variant_ids),
                self.past_date(2),
                "mobile",
            )
        )
        seq += 1

        # Register but abandon cart
        events.append(
            self._create_event(
                "customer_linked",
                client_id,
                seq,
                {"customerId": customer_id},
                self.past_date(2),
                "mobile",
            )
        )
        seq += 1

        return events

    def _generate_eve_journey(
        self, client_id: str, product_variant_ids: List[str], customer_id: str
    ) -> List[Dict[str, Any]]:
        """Generate Eve's journey (cross-category buyer)."""
        events = []
        seq = 1

        # Cross-category purchase
        events.append(
            self._create_event(
                "page_viewed", client_id, seq, {}, self.past_date(6), "mobile"
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(0, product_variant_ids),
                self.past_date(6),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(10, product_variant_ids),
                self.past_date(6),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(0, product_variant_ids),
                self.past_date(6),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(10, product_variant_ids),
                self.past_date(6),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "checkout_completed",
                client_id,
                seq,
                self._build_checkout_completed_data([0, 10], product_variant_ids),
                self.past_date(6),
                "mobile",
                customer_id,
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "customer_linked",
                client_id,
                seq,
                {"customerId": customer_id},
                self.past_date(6),
                "mobile",
            )
        )
        seq += 1

        # Fashion accessories purchase
        events.append(
            self._create_event(
                "page_viewed", client_id, seq, {}, self.past_date(2), "desktop"
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(7, product_variant_ids),
                self.past_date(2),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(8, product_variant_ids),
                self.past_date(2),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(7, product_variant_ids),
                self.past_date(2),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(8, product_variant_ids),
                self.past_date(2),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "checkout_completed",
                client_id,
                seq,
                self._build_checkout_completed_data([7, 8], product_variant_ids),
                self.past_date(2),
                "desktop",
                customer_id,
            )
        )
        seq += 1

        return events

    def _generate_frank_journey(
        self, client_id: str, product_variant_ids: List[str], customer_id: str
    ) -> List[Dict[str, Any]]:
        """Generate Frank's journey (tech enthusiast)."""
        events = []
        seq = 1

        # Tech bundle purchase
        events.append(
            self._create_event(
                "page_viewed", client_id, seq, {}, self.past_date(8), "desktop"
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "collection_viewed",
                client_id,
                seq,
                self._build_collection_data(
                    "tech-gear", [11, 12, 13], product_variant_ids
                ),
                self.past_date(8),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(11, product_variant_ids),
                self.past_date(8),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(12, product_variant_ids),
                self.past_date(8),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(13, product_variant_ids),
                self.past_date(8),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(11, product_variant_ids),
                self.past_date(8),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(12, product_variant_ids),
                self.past_date(8),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(13, product_variant_ids),
                self.past_date(8),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "checkout_completed",
                client_id,
                seq,
                self._build_checkout_completed_data([11, 12, 13], product_variant_ids),
                self.past_date(8),
                "desktop",
                customer_id,
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "customer_linked",
                client_id,
                seq,
                {"customerId": customer_id},
                self.past_date(8),
                "desktop",
            )
        )
        seq += 1

        # Speaker purchase
        events.append(
            self._create_event(
                "page_viewed", client_id, seq, {}, self.past_date(3), "mobile"
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(14, product_variant_ids),
                self.past_date(3),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(14, product_variant_ids),
                self.past_date(3),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "checkout_completed",
                client_id,
                seq,
                self._build_checkout_completed_data([14], product_variant_ids),
                self.past_date(3),
                "mobile",
                customer_id,
            )
        )
        seq += 1

        return events

    def _generate_grace_journey(
        self, client_id: str, product_variant_ids: List[str], customer_id: str
    ) -> List[Dict[str, Any]]:
        """Generate Grace's journey (fashion lover)."""
        events = []
        seq = 1

        # Fashion bundle
        events.append(
            self._create_event(
                "page_viewed", client_id, seq, {}, self.past_date(4), "mobile"
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "collection_viewed",
                client_id,
                seq,
                self._build_collection_data(
                    "summer-essentials", [1, 2, 6], product_variant_ids
                ),
                self.past_date(4),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(1, product_variant_ids),
                self.past_date(4),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(2, product_variant_ids),
                self.past_date(4),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(6, product_variant_ids),
                self.past_date(4),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(1, product_variant_ids),
                self.past_date(4),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(2, product_variant_ids),
                self.past_date(4),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(6, product_variant_ids),
                self.past_date(4),
                "mobile",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "checkout_completed",
                client_id,
                seq,
                self._build_checkout_completed_data([1, 2, 6], product_variant_ids),
                self.past_date(4),
                "mobile",
                customer_id,
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "customer_linked",
                client_id,
                seq,
                {"customerId": customer_id},
                self.past_date(4),
                "mobile",
            )
        )
        seq += 1

        # Accessories purchase
        events.append(
            self._create_event(
                "page_viewed", client_id, seq, {}, self.past_date(1), "desktop"
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(5, product_variant_ids),
                self.past_date(1),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(7, product_variant_ids),
                self.past_date(1),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(5, product_variant_ids),
                self.past_date(1),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(7, product_variant_ids),
                self.past_date(1),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "checkout_completed",
                client_id,
                seq,
                self._build_checkout_completed_data([5, 7], product_variant_ids),
                self.past_date(1),
                "desktop",
                customer_id,
            )
        )
        seq += 1

        return events

    def _generate_henry_journey(
        self, client_id: str, product_variant_ids: List[str], customer_id: str
    ) -> List[Dict[str, Any]]:
        """Generate Henry's journey (bargain hunter)."""
        events = []
        seq = 1

        # Browse sale items
        events.append(
            self._create_event(
                "page_viewed", client_id, seq, {}, self.past_date(6), "desktop"
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "search_submitted",
                client_id,
                seq,
                {"searchResult": {"query": "sale"}},
                self.past_date(6),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(2, product_variant_ids),
                self.past_date(6),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(4, product_variant_ids),
                self.past_date(6),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_viewed",
                client_id,
                seq,
                self._build_product_view_data(9, product_variant_ids),
                self.past_date(6),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(2, product_variant_ids),
                self.past_date(6),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(4, product_variant_ids),
                self.past_date(6),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "product_added_to_cart",
                client_id,
                seq,
                self._build_cart_data(9, product_variant_ids),
                self.past_date(6),
                "desktop",
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "checkout_completed",
                client_id,
                seq,
                self._build_checkout_completed_data([2, 4, 9], product_variant_ids),
                self.past_date(6),
                "desktop",
                customer_id,
            )
        )
        seq += 1

        events.append(
            self._create_event(
                "customer_linked",
                client_id,
                seq,
                {"customerId": customer_id},
                self.past_date(6),
                "desktop",
            )
        )
        seq += 1

        return events

    def _generate_anonymous_sessions(
        self, product_variant_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Generate additional anonymous sessions for edge cases."""
        events = []

        # Anonymous abandonment
        anonymous_client = self.generate_client_id()
        events.append(
            self._create_event(
                "page_viewed", anonymous_client, 1, {}, self.past_date(6)
            )
        )
        events.append(
            self._create_event(
                "product_viewed",
                anonymous_client,
                2,
                self._build_product_view_data(9, product_variant_ids),
                self.past_date(6),
            )
        )
        events.append(
            self._create_event(
                "product_added_to_cart",
                anonymous_client,
                3,
                self._build_cart_data(9, product_variant_ids),
                self.past_date(6),
            )
        )

        # Popular item views (make sunglasses popular)
        for i in range(8):
            popular_client = self.generate_client_id()
            events.append(
                self._create_event(
                    "product_viewed",
                    popular_client,
                    1,
                    self._build_product_view_data(5, product_variant_ids),
                    self.random_past_date(1, 30),
                )
            )

        # New item views (make scarf popular for "latest")
        for i in range(5):
            new_client = self.generate_client_id()
            events.append(
                self._create_event(
                    "product_viewed",
                    new_client,
                    1,
                    self._build_product_view_data(7, product_variant_ids),
                    self.random_past_date(1, 5),
                )
            )

        return events

    def _create_event(
        self,
        event_name: str,
        client_id: str,
        seq: int,
        extra: Dict[str, Any],
        timestamp: datetime,
        device_type: str = "desktop",
        customer_id: str = None,
        extension_type: str = None,
        interaction_type: str = None,
    ) -> Dict[str, Any]:
        """Create a behavioral event payload with new interaction and extension types."""
        base = {
            "id": f"e_{self.generate_client_id()}",
            "name": event_name,
            "eventType": event_name,  # Add eventType for mapping
            "timestamp": timestamp.isoformat(),
            "clientId": client_id,
            "seq": seq,
            "type": "standard",
            "extensionType": extension_type or self._get_extension_type(event_name),
            "interactionType": interaction_type
            or self._get_interaction_type(event_name),
            "context": {
                "document": {
                    "location": {
                        "href": f"https://{self.shop_domain}/",
                        "pathname": "/",
                        "search": "",
                    },
                    "referrer": f"https://{self.shop_domain}/",
                    "title": "Fashion Store",
                },
                "shop": {
                    "domain": self.shop_domain,
                },
                "userAgent": f"Mozilla/5.0 ({device_type})",
            },
        }

        if customer_id:
            base["customerId"] = customer_id

        if extra:
            base.update({"data": extra})
        else:
            base.update({"data": {}})

        return base

    def _get_extension_type(self, event_name: str) -> str:
        """Map event names to extension types."""
        extension_mapping = {
            # Standard Shopify events (tracked by Atlas)
            "page_viewed": "atlas",
            "product_viewed": "atlas",
            "product_added_to_cart": "atlas",
            "product_removed_from_cart": "atlas",
            "cart_viewed": "atlas",
            "collection_viewed": "atlas",
            "search_submitted": "atlas",
            "checkout_started": "atlas",
            "checkout_completed": "atlas",
            "customer_linked": "atlas",
            # Recommendation events (tracked by Phoenix)
            "recommendation_viewed": "phoenix",
            "recommendation_clicked": "phoenix",
            "recommendation_add_to_cart": "phoenix",
            # Post-purchase events (tracked by Apollo)
            "upsell_viewed": "apollo",
            "upsell_clicked": "apollo",
            "upsell_add_to_cart": "apollo",
            # Cross-sell events (tracked by Venus)
            "cross_sell_viewed": "venus",
            "cross_sell_clicked": "venus",
            "cross_sell_add_to_cart": "venus",
        }
        return extension_mapping.get(event_name, "atlas")

    def _get_interaction_type(self, event_name: str) -> str:
        """Map event names to interaction types."""
        interaction_mapping = {
            # Standard Shopify events
            "page_viewed": "page_viewed",
            "product_viewed": "product_viewed",
            "product_added_to_cart": "product_added_to_cart",
            "product_removed_from_cart": "product_removed_from_cart",
            "cart_viewed": "cart_viewed",
            "collection_viewed": "collection_viewed",
            "search_submitted": "search_submitted",
            "checkout_started": "checkout_started",
            "checkout_completed": "checkout_completed",
            "customer_linked": "customer_linked",
            # Recommendation events
            "recommendation_viewed": "recommendation_viewed",
            "recommendation_clicked": "recommendation_clicked",
            "recommendation_add_to_cart": "recommendation_add_to_cart",
            # Post-purchase events
            "upsell_viewed": "recommendation_viewed",
            "upsell_clicked": "recommendation_clicked",
            "upsell_add_to_cart": "recommendation_add_to_cart",
            # Cross-sell events
            "cross_sell_viewed": "recommendation_viewed",
            "cross_sell_clicked": "recommendation_clicked",
            "cross_sell_add_to_cart": "recommendation_add_to_cart",
        }
        return interaction_mapping.get(event_name, "page_viewed")

    def _build_recommendation_data(
        self,
        extension_type: str,
        context: str,
        recommended_indices: List[int],
        product_variant_ids: List[str],
    ) -> Dict[str, Any]:
        """Build recommendation event data."""
        recommended_products = []
        for idx in recommended_indices:
            if idx < len(product_variant_ids):
                recommended_products.append(
                    {
                        "productId": product_variant_ids[idx],
                        "variantId": product_variant_ids[idx],
                        "title": f"Recommended Product {idx + 1}",
                        "price": f"${(idx + 1) * 25}.00",
                        "image": f"https://example.com/product{idx + 1}.jpg",
                    }
                )

        return {
            "extensionType": extension_type,
            "context": context,
            "recommendedProducts": recommended_products,
            "recommendationEngine": "phoenix",
            "algorithm": "collaborative_filtering",
            "confidence": 0.85,
        }

    def _build_recommendation_click_data(
        self, product_index: int, product_variant_ids: List[str]
    ) -> Dict[str, Any]:
        """Build recommendation click event data."""
        return {
            "clickedProduct": {
                "productId": product_variant_ids[product_index],
                "variantId": product_variant_ids[product_index],
                "title": f"Recommended Product {product_index + 1}",
                "price": f"${(product_index + 1) * 25}.00",
            },
            "recommendationContext": "product_page",
            "position": product_index + 1,
            "clickThroughRate": 0.12,
        }

    def _build_upsell_data(
        self,
        extension_type: str,
        context: str,
        upsell_indices: List[int],
        product_variant_ids: List[str],
    ) -> Dict[str, Any]:
        """Build upsell event data for Apollo."""
        upsell_products = []
        for idx in upsell_indices:
            if idx < len(product_variant_ids):
                upsell_products.append(
                    {
                        "productId": product_variant_ids[idx],
                        "variantId": product_variant_ids[idx],
                        "title": f"Upsell Product {idx + 1}",
                        "price": f"${(idx + 1) * 50}.00",
                        "discount": "20% off",
                    }
                )

        return {
            "extensionType": extension_type,
            "context": context,
            "upsellProducts": upsell_products,
            "recommendationEngine": "apollo",
            "algorithm": "post_purchase_upsell",
            "confidence": 0.75,
        }

    def _build_cross_sell_data(
        self,
        extension_type: str,
        context: str,
        cross_sell_indices: List[int],
        product_variant_ids: List[str],
    ) -> Dict[str, Any]:
        """Build cross-sell event data for Venus."""
        cross_sell_products = []
        for idx in cross_sell_indices:
            if idx < len(product_variant_ids):
                cross_sell_products.append(
                    {
                        "productId": product_variant_ids[idx],
                        "variantId": product_variant_ids[idx],
                        "title": f"Cross-sell Product {idx + 1}",
                        "price": f"${(idx + 1) * 30}.00",
                        "category": "accessories",
                    }
                )

        return {
            "extensionType": extension_type,
            "context": context,
            "crossSellProducts": cross_sell_products,
            "recommendationEngine": "venus",
            "algorithm": "frequently_bought_together",
            "confidence": 0.68,
        }

    def _build_product_view_data(
        self, product_index: int, product_variant_ids: List[str]
    ) -> Dict[str, Any]:
        """Build product view event data."""
        product_titles = [
            "Premium Cotton Hoodie",
            "Classic V-Neck T-Shirt",
            "Slim Fit Jeans",
            "Athletic Shorts",
            "Wool Blend Sweater",
            "Designer Sunglasses",
            "Leather Crossbody Bag",
            "Silk Scarf",
            "Leather Belt",
            "Baseball Cap",
            "Wireless Earbuds Pro",
            "Smart Watch",
            "Phone Case",
            "Portable Charger",
            "Bluetooth Speaker",
        ]

        prices = [
            45.00,
            25.00,
            60.00,
            30.00,
            70.00,
            60.00,
            80.00,
            40.00,
            35.00,
            20.00,
            100.00,
            150.00,
            18.00,
            40.00,
            60.00,
        ]

        return {
            "productVariant": {
                "id": product_variant_ids[product_index],
                "title": "Default Title",
                "price": {"amount": prices[product_index], "currencyCode": "USD"},
                "product": {
                    "id": self.dynamic_ids[f"product_{product_index + 1}_id"],
                    "title": product_titles[product_index],
                    "vendor": self.get_vendor(
                        self.get_product_category(product_index + 1)
                    ),
                },
            }
        }

    def _build_cart_data(
        self, product_index: int, product_variant_ids: List[str]
    ) -> Dict[str, Any]:
        """Build cart event data."""
        product_view_data = self._build_product_view_data(
            product_index, product_variant_ids
        )
        price = product_view_data["productVariant"]["price"]["amount"]

        return {
            "cartLine": {
                "merchandise": product_view_data["productVariant"],
                "quantity": 1,
                "cost": {"totalAmount": {"amount": price, "currencyCode": "USD"}},
            }
        }

    def _build_cart_view_data(
        self, product_indices: List[int], product_variant_ids: List[str]
    ) -> Dict[str, Any]:
        """Build cart view event data."""
        lines = []
        total_amount = 0.0

        for product_index in product_indices:
            cart_data = self._build_cart_data(product_index, product_variant_ids)
            lines.append(cart_data["cartLine"])
            total_amount += cart_data["cartLine"]["cost"]["totalAmount"]["amount"]

        return {
            "cart": {
                "id": f"cart_{self.generate_client_id()}",
                "totalQuantity": len(product_indices),
                "cost": {
                    "totalAmount": {"amount": total_amount, "currencyCode": "USD"}
                },
                "lines": lines,
            }
        }

    def _build_checkout_data(
        self, product_indices: List[int], product_variant_ids: List[str]
    ) -> Dict[str, Any]:
        """Build checkout started event data."""
        lines = []
        total_amount = 0.0

        for product_index in product_indices:
            cart_data = self._build_cart_data(product_index, product_variant_ids)
            line_item = {
                "id": f"line_item_{product_index}",
                "title": cart_data["cartLine"]["merchandise"]["product"]["title"],
                "quantity": cart_data["cartLine"]["quantity"],
                "finalLinePrice": cart_data["cartLine"]["cost"]["totalAmount"],
                "variant": cart_data["cartLine"]["merchandise"],
            }
            lines.append(line_item)
            total_amount += cart_data["cartLine"]["cost"]["totalAmount"]["amount"]

        return {
            "checkout": {
                "id": f"gid://shopify/Checkout/{self.generate_client_id()}",
                "totalPrice": {"amount": total_amount, "currencyCode": "USD"},
                "lineItems": lines,
            }
        }

    def _build_checkout_completed_data(
        self, product_indices: List[int], product_variant_ids: List[str]
    ) -> Dict[str, Any]:
        """Build checkout completed event data."""
        checkout_data = self._build_checkout_data(product_indices, product_variant_ids)
        checkout_data["checkout"]["order"] = {
            "id": f"gid://shopify/Order/{self.generate_client_id()}"
        }
        return checkout_data

    def _build_collection_data(
        self,
        collection_handle: str,
        product_indices: List[int],
        product_variant_ids: List[str],
    ) -> Dict[str, Any]:
        """Build collection view event data."""
        collection_id = self.dynamic_ids.get(
            f"collection_{collection_handle.split('-')[0]}_id",
            self.dynamic_ids["collection_1_id"],
        )

        product_variants = []
        for product_index in product_indices:
            product_view_data = self._build_product_view_data(
                product_index, product_variant_ids
            )
            product_variants.append(product_view_data["productVariant"])

        return {
            "collection": {
                "id": collection_id,
                "title": collection_handle.replace("-", " ").title(),
                "productVariants": product_variants,
            }
        }
