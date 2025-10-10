"""
Base generator class with common utilities for seed data generation.
"""

import uuid
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List


class BaseGenerator:
    """Base class for all data generators with common utilities."""

    def __init__(self, shop_domain: str = "fashion-store.myshopify.com"):
        self.shop_domain = shop_domain
        self.base_id = random.randint(10000, 99999)
        self.dynamic_ids = self._generate_dynamic_ids()

    def _generate_dynamic_ids(self) -> Dict[str, str]:
        """Generate unique IDs for this run to avoid conflicts."""
        ids = {
            "shop_id": f"cmfb{self.base_id:05d}00000v3dhw8juz526",
            "collection_1_id": f"gid://shopify/Collection/{self.base_id + 3001}",
            "collection_2_id": f"gid://shopify/Collection/{self.base_id + 3002}",
            "collection_3_id": f"gid://shopify/Collection/{self.base_id + 3003}",
        }

        # Products (50 total for more variety and better recommendations)
        for i in range(1, 51):
            ids[f"product_{i}_id"] = f"gid://shopify/Product/{self.base_id + i}"
            ids[f"variant_{i}_id"] = (
                f"gid://shopify/ProductVariant/{self.base_id + 1000 + i}"
            )

        # Customers (25 total for more diverse user base and interactions)
        for i in range(1, 26):
            ids[f"customer_{i}_id"] = (
                f"gid://shopify/Customer/{self.base_id + 5000 + i}"
            )

        # Orders (40 total for more purchase patterns and feedback)
        for i in range(1, 41):
            ids[f"order_{i}_id"] = f"gid://shopify/Order/{self.base_id + 7000 + i}"

        # Line items (multiple per order - increased for more feedback)
        for i in range(1, 100):  # Up to 2-3 per order, more line items
            ids[f"line_item_{i}_id"] = (
                f"gid://shopify/LineItem/{self.base_id + 8000 + i}"
            )

        return ids

    def now_utc(self) -> datetime:
        """Get current UTC datetime."""
        return datetime.now(timezone.utc)

    def past_date(self, days_ago: int) -> datetime:
        """Get a date N days ago."""
        return self.now_utc() - timedelta(days=days_ago)

    def random_past_date(self, min_days: int = 1, max_days: int = 30) -> datetime:
        """Get a random date between min_days and max_days ago."""
        days_ago = random.randint(min_days, max_days)
        return self.past_date(days_ago)

    def generate_client_id(self) -> str:
        """Generate a unique client ID."""
        return str(uuid.uuid4())

    def get_product_category(self, product_index: int) -> str:
        """Get product category based on index."""
        if product_index <= 5:
            return "Clothing"
        elif product_index <= 10:
            return "Accessories"
        else:
            return "Electronics"

    def get_vendor(self, category: str) -> str:
        """Get vendor based on category."""
        vendors = {
            "Clothing": "Fashion Co",
            "Accessories": "Style Co",
            "Electronics": "Tech Co",
        }
        return vendors.get(category, "Generic Co")

    def get_price_range(self, category: str) -> tuple:
        """Get price range for category."""
        price_ranges = {
            "Clothing": (15, 80),
            "Accessories": (10, 60),
            "Electronics": (20, 150),
        }
        return price_ranges.get(category, (10, 50))

    def get_inventory_range(self, category: str) -> tuple:
        """Get inventory range for category."""
        inventory_ranges = {
            "Clothing": (5, 25),
            "Accessories": (3, 20),
            "Electronics": (2, 15),
        }
        return inventory_ranges.get(category, (1, 10))
