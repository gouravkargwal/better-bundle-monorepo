#!/usr/bin/env python3
"""
Base Data Generator - Common utilities for all data generators
"""

import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any


class BaseDataGenerator:
    """Base class with common utilities for generating test data"""

    def __init__(self):
        # Realistic data pools
        self.first_names = [
            "Emma",
            "Liam",
            "Olivia",
            "Noah",
            "Ava",
            "William",
            "Sophia",
            "James",
            "Isabella",
            "Benjamin",
            "Charlotte",
            "Lucas",
            "Amelia",
            "Henry",
            "Mia",
            "Alexander",
            "Harper",
            "Mason",
            "Evelyn",
            "Michael",
            "Abigail",
            "Ethan",
            "Emily",
            "Daniel",
            "Elizabeth",
            "Jacob",
            "Sofia",
            "Logan",
            "Avery",
            "Jackson",
        ]

        self.last_names = [
            "Smith",
            "Johnson",
            "Williams",
            "Brown",
            "Jones",
            "Garcia",
            "Miller",
            "Davis",
            "Rodriguez",
            "Martinez",
            "Hernandez",
            "Lopez",
            "Gonzalez",
            "Wilson",
            "Anderson",
            "Thomas",
            "Taylor",
            "Moore",
            "Jackson",
            "Martin",
            "Lee",
            "Perez",
            "Thompson",
            "White",
            "Harris",
            "Sanchez",
            "Clark",
            "Ramirez",
        ]

        self.cities = [
            "New York",
            "Los Angeles",
            "Chicago",
            "Houston",
            "Phoenix",
            "Philadelphia",
            "San Antonio",
            "San Diego",
            "Dallas",
            "San Jose",
            "Austin",
            "Jacksonville",
            "Fort Worth",
            "Columbus",
            "Charlotte",
            "San Francisco",
            "Indianapolis",
            "Seattle",
            "Denver",
            "Washington",
            "Boston",
            "El Paso",
            "Nashville",
            "Detroit",
        ]

        self.states = [
            "NY",
            "CA",
            "IL",
            "TX",
            "AZ",
            "PA",
            "FL",
            "OH",
            "NC",
            "GA",
            "MI",
            "NJ",
            "VA",
            "WA",
            "MA",
            "TN",
            "IN",
            "MO",
            "MD",
            "WI",
            "CO",
            "MN",
            "SC",
            "AL",
        ]

        self.product_categories = [
            "Electronics",
            "Clothing",
            "Home & Garden",
            "Sports",
            "Books",
            "Beauty",
            "Toys",
            "Automotive",
            "Health",
            "Food",
            "Jewelry",
            "Shoes",
            "Bags",
            "Furniture",
            "Kitchen",
            "Outdoor",
            "Baby",
            "Pet",
            "Office",
            "Art",
        ]

        self.brands = [
            "Nike",
            "Apple",
            "Samsung",
            "Adidas",
            "Sony",
            "Microsoft",
            "Google",
            "Amazon",
            "Tesla",
            "Coca-Cola",
            "McDonald's",
            "Disney",
            "Netflix",
            "Spotify",
            "Uber",
            "Airbnb",
            "Instagram",
            "Facebook",
            "Twitter",
            "LinkedIn",
        ]

    def generate_shopify_id(self) -> str:
        """Generate a realistic Shopify ID"""
        return str(random.randint(1000000000000, 9999999999999))

    def generate_email(self, first_name: str, last_name: str) -> str:
        """Generate a realistic email address"""
        domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"]
        return f"{first_name.lower()}.{last_name.lower()}@{random.choice(domains)}"

    def generate_phone(self) -> str:
        """Generate a realistic phone number"""
        return f"+1-{random.randint(200, 999)}-{random.randint(100, 999)}-{random.randint(1000, 9999)}"

    def generate_address(self) -> Dict[str, Any]:
        """Generate a realistic address"""
        street_numbers = [str(random.randint(1, 9999))]
        street_names = [
            "Main St",
            "Oak Ave",
            "Pine Rd",
            "Cedar Ln",
            "Maple Dr",
            "Elm St",
            "First Ave",
            "Second St",
            "Park Ave",
            "Washington St",
            "Lincoln Ave",
            "Jefferson St",
            "Madison Ave",
            "Franklin St",
            "Roosevelt Ave",
        ]

        return {
            "first_name": random.choice(self.first_names),
            "last_name": random.choice(self.last_names),
            "company": random.choice(self.brands) if random.random() < 0.3 else None,
            "address1": f"{random.choice(street_numbers)} {random.choice(street_names)}",
            "address2": (
                f"Apt {random.randint(1, 50)}" if random.random() < 0.4 else None
            ),
            "city": random.choice(self.cities),
            "province": random.choice(self.states),
            "country": "United States",
            "zip": f"{random.randint(10000, 99999)}",
            "phone": self.generate_phone(),
        }

    def generate_date_range(self, days_back: int = 365) -> datetime:
        """Generate a random date within the last N days"""
        start_date = datetime.now() - timedelta(days=days_back)
        random_days = random.randint(0, days_back)
        return start_date + timedelta(days=random_days)

    def generate_price(
        self, min_price: float = 10.0, max_price: float = 500.0
    ) -> float:
        """Generate a realistic price"""
        return round(random.uniform(min_price, max_price), 2)

    def generate_tags(self, category: str) -> List[str]:
        """Generate realistic tags based on category"""
        tag_pools = {
            "Electronics": ["new", "sale", "premium", "wireless", "smart", "portable"],
            "Clothing": ["casual", "formal", "summer", "winter", "cotton", "sale"],
            "Home & Garden": [
                "outdoor",
                "indoor",
                "decorative",
                "functional",
                "modern",
            ],
            "Sports": ["fitness", "outdoor", "professional", "beginner", "advanced"],
            "Books": ["bestseller", "new-release", "classic", "educational", "fiction"],
        }

        base_tags = tag_pools.get(category, ["new", "popular", "quality"])
        return random.sample(base_tags, random.randint(1, 3))

    def generate_metafields(self) -> List[Dict[str, Any]]:
        """Generate realistic metafields"""
        metafield_types = [
            {
                "namespace": "custom",
                "key": "material",
                "value": random.choice(
                    ["cotton", "polyester", "leather", "metal", "plastic"]
                ),
            },
            {
                "namespace": "custom",
                "key": "color",
                "value": random.choice(
                    ["red", "blue", "green", "black", "white", "gray"]
                ),
            },
            {
                "namespace": "custom",
                "key": "size",
                "value": random.choice(["S", "M", "L", "XL", "XXL"]),
            },
            {
                "namespace": "custom",
                "key": "season",
                "value": random.choice(["spring", "summer", "fall", "winter"]),
            },
            {
                "namespace": "custom",
                "key": "rating",
                "value": str(random.randint(3, 5)),
            },
        ]

        return random.sample(metafield_types, random.randint(1, 3))

    def generate_line_items(
        self, product_ids: List[str], max_items: int = 5
    ) -> List[Dict[str, Any]]:
        """Generate realistic line items for orders"""
        num_items = random.randint(1, max_items)
        selected_products = random.sample(product_ids, num_items)

        line_items = []
        for product_id in selected_products:
            quantity = random.randint(1, 3)
            price = self.generate_price()

            line_items.append(
                {
                    "id": self.generate_shopify_id(),
                    "product_id": product_id,
                    "variant_id": self.generate_shopify_id(),
                    "title": f"Product {product_id}",
                    "variant_title": random.choice(
                        ["Default", "Large", "Small", "Red", "Blue"]
                    ),
                    "sku": f"SKU-{product_id}",
                    "quantity": quantity,
                    "price": f"{price:.2f}",
                    "total_discount": f"{random.uniform(0, price * 0.2):.2f}",
                    "fulfillment_status": random.choice(
                        ["fulfilled", "partial", "unfulfilled"]
                    ),
                    "requires_shipping": True,
                    "taxable": True,
                    "gift_card": False,
                }
            )

        return line_items

    def generate_discount_applications(self) -> List[Dict[str, Any]]:
        """Generate realistic discount applications"""
        if random.random() < 0.3:  # 30% chance of discount
            return [
                {
                    "type": "discount_code",
                    "title": random.choice(["SAVE10", "WELCOME20", "SUMMER15"]),
                    "description": "Discount code applied",
                    "value": f"{random.uniform(5, 50):.2f}",
                    "value_type": "fixed_amount",
                    "allocation_method": "across",
                    "target_selection": "all",
                    "target_type": "line_item",
                }
            ]
        return []

    def generate_behavioral_event(
        self, customer_id: str, product_ids: List[str], event_type: str
    ) -> Dict[str, Any]:
        """Generate realistic behavioral events"""
        base_event = {
            "event_type": event_type,
            "timestamp": self.generate_date_range(30).isoformat(),  # Last 30 days
            "customer_id": customer_id,
            "session_id": str(uuid.uuid4()),
            "user_agent": random.choice(
                [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15",
                ]
            ),
            "ip_address": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
            "referrer": random.choice(
                [
                    "https://google.com",
                    "https://facebook.com",
                    "https://instagram.com",
                    "https://twitter.com",
                    "direct",
                    "email",
                ]
            ),
        }

        if event_type in ["product_view", "add_to_cart", "purchase"]:
            base_event["product_id"] = random.choice(product_ids)
            base_event["product_title"] = f"Product {base_event['product_id']}"
            base_event["product_price"] = self.generate_price()

        if event_type == "purchase":
            base_event["order_id"] = self.generate_shopify_id()
            base_event["order_total"] = self.generate_price(50, 1000)

        return base_event
