#!/usr/bin/env python3
"""
Raw Products Generator - Generates realistic Shopify product data
"""

import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
from base_data_generator import BaseDataGenerator


class RawProductsGenerator(BaseDataGenerator):
    """Generates raw Shopify product data"""

    def __init__(self):
        super().__init__()
        self.product_titles = {
            "Electronics": [
                "Wireless Bluetooth Headphones",
                "Smart Fitness Watch",
                "Portable Phone Charger",
                "4K Ultra HD TV",
                "Gaming Mechanical Keyboard",
                "Wireless Mouse",
                "USB-C Hub",
                "Bluetooth Speaker",
                "Tablet Stand",
                "Phone Case",
                "Screen Protector",
                "Cable Organizer",
            ],
            "Clothing": [
                "Cotton T-Shirt",
                "Denim Jeans",
                "Hoodie Sweatshirt",
                "Running Shoes",
                "Winter Jacket",
                "Summer Dress",
                "Polo Shirt",
                "Cargo Pants",
                "Baseball Cap",
                "Sneakers",
                "Blazer",
                "Leggings",
                "Shorts",
                "Tank Top",
                "Cardigan",
            ],
            "Home & Garden": [
                "Indoor Plant Pot",
                "LED Desk Lamp",
                "Throw Pillow",
                "Wall Art",
                "Kitchen Knife Set",
                "Bath Towel Set",
                "Coffee Mug",
                "Candle Holder",
                "Picture Frame",
                "Garden Tools",
                "Outdoor Chair",
                "Plant Stand",
                "Decorative Vase",
                "Table Runner",
            ],
            "Sports": [
                "Yoga Mat",
                "Resistance Bands",
                "Water Bottle",
                "Gym Bag",
                "Running Shorts",
                "Tennis Racket",
                "Basketball",
                "Soccer Ball",
                "Dumbbells",
                "Jump Rope",
                "Swimming Goggles",
                "Cycling Helmet",
                "Hiking Boots",
                "Fitness Tracker",
            ],
            "Books": [
                "Mystery Novel",
                "Self-Help Guide",
                "Cookbook",
                "Biography",
                "Science Fiction",
                "Romance Novel",
                "History Book",
                "Children's Story",
                "Poetry Collection",
                "Business Strategy",
                "Art Book",
                "Travel Guide",
                "Philosophy Text",
            ],
        }

        self.vendors = [
            "Premium Brands",
            "Quality Goods",
            "Modern Living",
            "Tech Solutions",
            "Style Co",
            "Home Essentials",
            "Sports Pro",
            "Book World",
            "Fashion Forward",
            "Garden Life",
        ]

    def generate_product_variants(self, base_price: float) -> List[Dict[str, Any]]:
        """Generate realistic product variants"""
        variants = []
        sizes = ["XS", "S", "M", "L", "XL", "XXL"]
        colors = ["Black", "White", "Red", "Blue", "Green", "Gray", "Navy", "Brown"]

        # Generate 1-4 variants
        num_variants = random.randint(1, 4)

        for i in range(num_variants):
            variant = {
                "id": self.generate_shopify_id(),
                "product_id": None,  # Will be set later
                "title": "Default Title",
                "price": f"{base_price + random.uniform(-10, 20):.2f}",
                "sku": f"SKU-{random.randint(100000, 999999)}",
                "position": i + 1,
                "inventory_policy": "deny",
                "compare_at_price": f"{base_price + random.uniform(20, 50):.2f}",
                "fulfillment_service": "manual",
                "inventory_management": "shopify",
                "option1": random.choice(sizes) if random.random() < 0.7 else "Default",
                "option2": random.choice(colors) if random.random() < 0.5 else None,
                "option3": None,
                "created_at": self.generate_date_range(180).isoformat(),
                "updated_at": self.generate_date_range(30).isoformat(),
                "taxable": True,
                "barcode": f"123456789{random.randint(100, 999)}",
                "grams": random.randint(50, 2000),
                "image_id": None,
                "weight": random.uniform(0.1, 5.0),
                "weight_unit": "kg",
                "inventory_item_id": self.generate_shopify_id(),
                "inventory_quantity": random.randint(0, 100),
                "old_inventory_quantity": random.randint(0, 100),
                "requires_shipping": True,
                "admin_graphql_api_id": f"gid://shopify/ProductVariant/{self.generate_shopify_id()}",
            }
            variants.append(variant)

        return variants

    def generate_product_images(self) -> List[Dict[str, Any]]:
        """Generate realistic product images"""
        num_images = random.randint(1, 5)
        images = []

        for i in range(num_images):
            image = {
                "id": self.generate_shopify_id(),
                "product_id": None,  # Will be set later
                "position": i + 1,
                "created_at": self.generate_date_range(180).isoformat(),
                "updated_at": self.generate_date_range(30).isoformat(),
                "alt": f"Product image {i + 1}",
                "width": random.choice([800, 1024, 1200, 1600]),
                "height": random.choice([600, 768, 900, 1200]),
                "src": f"https://cdn.shopify.com/s/files/1/0000/0000/products/product_{random.randint(1000, 9999)}.jpg",
                "variant_ids": [],
                "admin_graphql_api_id": f"gid://shopify/ProductImage/{self.generate_shopify_id()}",
            }
            images.append(image)

        return images

    def generate_product_options(self) -> List[Dict[str, Any]]:
        """Generate realistic product options"""
        options = []
        option_names = ["Size", "Color", "Style", "Material"]

        num_options = random.randint(1, 3)

        for i in range(num_options):
            option = {
                "id": self.generate_shopify_id(),
                "product_id": None,  # Will be set later
                "name": option_names[i],
                "position": i + 1,
                "values": self.get_option_values(option_names[i]),
            }
            options.append(option)

        return options

    def get_option_values(self, option_name: str) -> List[str]:
        """Get realistic option values based on option name"""
        values_map = {
            "Size": ["XS", "S", "M", "L", "XL", "XXL"],
            "Color": [
                "Black",
                "White",
                "Red",
                "Blue",
                "Green",
                "Gray",
                "Navy",
                "Brown",
            ],
            "Style": ["Classic", "Modern", "Vintage", "Casual", "Formal"],
            "Material": ["Cotton", "Polyester", "Leather", "Metal", "Plastic", "Wood"],
        }

        available_values = values_map.get(option_name, ["Default"])
        return random.sample(available_values, random.randint(2, len(available_values)))

    def generate_single_product(
        self, shop_id: str, product_id: str, category: str
    ) -> Dict[str, Any]:
        """Generate a single realistic product"""
        title = random.choice(self.product_titles.get(category, ["Generic Product"]))
        vendor = random.choice(self.vendors)
        base_price = self.generate_price(10, 500)

        # Generate dates
        created_at = self.generate_date_range(365)
        updated_at = created_at + timedelta(days=random.randint(1, 30))

        # Generate variants, images, and options
        variants = self.generate_product_variants(base_price)
        images = self.generate_product_images()
        options = self.generate_product_options()

        # Set product_id references
        for variant in variants:
            variant["product_id"] = product_id
        for image in images:
            image["product_id"] = product_id
        for option in options:
            option["product_id"] = product_id

        product = {
            "id": product_id,
            "title": title,
            "body_html": f"<p>High-quality {title.lower()} perfect for everyday use. Made with premium materials and designed for durability.</p>",
            "vendor": vendor,
            "product_type": category,
            "created_at": created_at.isoformat(),
            "handle": f"{title.lower().replace(' ', '-')}-{product_id}",
            "updated_at": updated_at.isoformat(),
            "published_at": created_at.isoformat(),
            "template_suffix": None,
            "status": random.choice(["ACTIVE", "DRAFT", "ARCHIVED"]),
            "published_scope": "web",
            "tags": ", ".join(self.generate_tags(category)),
            "admin_graphql_api_id": f"gid://shopify/Product/{product_id}",
            "variants": variants,
            "options": options,
            "images": images,
            "image": images[0] if images else None,
        }

        return product

    def generate_products_for_shop(
        self, shop_id: str, num_products: int = 500
    ) -> List[Dict[str, Any]]:
        """Generate products for a specific shop"""
        products = []
        categories = list(self.product_titles.keys())

        for i in range(num_products):
            product_id = self.generate_shopify_id()
            category = random.choice(categories)

            product = self.generate_single_product(shop_id, product_id, category)

            # Create raw product record
            raw_product = {
                "id": f"raw_product_{shop_id}_{product_id}",
                "shopId": shop_id,
                "payload": product,
                # Align extractedAt with Shopify updated_at to match incremental semantics
                "extractedAt": product["updated_at"],
                "shopifyId": product_id,
                "shopifyCreatedAt": product["created_at"],
                "shopifyUpdatedAt": product["updated_at"],
            }

            products.append(raw_product)

        return products

    def generate_all_products(
        self, shops: List[Dict[str, str]], products_per_shop: int = 500
    ) -> List[Dict[str, Any]]:
        """Generate products for all shops"""
        all_products = []

        for shop in shops:
            shop_id = shop["id"]
            print(f"Generating {products_per_shop} products for shop {shop_id}...")

            products = self.generate_products_for_shop(shop_id, products_per_shop)
            all_products.extend(products)

        print(f"Generated {len(all_products)} total products")
        return all_products


if __name__ == "__main__":
    # Test the generator
    generator = RawProductsGenerator()
    shops = [
        {"id": "shop_123", "name": "Fashion Store"},
        {"id": "shop_456", "name": "Electronics Hub"},
        {"id": "shop_789", "name": "Home & Garden"},
    ]

    products = generator.generate_all_products(shops, 10)  # Small test
    print(f"Generated {len(products)} products")
    print("Sample product:", json.dumps(products[0], indent=2))
