"""
Customer data generator for creating realistic customer profiles.
"""

import random
from typing import Dict, Any, List
from .base_generator import BaseGenerator


class CustomerGenerator(BaseGenerator):
    """Generates realistic customer data with diverse profiles."""

    def generate_customers(self) -> List[Dict[str, Any]]:
        """Generate 15 diverse customer profiles."""
        customer_profiles = [
            {
                "name": "Alice Johnson",
                "email": "alice.johnson@email.com",
                "profile_type": "vip_customer",
                "total_spent": 450.00,
                "orders_count": 8,
                "tags": ["vip", "repeat-buyer", "high-value"],
                "created_days_ago": 120,
                "last_order_days_ago": 3,
                "preferred_categories": ["Clothing", "Accessories"],
                "avg_order_value": 56.25,
            },
            {
                "name": "Bob Smith",
                "email": "bob.smith@email.com",
                "profile_type": "new_customer",
                "total_spent": 0.00,
                "orders_count": 0,
                "tags": ["new", "browser-only"],
                "created_days_ago": 5,
                "last_order_days_ago": None,
                "preferred_categories": ["Electronics"],
                "avg_order_value": 0.00,
            },
            {
                "name": "Charlie Brown",
                "email": "charlie.brown@email.com",
                "profile_type": "moderate_buyer",
                "total_spent": 180.00,
                "orders_count": 3,
                "tags": ["moderate", "electronics-focused"],
                "created_days_ago": 60,
                "last_order_days_ago": 7,
                "preferred_categories": ["Electronics", "Accessories"],
                "avg_order_value": 60.00,
            },
            {
                "name": "Dana Lee",
                "email": "dana.lee@email.com",
                "profile_type": "abandoned_cart",
                "total_spent": 0.00,
                "orders_count": 0,
                "tags": ["abandoned-cart", "price-sensitive"],
                "created_days_ago": 15,
                "last_order_days_ago": None,
                "preferred_categories": ["Clothing", "Accessories"],
                "avg_order_value": 0.00,
            },
            {
                "name": "Eve Adams",
                "email": "eve.adams@email.com",
                "profile_type": "cross_category",
                "total_spent": 320.00,
                "orders_count": 5,
                "tags": ["cross-category", "fashion-forward"],
                "created_days_ago": 90,
                "last_order_days_ago": 2,
                "preferred_categories": ["Clothing", "Accessories", "Electronics"],
                "avg_order_value": 64.00,
            },
            {
                "name": "Frank Wilson",
                "email": "frank.wilson@email.com",
                "profile_type": "tech_enthusiast",
                "total_spent": 280.00,
                "orders_count": 4,
                "tags": ["tech-enthusiast", "early-adopter"],
                "created_days_ago": 75,
                "last_order_days_ago": 5,
                "preferred_categories": ["Electronics"],
                "avg_order_value": 70.00,
            },
            {
                "name": "Grace Taylor",
                "email": "grace.taylor@email.com",
                "profile_type": "fashion_lover",
                "total_spent": 220.00,
                "orders_count": 6,
                "tags": ["fashion-lover", "trendy"],
                "created_days_ago": 45,
                "last_order_days_ago": 1,
                "preferred_categories": ["Clothing", "Accessories"],
                "avg_order_value": 36.67,
            },
            {
                "name": "Henry Davis",
                "email": "henry.davis@email.com",
                "profile_type": "bargain_hunter",
                "total_spent": 95.00,
                "orders_count": 3,
                "tags": ["bargain-hunter", "sale-focused"],
                "created_days_ago": 30,
                "last_order_days_ago": 8,
                "preferred_categories": ["Clothing", "Accessories"],
                "avg_order_value": 31.67,
            },
            {
                "name": "Isabella Martinez",
                "email": "isabella.martinez@email.com",
                "profile_type": "wellness_enthusiast",
                "total_spent": 180.00,
                "orders_count": 4,
                "tags": ["wellness", "health-focused", "yoga"],
                "created_days_ago": 45,
                "last_order_days_ago": 3,
                "preferred_categories": ["Sports & Fitness", "Home & Garden"],
                "avg_order_value": 45.00,
            },
            {
                "name": "James Wilson",
                "email": "james.wilson@email.com",
                "profile_type": "home_improver",
                "total_spent": 320.00,
                "orders_count": 6,
                "tags": ["home-improvement", "diy", "gardening"],
                "created_days_ago": 80,
                "last_order_days_ago": 2,
                "preferred_categories": ["Home & Garden", "Electronics"],
                "avg_order_value": 53.33,
            },
            {
                "name": "Sophia Chen",
                "email": "sophia.chen@email.com",
                "profile_type": "luxury_buyer",
                "total_spent": 850.00,
                "orders_count": 5,
                "tags": ["luxury", "high-end", "premium"],
                "created_days_ago": 100,
                "last_order_days_ago": 1,
                "preferred_categories": ["Clothing", "Accessories", "Electronics"],
                "avg_order_value": 170.00,
            },
            {
                "name": "Michael Rodriguez",
                "email": "michael.rodriguez@email.com",
                "profile_type": "gift_buyer",
                "total_spent": 240.00,
                "orders_count": 8,
                "tags": ["gift-buyer", "holiday-shopper", "seasonal"],
                "created_days_ago": 60,
                "last_order_days_ago": 4,
                "preferred_categories": ["Accessories", "Home & Garden"],
                "avg_order_value": 30.00,
            },
            {
                "name": "Emma Thompson",
                "email": "emma.thompson@email.com",
                "profile_type": "student_budget",
                "total_spent": 75.00,
                "orders_count": 4,
                "tags": ["student", "budget-conscious", "young"],
                "created_days_ago": 25,
                "last_order_days_ago": 6,
                "preferred_categories": ["Clothing", "Accessories"],
                "avg_order_value": 18.75,
            },
            {
                "name": "David Kim",
                "email": "david.kim@email.com",
                "profile_type": "professional_worker",
                "total_spent": 420.00,
                "orders_count": 7,
                "tags": ["professional", "business", "work-wear"],
                "created_days_ago": 90,
                "last_order_days_ago": 2,
                "preferred_categories": ["Clothing", "Electronics"],
                "avg_order_value": 60.00,
            },
        ]

        return self._build_customer_payloads(customer_profiles)

    def _build_customer_payloads(
        self, customer_configs: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Build complete customer payloads from configurations."""
        customers = []

        for i, config in enumerate(customer_configs, 1):
            customer_id = self.dynamic_ids[f"customer_{i}_id"]

            # Split name into first and last
            name_parts = config["name"].split(" ", 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            # Generate customer state based on profile
            customer_state = self._get_customer_state(config["profile_type"])

            # Generate verification status
            verified_email = config["total_spent"] > 0 or config["profile_type"] in [
                "vip_customer",
                "moderate_buyer",
            ]

            # Generate default address for customers with orders
            default_address = None
            if config["orders_count"] > 0:
                default_address = self._generate_default_address()

            customer_payload = {
                "id": customer_id,
                "email": config["email"],
                "firstName": first_name,
                "lastName": last_name,
                "displayName": config["name"],
                "totalSpent": str(config["total_spent"]),
                "ordersCount": config["orders_count"],
                "state": customer_state,
                "verifiedEmail": verified_email,
                "defaultAddress": default_address,
                "createdAt": self.past_date(config["created_days_ago"]).isoformat(),
                "updatedAt": self.past_date(config["created_days_ago"]).isoformat(),
                "tags": config["tags"],
            }

            customers.append(customer_payload)

        return customers

    def _get_customer_state(self, profile_type: str) -> str:
        """Get customer state based on profile type."""
        state_mapping = {
            "vip_customer": "ENABLED",
            "new_customer": "ENABLED",
            "moderate_buyer": "ENABLED",
            "abandoned_cart": "ENABLED",
            "cross_category": "ENABLED",
            "tech_enthusiast": "ENABLED",
            "fashion_lover": "ENABLED",
            "bargain_hunter": "ENABLED",
        }
        return state_mapping.get(profile_type, "ENABLED")

    def _generate_default_address(self) -> Dict[str, str]:
        """Generate a realistic default address."""
        addresses = [
            {
                "address1": "123 Main Street",
                "city": "New York",
                "province": "New York",
                "country": "United States",
                "zip": "10001",
                "phone": "+1-555-0123",
                "provinceCode": "NY",
                "countryCodeV2": "US",
            },
            {
                "address1": "456 Oak Avenue",
                "city": "Los Angeles",
                "province": "California",
                "country": "United States",
                "zip": "90210",
                "phone": "+1-555-0456",
                "provinceCode": "CA",
                "countryCodeV2": "US",
            },
            {
                "address1": "789 Pine Road",
                "city": "Chicago",
                "province": "Illinois",
                "country": "United States",
                "zip": "60601",
                "phone": "+1-555-0789",
                "provinceCode": "IL",
                "countryCodeV2": "US",
            },
            {
                "address1": "321 Elm Street",
                "city": "Houston",
                "province": "Texas",
                "country": "United States",
                "zip": "77001",
                "phone": "+1-555-0321",
                "provinceCode": "TX",
                "countryCodeV2": "US",
            },
        ]

        return random.choice(addresses)
