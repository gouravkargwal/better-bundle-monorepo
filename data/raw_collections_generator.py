#!/usr/bin/env python3
"""
Raw Collections Generator - Generates realistic Shopify collection data
"""

import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
from base_data_generator import BaseDataGenerator


class RawCollectionsGenerator(BaseDataGenerator):
    """Generates raw Shopify collection data"""

    def __init__(self):
        super().__init__()
        self.collection_titles = [
            "New Arrivals",
            "Best Sellers",
            "Sale Items",
            "Featured Products",
            "Summer Collection",
            "Winter Collection",
            "Spring Collection",
            "Fall Collection",
            "Premium Quality",
            "Budget Friendly",
            "Gift Ideas",
            "Limited Edition",
            "Customer Favorites",
            "Staff Picks",
            "Trending Now",
            "Clearance",
            "Eco Friendly",
            "Organic Products",
            "Handmade Items",
            "Vintage Collection",
            "Tech Gadgets",
            "Home Decor",
            "Fashion Forward",
            "Athletic Wear",
            "Beauty Essentials",
            "Kitchen Must-Haves",
            "Outdoor Gear",
            "Office Supplies",
        ]

        self.collection_descriptions = [
            "Discover our latest and greatest products in this curated collection.",
            "Handpicked items that our customers love and recommend.",
            "Save big on these amazing deals and limited-time offers.",
            "Premium quality products that stand out from the rest.",
            "Perfect for the season with trendy and stylish options.",
            "Eco-conscious choices for environmentally aware shoppers.",
            "Unique and one-of-a-kind items you won't find anywhere else.",
            "Essential items for your daily needs and lifestyle.",
        ]

    def generate_collection_image(self) -> Dict[str, Any]:
        """Generate realistic collection image"""
        return {
            "id": self.generate_shopify_id(),
            "product_id": None,
            "position": 1,
            "created_at": self.generate_date_range(180).isoformat(),
            "updated_at": self.generate_date_range(30).isoformat(),
            "alt": "Collection image",
            "width": random.choice([800, 1024, 1200, 1600]),
            "height": random.choice([600, 768, 900, 1200]),
            "src": f"https://cdn.shopify.com/s/files/1/0000/0000/collections/collection_{random.randint(1000, 9999)}.jpg",
            "variant_ids": [],
            "admin_graphql_api_id": f"gid://shopify/CollectionImage/{self.generate_shopify_id()}",
        }

    def generate_collection_metafields(self) -> List[Dict[str, Any]]:
        """Generate realistic collection metafields"""
        metafields = []

        if random.random() < 0.5:  # 50% chance
            metafields.append(
                {
                    "id": self.generate_shopify_id(),
                    "namespace": "custom",
                    "key": "season",
                    "value": random.choice(
                        ["spring", "summer", "fall", "winter", "all-season"]
                    ),
                    "type": "single_line_text_field",
                    "description": "Collection season",
                }
            )

        if random.random() < 0.3:  # 30% chance
            metafields.append(
                {
                    "id": self.generate_shopify_id(),
                    "namespace": "custom",
                    "key": "target_audience",
                    "value": random.choice(["men", "women", "kids", "unisex", "all"]),
                    "type": "single_line_text_field",
                    "description": "Target audience",
                }
            )

        if random.random() < 0.4:  # 40% chance
            metafields.append(
                {
                    "id": self.generate_shopify_id(),
                    "namespace": "custom",
                    "key": "price_range",
                    "value": random.choice(
                        ["budget", "mid-range", "premium", "luxury"]
                    ),
                    "type": "single_line_text_field",
                    "description": "Price range category",
                }
            )

        return metafields

    def generate_single_collection(
        self, shop_id: str, collection_id: str
    ) -> Dict[str, Any]:
        """Generate a single realistic collection"""
        title = random.choice(self.collection_titles)
        description = random.choice(self.collection_descriptions)

        # Generate dates
        created_at = self.generate_date_range(365)
        updated_at = created_at + timedelta(days=random.randint(1, 30))

        # Generate collection data
        image = self.generate_collection_image()
        metafields = self.generate_collection_metafields()

        collection = {
            "id": collection_id,
            "title": title,
            "body_html": f"<p>{description}</p>",
            "handle": f"{title.lower().replace(' ', '-')}-{collection_id}",
            "updated_at": updated_at.isoformat(),
            "published_at": created_at.isoformat(),
            "sort_order": random.choice(
                [
                    "alpha-asc",
                    "alpha-desc",
                    "best-selling",
                    "created",
                    "created-desc",
                    "manual",
                    "price-asc",
                    "price-desc",
                ]
            ),
            "template_suffix": None,
            "disjunctive": random.choice([True, False]),
            "rules": self.generate_collection_rules(),
            "published_scope": "web",
            "admin_graphql_api_id": f"gid://shopify/Collection/{collection_id}",
            "image": image,
            "metafields": metafields,
        }

        return collection

    def generate_collection_rules(self) -> List[Dict[str, Any]]:
        """Generate realistic collection rules"""
        rules = []

        # Generate 1-3 rules
        num_rules = random.randint(1, 3)

        for i in range(num_rules):
            rule_types = [
                "title",
                "product_type",
                "vendor",
                "tag",
                "price",
                "compare_at_price",
                "weight",
                "inventory_stock",
                "variant_title",
                "variant_compare_at_price",
            ]
            rule_type = random.choice(rule_types)

            rule = {
                "column": rule_type,
                "relation": random.choice(
                    [
                        "equals",
                        "not_equals",
                        "greater_than",
                        "less_than",
                        "starts_with",
                        "ends_with",
                        "contains",
                        "not_contains",
                    ]
                ),
                "condition": self.generate_rule_condition(rule_type),
            }
            rules.append(rule)

        return rules

    def generate_rule_condition(self, rule_type: str) -> str:
        """Generate realistic rule conditions based on rule type"""
        conditions_map = {
            "title": ["New", "Sale", "Premium", "Limited", "Exclusive"],
            "product_type": [
                "Electronics",
                "Clothing",
                "Home & Garden",
                "Sports",
                "Books",
            ],
            "vendor": [
                "Premium Brands",
                "Quality Goods",
                "Modern Living",
                "Tech Solutions",
            ],
            "tag": ["new", "sale", "premium", "limited", "exclusive", "popular"],
            "price": ["10", "25", "50", "100", "200", "500"],
            "compare_at_price": ["20", "50", "100", "200", "500", "1000"],
            "weight": ["100", "500", "1000", "2000", "5000"],
            "inventory_stock": ["1", "5", "10", "25", "50", "100"],
            "variant_title": ["Default", "Large", "Small", "Red", "Blue", "Green"],
            "variant_compare_at_price": ["20", "50", "100", "200", "500"],
        }

        available_conditions = conditions_map.get(rule_type, ["default"])
        return random.choice(available_conditions)

    def generate_collections_for_shop(
        self, shop_id: str, num_collections: int = 50
    ) -> List[Dict[str, Any]]:
        """Generate collections for a specific shop"""
        collections = []

        for i in range(num_collections):
            collection_id = self.generate_shopify_id()
            collection = self.generate_single_collection(shop_id, collection_id)

            # Create raw collection record
            raw_collection = {
                "id": f"raw_collection_{shop_id}_{collection_id}",
                "shop_id": shop_id,
                "payload": collection,
                # Align extractedAt with Shopify updated_at
                "extractedAt": collection["updated_at"],
                "shopifyId": collection_id,
                "shopifyCreatedAt": collection["published_at"],
                "shopifyUpdatedAt": collection["updated_at"],
            }

            collections.append(raw_collection)

        return collections

    def generate_all_collections(
        self, shops: List[Dict[str, str]], collections_per_shop: int = 50
    ) -> List[Dict[str, Any]]:
        """Generate collections for all shops"""
        all_collections = []

        for shop in shops:
            shop_id = shop["id"]
            print(
                f"Generating {collections_per_shop} collections for shop {shop_id}..."
            )

            collections = self.generate_collections_for_shop(
                shop_id, collections_per_shop
            )
            all_collections.extend(collections)

        print(f"Generated {len(all_collections)} total collections")
        return all_collections


if __name__ == "__main__":
    # Test the generator
    generator = RawCollectionsGenerator()
    shops = [
        {"id": "shop_123", "name": "Fashion Store"},
        {"id": "shop_456", "name": "Electronics Hub"},
        {"id": "shop_789", "name": "Home & Garden"},
    ]

    collections = generator.generate_all_collections(shops, 10)  # Small test
    print(f"Generated {len(collections)} collections")
    print("Sample collection:", json.dumps(collections[0], indent=2))
