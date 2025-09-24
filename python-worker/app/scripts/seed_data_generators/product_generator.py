"""
Product data generator for creating realistic Shopify product data.
"""

import random
from typing import Dict, Any, List
from .base_generator import BaseGenerator


class ProductGenerator(BaseGenerator):
    """Generates realistic product data with enhanced features."""

    def generate_products(self) -> List[Dict[str, Any]]:
        """Generate 15 diverse products across categories."""
        products = []

        # Clothing Products (1-5)
        products.extend(self._generate_clothing_products())

        # Accessories Products (6-10)
        products.extend(self._generate_accessories_products())

        # Electronics Products (11-15)
        products.extend(self._generate_electronics_products())

        return products

    def _generate_clothing_products(self) -> List[Dict[str, Any]]:
        """Generate clothing products with realistic data."""
        clothing_products = [
            {
                "title": "Premium Cotton Hoodie",
                "handle": "premium-cotton-hoodie",
                "description": "Ultra-soft cotton hoodie perfect for everyday comfort. Features adjustable drawstring hood and kangaroo pocket.",
                "productType": "Clothing",
                "tags": ["clothing", "hoodie", "cotton", "casual", "comfortable"],
                "price_range": (35, 55),
                "inventory_range": (8, 20),
                "has_video": True,
                "has_3d": False,
                "seo_optimized": True,
                "on_sale": False,
                "created_days_ago": 45,
            },
            {
                "title": "Classic V-Neck T-Shirt",
                "handle": "classic-vneck-tshirt",
                "description": "Essential v-neck t-shirt in premium cotton blend. Perfect for layering or wearing alone.",
                "productType": "Clothing",
                "tags": ["clothing", "tshirt", "v-neck", "cotton", "essential"],
                "price_range": (18, 28),
                "inventory_range": (15, 30),
                "has_video": False,
                "has_3d": False,
                "seo_optimized": True,
                "on_sale": False,
                "created_days_ago": 30,
            },
            {
                "title": "Slim Fit Jeans",
                "handle": "slim-fit-jeans",
                "description": "Modern slim-fit jeans with stretch denim for comfort and style. Perfect for casual and smart-casual looks.",
                "productType": "Clothing",
                "tags": ["clothing", "jeans", "denim", "slim-fit", "stretch"],
                "price_range": (45, 75),
                "inventory_range": (6, 18),
                "has_video": True,
                "has_3d": True,
                "seo_optimized": True,
                "on_sale": True,
                "created_days_ago": 25,
            },
            {
                "title": "Athletic Shorts",
                "handle": "athletic-shorts",
                "description": "Performance athletic shorts with moisture-wicking fabric. Ideal for workouts and active lifestyle.",
                "productType": "Clothing",
                "tags": [
                    "clothing",
                    "shorts",
                    "athletic",
                    "performance",
                    "moisture-wicking",
                ],
                "price_range": (25, 40),
                "inventory_range": (10, 25),
                "has_video": False,
                "has_3d": False,
                "seo_optimized": False,
                "on_sale": False,
                "created_days_ago": 20,
            },
            {
                "title": "Wool Blend Sweater",
                "handle": "wool-blend-sweater",
                "description": "Cozy wool blend sweater perfect for cooler weather. Features ribbed cuffs and hem for a polished look.",
                "productType": "Clothing",
                "tags": ["clothing", "sweater", "wool", "warm", "cozy"],
                "price_range": (55, 85),
                "inventory_range": (4, 12),
                "has_video": True,
                "has_3d": False,
                "seo_optimized": True,
                "on_sale": False,
                "created_days_ago": 15,
            },
        ]

        return self._build_product_payloads(clothing_products, 1)

    def _generate_accessories_products(self) -> List[Dict[str, Any]]:
        """Generate accessories products with realistic data."""
        accessories_products = [
            {
                "title": "Designer Sunglasses",
                "handle": "designer-sunglasses",
                "description": "Premium designer sunglasses with UV protection and polarized lenses. Stylish and functional.",
                "productType": "Accessories",
                "tags": [
                    "accessories",
                    "sunglasses",
                    "designer",
                    "uv-protection",
                    "polarized",
                ],
                "price_range": (45, 75),
                "inventory_range": (5, 15),
                "has_video": True,
                "has_3d": True,
                "seo_optimized": True,
                "on_sale": True,
                "created_days_ago": 40,
            },
            {
                "title": "Leather Crossbody Bag",
                "handle": "leather-crossbody-bag",
                "description": "Handcrafted leather crossbody bag with adjustable strap. Perfect for daily essentials.",
                "productType": "Accessories",
                "tags": ["accessories", "bag", "leather", "crossbody", "handcrafted"],
                "price_range": (65, 95),
                "inventory_range": (3, 10),
                "has_video": False,
                "has_3d": True,
                "seo_optimized": True,
                "on_sale": False,
                "created_days_ago": 35,
            },
            {
                "title": "Silk Scarf",
                "handle": "silk-scarf",
                "description": "Luxurious silk scarf with elegant pattern. Versatile accessory for any outfit.",
                "productType": "Accessories",
                "tags": ["accessories", "scarf", "silk", "luxury", "elegant"],
                "price_range": (35, 55),
                "inventory_range": (8, 20),
                "has_video": False,
                "has_3d": False,
                "seo_optimized": False,
                "on_sale": False,
                "created_days_ago": 10,
            },
            {
                "title": "Leather Belt",
                "handle": "leather-belt",
                "description": "Classic leather belt with brass buckle. Timeless accessory for any wardrobe.",
                "productType": "Accessories",
                "tags": ["accessories", "belt", "leather", "classic", "brass-buckle"],
                "price_range": (25, 45),
                "inventory_range": (12, 25),
                "has_video": False,
                "has_3d": False,
                "seo_optimized": True,
                "on_sale": False,
                "created_days_ago": 28,
            },
            {
                "title": "Baseball Cap",
                "handle": "baseball-cap",
                "description": "Classic baseball cap with embroidered logo. Adjustable fit for all head sizes.",
                "productType": "Accessories",
                "tags": ["accessories", "cap", "baseball", "embroidered", "adjustable"],
                "price_range": (15, 30),
                "inventory_range": (20, 40),
                "has_video": False,
                "has_3d": False,
                "seo_optimized": False,
                "on_sale": False,
                "created_days_ago": 5,
            },
        ]

        return self._build_product_payloads(accessories_products, 6)

    def _generate_electronics_products(self) -> List[Dict[str, Any]]:
        """Generate electronics products with realistic data."""
        electronics_products = [
            {
                "title": "Wireless Earbuds Pro",
                "handle": "wireless-earbuds-pro",
                "description": "Premium wireless earbuds with active noise cancellation, 3D audio, and 24-hour battery life.",
                "productType": "Electronics",
                "tags": [
                    "electronics",
                    "earbuds",
                    "wireless",
                    "noise-cancellation",
                    "3d-audio",
                ],
                "price_range": (80, 120),
                "inventory_range": (5, 15),
                "has_video": True,
                "has_3d": True,
                "seo_optimized": True,
                "on_sale": True,
                "created_days_ago": 50,
            },
            {
                "title": "Smart Watch",
                "handle": "smart-watch",
                "description": "Advanced smart watch with health tracking, GPS, and 7-day battery life. Water resistant.",
                "productType": "Electronics",
                "tags": [
                    "electronics",
                    "smartwatch",
                    "health-tracking",
                    "gps",
                    "water-resistant",
                ],
                "price_range": (120, 200),
                "inventory_range": (3, 8),
                "has_video": True,
                "has_3d": True,
                "seo_optimized": True,
                "on_sale": False,
                "created_days_ago": 60,
            },
            {
                "title": "Phone Case",
                "handle": "phone-case",
                "description": "Protective phone case with shock absorption and wireless charging compatibility.",
                "productType": "Electronics",
                "tags": [
                    "electronics",
                    "phone-case",
                    "protective",
                    "wireless-charging",
                    "shock-absorption",
                ],
                "price_range": (12, 25),
                "inventory_range": (25, 50),
                "has_video": False,
                "has_3d": False,
                "seo_optimized": True,
                "on_sale": False,
                "created_days_ago": 20,
            },
            {
                "title": "Portable Charger",
                "handle": "portable-charger",
                "description": "High-capacity portable charger with fast charging technology. Compact and lightweight.",
                "productType": "Electronics",
                "tags": [
                    "electronics",
                    "charger",
                    "portable",
                    "fast-charging",
                    "high-capacity",
                ],
                "price_range": (30, 50),
                "inventory_range": (8, 20),
                "has_video": False,
                "has_3d": False,
                "seo_optimized": True,
                "on_sale": False,
                "created_days_ago": 12,
            },
            {
                "title": "Bluetooth Speaker",
                "handle": "bluetooth-speaker",
                "description": "Portable Bluetooth speaker with 360-degree sound and 12-hour battery life.",
                "productType": "Electronics",
                "tags": [
                    "electronics",
                    "speaker",
                    "bluetooth",
                    "portable",
                    "360-sound",
                ],
                "price_range": (45, 75),
                "inventory_range": (6, 15),
                "has_video": True,
                "has_3d": False,
                "seo_optimized": True,
                "on_sale": True,
                "created_days_ago": 8,
            },
        ]

        return self._build_product_payloads(electronics_products, 11)

    def _build_product_payloads(
        self, product_configs: List[Dict], start_index: int
    ) -> List[Dict[str, Any]]:
        """Build complete product payloads from configurations."""
        products = []

        for i, config in enumerate(product_configs):
            product_index = start_index + i
            product_id = self.dynamic_ids[f"product_{product_index}_id"]
            variant_id = self.dynamic_ids[f"variant_{product_index}_id"]

            # Generate realistic pricing
            min_price, max_price = config["price_range"]
            price = round(random.uniform(min_price, max_price), 2)
            compare_at_price = None
            if config["on_sale"]:
                compare_at_price = round(price * random.uniform(1.2, 1.5), 2)

            # Generate inventory
            min_inv, max_inv = config["inventory_range"]
            inventory = random.randint(min_inv, max_inv)

            # Build media array
            media_edges = self._build_media_edges(product_index, config)

            # Build SEO data
            seo_data = (
                self._build_seo_data(config)
                if config["seo_optimized"]
                else {"title": None, "description": None}
            )

            product_payload = {
                "id": product_id,
                "title": config["title"],
                "handle": config["handle"],
                "description": config["description"],
                "productType": config["productType"],
                "vendor": self.get_vendor(config["productType"]),
                "totalInventory": inventory,
                "onlineStoreUrl": f"https://{self.shop_domain}/products/{config['handle']}",
                "onlineStorePreviewUrl": f"https://{self.shop_domain}/products/{config['handle']}",
                "seo": seo_data,
                "templateSuffix": (
                    "custom-template" if config["seo_optimized"] else None
                ),
                "media": {"edges": media_edges},
                "variants": {
                    "edges": [
                        {
                            "node": {
                                "id": variant_id,
                                "title": "Default Title",
                                "sku": f"{config['handle'].upper().replace('-', '')}-001",
                                "price": str(price),
                                "inventoryQuantity": inventory,
                                "compareAtPrice": (
                                    str(compare_at_price)
                                    if compare_at_price
                                    else None
                                ),
                                "taxable": True,
                                "inventoryPolicy": "DENY",
                                "position": 1,
                                "createdAt": self.past_date(
                                    config["created_days_ago"]
                                ).isoformat(),
                                "updatedAt": self.past_date(
                                    config["created_days_ago"]
                                ).isoformat(),
                            }
                        }
                    ]
                },
                "tags": config["tags"],
                "createdAt": self.past_date(config["created_days_ago"]).isoformat(),
            }

            products.append(product_payload)

        return products

    def _build_media_edges(self, product_index: int, config: Dict) -> List[Dict]:
        """Build media edges for product."""
        media_edges = []

        # Always add main image
        media_edges.append(
            {
                "node": {
                    "id": f"gid://shopify/MediaImage/{product_index}",
                    "image": {
                        "url": f"https://cdn.shopify.com/s/files/1/0000/0001/files/product_{product_index}_main.jpg",
                        "altText": f"{config['title']} - Main view",
                    },
                }
            }
        )

        # Add video if specified
        if config["has_video"]:
            media_edges.append(
                {
                    "node": {
                        "id": f"gid://shopify/MediaVideo/{product_index}",
                        "video": {
                            "id": f"gid://shopify/Video/{product_index}",
                            "sources": [
                                {
                                    "url": f"https://cdn.shopify.com/s/files/1/0000/0001/files/product_{product_index}_video.mp4",
                                    "mimeType": "video/mp4",
                                }
                            ],
                        },
                    }
                }
            )

        # Add 3D model if specified
        if config["has_3d"]:
            media_edges.append(
                {
                    "node": {
                        "id": f"gid://shopify/Model3d/{product_index}",
                        "model3d": {
                            "id": f"gid://shopify/Model3d/{product_index}",
                            "sources": [
                                {
                                    "url": f"https://cdn.shopify.com/s/files/1/0000/0001/files/product_{product_index}_3d.glb",
                                    "mimeType": "model/gltf-binary",
                                }
                            ],
                        },
                    }
                }
            )

        return media_edges

    def _build_seo_data(self, config: Dict) -> Dict[str, str]:
        """Build SEO data for product."""
        return {
            "title": f"{config['title']} - Premium Quality | {self.get_vendor(config['productType'])}",
            "description": f"{config['description']} Shop now with free shipping and easy returns. Premium quality guaranteed.",
        }
