"""
Test Data Generator for Attribution Scenarios

This module generates realistic test data for all attribution scenarios
without requiring frontend interaction. It creates mock data that
simulates real user behavior and system states.
"""

import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional
import json


class AttributionTestDataGenerator:
    """Generates realistic test data for attribution scenarios"""

    def __init__(self):
        self.extensions = ["phoenix", "venus", "apollo", "atlas"]
        self.interaction_types = [
            "recommendation_clicked",
            "recommendation_add_to_cart",
            "product_viewed",
            "product_shared",
            "recommendation_ignored",
        ]
        self.device_types = ["mobile", "desktop", "tablet"]
        self.operating_systems = ["ios", "android", "windows", "macos", "linux"]
        self.user_agents = [
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Mozilla/5.0 (Android 10; Mobile; rv:68.0) Gecko/68.0 Firefox/68.0",
        ]

    def generate_customer_data(self, customer_id: str = None) -> Dict[str, Any]:
        """Generate realistic customer data"""
        return {
            "customer_id": customer_id or f"customer_{random.randint(1000, 9999)}",
            "email": f"customer{random.randint(100, 999)}@example.com",
            "first_name": random.choice(
                ["Sarah", "John", "Emma", "Michael", "Lisa", "David"]
            ),
            "last_name": random.choice(
                ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia"]
            ),
            "created_at": datetime.now() - timedelta(days=random.randint(1, 365)),
            "total_orders": random.randint(1, 50),
            "total_spent": Decimal(str(random.uniform(100, 5000))),
            "loyalty_tier": random.choice(["bronze", "silver", "gold", "platinum"]),
        }

    def generate_shop_data(self, shop_id: str = None) -> Dict[str, Any]:
        """Generate realistic shop data"""
        return {
            "shop_id": shop_id or f"shop_{random.randint(100, 999)}",
            "shop_name": f"Test Shop {random.randint(1, 100)}",
            "domain": f"testshop{random.randint(1, 100)}.myshopify.com",
            "currency": random.choice(["USD", "EUR", "GBP", "CAD", "AUD"]),
            "timezone": random.choice(["UTC", "EST", "PST", "GMT"]),
            "plan": random.choice(["basic", "shopify", "advanced", "plus"]),
        }

    def generate_product_data(self, product_id: str = None) -> Dict[str, Any]:
        """Generate realistic product data"""
        categories = ["electronics", "clothing", "home", "beauty", "sports", "books"]
        return {
            "product_id": product_id or f"product_{random.randint(1000, 9999)}",
            "title": f"Test Product {random.randint(1, 1000)}",
            "category": random.choice(categories),
            "price": Decimal(str(random.uniform(10, 500))),
            "compare_at_price": Decimal(str(random.uniform(20, 600))),
            "inventory_quantity": random.randint(0, 100),
            "tags": random.sample(
                ["new", "sale", "featured", "trending", "limited"], random.randint(1, 3)
            ),
            "vendor": f"Vendor {random.randint(1, 50)}",
            "product_type": random.choice(["physical", "digital", "service"]),
        }

    def generate_session_data(
        self, session_id: str = None, customer_id: str = None
    ) -> Dict[str, Any]:
        """Generate realistic session data"""
        device_type = random.choice(self.device_types)
        os = random.choice(self.operating_systems)
        user_agent = random.choice(self.user_agents)

        return {
            "session_id": session_id or f"session_{random.randint(10000, 99999)}",
            "customer_id": customer_id,
            "shop_id": f"shop_{random.randint(100, 999)}",
            "browser_session_id": f"browser_{random.randint(1000, 9999)}",
            "client_id": f"client_{random.randint(100, 999)}",
            "user_agent": user_agent,
            "ip_address": f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}",
            "referrer": random.choice(
                [
                    "https://google.com",
                    "https://facebook.com",
                    "https://instagram.com",
                    "https://twitter.com",
                    None,
                ]
            ),
            "device_type": device_type,
            "operating_system": os,
            "created_at": datetime.now() - timedelta(hours=random.randint(1, 24)),
            "last_active": datetime.now() - timedelta(minutes=random.randint(1, 60)),
            "expires_at": datetime.now() + timedelta(hours=24),
            "status": "active",
        }

    def generate_interaction_data(
        self, interaction_id: str = None, product_id: str = None
    ) -> Dict[str, Any]:
        """Generate realistic interaction data"""
        interaction_type = random.choice(self.interaction_types)
        extension = random.choice(self.extensions)

        return {
            "id": interaction_id or f"interaction_{random.randint(100000, 999999)}",
            "session_id": f"session_{random.randint(10000, 99999)}",
            "product_id": product_id or f"product_{random.randint(1000, 9999)}",
            "extension_type": extension,
            "interaction_type": interaction_type,
            "created_at": datetime.now() - timedelta(minutes=random.randint(1, 1440)),
            "metadata": {
                "position": random.randint(1, 10),
                "confidence": random.uniform(0.1, 1.0),
                "recommendation_id": f"rec_{random.randint(1000, 9999)}",
                "page_url": f"https://shop.com/products/product_{random.randint(1, 100)}",
                "user_behavior": random.choice(
                    ["engaged", "browsing", "purchasing", "leaving"]
                ),
                "time_on_page": random.randint(5, 300),  # seconds
                "scroll_depth": random.uniform(0.1, 1.0),
                "click_coordinates": {
                    "x": random.randint(0, 1920),
                    "y": random.randint(0, 1080),
                },
            },
        }

    def generate_order_data(
        self, order_id: str = None, customer_id: str = None
    ) -> Dict[str, Any]:
        """Generate realistic order data"""
        order_amount = Decimal(str(random.uniform(25, 1000)))
        tax_rate = Decimal("0.08")  # 8% tax
        tax_amount = order_amount * tax_rate
        total_amount = order_amount + tax_amount

        return {
            "order_id": order_id or f"order_{random.randint(100000, 999999)}",
            "customer_id": customer_id or f"customer_{random.randint(1000, 9999)}",
            "shop_id": f"shop_{random.randint(100, 999)}",
            "session_id": f"session_{random.randint(10000, 99999)}",
            "order_number": f"#{random.randint(1000, 9999)}",
            "total_price": str(total_amount),
            "subtotal_price": str(order_amount),
            "total_tax": str(tax_amount),
            "currency_code": random.choice(["USD", "EUR", "GBP", "CAD"]),
            "financial_status": random.choice(["PAID", "PENDING", "PARTIALLY_PAID"]),
            "fulfillment_status": random.choice(
                ["UNFULFILLED", "PARTIALLY_FULFILLED", "FULFILLED"]
            ),
            "created_at": datetime.now() - timedelta(hours=random.randint(1, 24)),
            "processed_at": datetime.now() - timedelta(hours=random.randint(1, 24)),
            "tags": random.sample(["test", "online", "priority"], random.randint(1, 3)),
            "note": random.choice(
                [None, "Special instructions", "Gift wrapping requested"]
            ),
            "test": random.choice([True, False]),
        }

    def generate_line_item_data(self, product_id: str = None) -> Dict[str, Any]:
        """Generate realistic line item data"""
        quantity = random.randint(1, 5)
        unit_price = Decimal(str(random.uniform(10, 200)))
        total_price = unit_price * quantity

        return {
            "id": f"line_item_{random.randint(100000, 999999)}",
            "product_id": product_id or f"product_{random.randint(1000, 9999)}",
            "variant_id": f"variant_{random.randint(10000, 99999)}",
            "title": f"Test Product {random.randint(1, 1000)}",
            "quantity": quantity,
            "unit_price": str(unit_price),
            "total_price": str(total_price),
            "sku": f"SKU-{random.randint(1000, 9999)}",
            "vendor": f"Vendor {random.randint(1, 50)}",
            "requires_shipping": random.choice([True, False]),
            "taxable": random.choice([True, False]),
        }

    def generate_attribution_context(self, scenario_name: str) -> Dict[str, Any]:
        """Generate attribution context for specific scenarios"""
        base_context = {
            "order_id": f"order_{scenario_name}_{random.randint(1000, 9999)}",
            "shop_id": f"shop_{random.randint(100, 999)}",
            "customer_id": f"customer_{random.randint(1000, 9999)}",
            "session_id": f"session_{random.randint(10000, 99999)}",
            "purchase_amount": Decimal(str(random.uniform(25, 1000))),
            "purchase_products": [
                {
                    "id": f"product_{random.randint(1000, 9999)}",
                    "quantity": random.randint(1, 3),
                    "price": random.uniform(10, 200),
                }
            ],
            "metadata": {},
        }

        # Add scenario-specific metadata
        if scenario_name == "payment_failure":
            base_context["metadata"] = {
                "financial_status": "VOIDED",
                "payment_status": "declined",
                "error_message": "Card declined - insufficient funds",
            }
        elif scenario_name == "subscription_cancellation":
            base_context["metadata"] = {
                "subscription_status": "cancelled",
                "cancelled_at": datetime.now().isoformat(),
            }
        elif scenario_name == "cross_shop":
            base_context["metadata"] = {
                "recommendation_shop_id": f"shop_{random.randint(100, 999)}",
                "cross_shop_attribution": True,
            }
        elif scenario_name == "low_quality":
            base_context["metadata"] = {
                "recommendation_quality_score": random.uniform(0.1, 0.3),
                "ignored_recommendations": random.randint(3, 10),
                "direct_search_after_recommendations": True,
                "recommendation_ctr": random.uniform(0.01, 0.1),
            }
        elif scenario_name == "poor_timing":
            base_context["metadata"] = {
                "recommendation_timestamp": (
                    datetime.now() - timedelta(days=2)
                ).isoformat(),
                "purchase_timestamp": datetime.now().isoformat(),
                "session_duration_minutes": random.randint(1, 10),
                "time_to_purchase_minutes": random.randint(1440, 4320),  # 1-3 days
                "user_activity_level": "low",
            }
        elif scenario_name == "data_loss":
            base_context["customer_id"] = None
            base_context["session_id"] = None
            base_context["purchase_amount"] = Decimal("0.00")
            base_context["purchase_products"] = []
            base_context["metadata"] = {}
        elif scenario_name == "fraudulent":
            base_context["user_agent"] = (
                "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
            )
            base_context["metadata"] = {
                "suspicious_activity": True,
                "bot_indicators": ["crawler", "spider"],
            }
        elif scenario_name == "manipulation":
            base_context["metadata"] = {
                "coordinated_activity": True,
                "timing_anomalies": True,
                "interaction_inflation": True,
                "attribution_gaming": True,
            }

        return base_context

    def generate_interaction_sequence(self, count: int = 10) -> List[Dict[str, Any]]:
        """Generate a sequence of interactions for testing"""
        interactions = []
        product_ids = [f"product_{i}" for i in range(1, 6)]  # 5 products

        for i in range(count):
            interaction = self.generate_interaction_data(
                product_id=random.choice(product_ids)
            )
            # Make interactions more realistic by adjusting timestamps
            interaction["created_at"] = datetime.now() - timedelta(minutes=i * 15)
            interactions.append(interaction)

        return interactions

    def generate_multi_device_scenario(self) -> Dict[str, Any]:
        """Generate multi-device scenario data"""
        customer_id = f"customer_{random.randint(1000, 9999)}"

        # Mobile session
        mobile_session = self.generate_session_data(customer_id=customer_id)
        mobile_session.update(
            {
                "device_type": "mobile",
                "operating_system": "ios",
                "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15",
            }
        )

        # Desktop session
        desktop_session = self.generate_session_data(customer_id=customer_id)
        desktop_session.update(
            {
                "device_type": "desktop",
                "operating_system": "macos",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            }
        )

        return {
            "customer_id": customer_id,
            "sessions": [mobile_session, desktop_session],
            "interactions": self.generate_interaction_sequence(8),
            "order": self.generate_order_data(customer_id=customer_id),
        }

    def generate_anonymous_to_customer_scenario(self) -> Dict[str, Any]:
        """Generate anonymous to customer conversion scenario"""
        customer_id = f"customer_{random.randint(1000, 9999)}"

        # Anonymous sessions (before login)
        anonymous_sessions = []
        for i in range(3):
            session = self.generate_session_data()
            session["customer_id"] = None  # Anonymous
            session["created_at"] = datetime.now() - timedelta(hours=i + 1)
            anonymous_sessions.append(session)

        # Conversion session (after login)
        conversion_session = self.generate_session_data(customer_id=customer_id)
        conversion_session["created_at"] = datetime.now()

        return {
            "customer_id": customer_id,
            "anonymous_sessions": anonymous_sessions,
            "conversion_session": conversion_session,
            "interactions": self.generate_interaction_sequence(15),
            "order": self.generate_order_data(customer_id=customer_id),
        }

    def generate_refund_scenario(self) -> Dict[str, Any]:
        """Generate refund scenario data"""
        order = self.generate_order_data()
        refund_amount = Decimal(
            str(random.uniform(10, float(order["total_price"]) * 0.5))
        )

        return {
            "order": order,
            "refund": {
                "id": f"refund_{random.randint(100000, 999999)}",
                "order_id": order["order_id"],
                "total_refund_amount": str(refund_amount),
                "created_at": datetime.now().isoformat(),
                "currency_code": order["currency_code"],
                "reason": random.choice(
                    [
                        "customer_request",
                        "defective_product",
                        "wrong_item",
                        "not_as_described",
                    ]
                ),
            },
            "original_attribution": {
                "total_revenue": float(order["total_price"]),
                "attribution_weights": {"phoenix": 0.6, "venus": 0.3, "apollo": 0.1},
                "contributing_extensions": ["phoenix", "venus", "apollo"],
                "total_interactions": random.randint(5, 20),
            },
        }

    def save_test_data(self, filename: str = "attribution_test_data.json"):
        """Save generated test data to file"""
        test_data = {
            "customers": [self.generate_customer_data() for _ in range(5)],
            "shops": [self.generate_shop_data() for _ in range(3)],
            "products": [self.generate_product_data() for _ in range(10)],
            "sessions": [self.generate_session_data() for _ in range(8)],
            "interactions": self.generate_interaction_sequence(50),
            "orders": [self.generate_order_data() for _ in range(5)],
            "scenarios": {
                "payment_failure": self.generate_attribution_context("payment_failure"),
                "subscription_cancellation": self.generate_attribution_context(
                    "subscription_cancellation"
                ),
                "cross_shop": self.generate_attribution_context("cross_shop"),
                "low_quality": self.generate_attribution_context("low_quality"),
                "poor_timing": self.generate_attribution_context("poor_timing"),
                "data_loss": self.generate_attribution_context("data_loss"),
                "fraudulent": self.generate_attribution_context("fraudulent"),
                "manipulation": self.generate_attribution_context("manipulation"),
            },
            "multi_device": self.generate_multi_device_scenario(),
            "anonymous_conversion": self.generate_anonymous_to_customer_scenario(),
            "refund": self.generate_refund_scenario(),
        }

        with open(filename, "w") as f:
            json.dump(test_data, f, indent=2, default=str)

        print(f"✅ Test data saved to: {filename}")
        return test_data


def main():
    """Generate and save test data"""
    generator = AttributionTestDataGenerator()
    test_data = generator.save_test_data()

    print(f"📊 Generated test data:")
    print(f"  - Customers: {len(test_data['customers'])}")
    print(f"  - Shops: {len(test_data['shops'])}")
    print(f"  - Products: {len(test_data['products'])}")
    print(f"  - Sessions: {len(test_data['sessions'])}")
    print(f"  - Interactions: {len(test_data['interactions'])}")
    print(f"  - Orders: {len(test_data['orders'])}")
    print(f"  - Scenarios: {len(test_data['scenarios'])}")
    print(f"  - Multi-device scenario: ✅")
    print(f"  - Anonymous conversion scenario: ✅")
    print(f"  - Refund scenario: ✅")


if __name__ == "__main__":
    main()
