"""
Product data generator for creating realistic Shopify product data with variants.
"""

import random
from typing import Dict, Any, List, Tuple
from .base_generator import BaseGenerator


class ProductGenerator(BaseGenerator):
    """Generates realistic product data with enhanced features and variants."""

    def __init__(self, shop_domain: str = "fashion-store.myshopify.com"):
        super().__init__(shop_domain)
        # Define variant options for different product types
        self.clothing_sizes = ["XS", "S", "M", "L", "XL", "XXL"]
        self.clothing_colors = [
            "Black",
            "White",
            "Navy",
            "Gray",
            "Red",
            "Blue",
            "Green",
            "Pink",
            "Brown",
            "Beige",
            "Purple",
            "Yellow",
            "Orange",
            "Maroon",
            "Teal",
        ]
        self.electronics_colors = [
            "Black",
            "White",
            "Silver",
            "Space Gray",
            "Rose Gold",
            "Blue",
        ]
        self.electronics_storage = ["32GB", "64GB", "128GB", "256GB", "512GB", "1TB"]
        self.accessories_colors = [
            "Black",
            "Brown",
            "Tan",
            "Navy",
            "Red",
            "Green",
            "Blue",
        ]
        self.accessories_materials = ["Leather", "Canvas", "Synthetic", "Metal", "Wood"]
        self.home_colors = [
            "White",
            "Black",
            "Brown",
            "Gray",
            "Blue",
            "Green",
            "Red",
            "Yellow",
        ]
        self.home_sizes = ["Small", "Medium", "Large", "Extra Large"]
        self.sports_sizes = ["XS", "S", "M", "L", "XL", "XXL"]
        self.sports_colors = [
            "Black",
            "White",
            "Red",
            "Blue",
            "Green",
            "Orange",
            "Purple",
            "Pink",
        ]
        self.sports_resistance = ["Light", "Medium", "Heavy", "Extra Heavy"]

    def generate_products(self) -> List[Dict[str, Any]]:
        """Generate 30 diverse products across multiple categories."""
        products = []

        # Clothing Products (1-8)
        products.extend(self._generate_clothing_products())

        # Accessories Products (9-14)
        products.extend(self._generate_accessories_products())

        # Electronics Products (15-20)
        products.extend(self._generate_electronics_products())

        # Home & Garden Products (21-25)
        products.extend(self._generate_home_garden_products())

        # Sports & Fitness Products (26-30)
        products.extend(self._generate_sports_fitness_products())

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
            {
                "title": "Denim Jacket",
                "handle": "denim-jacket",
                "description": "Classic denim jacket with vintage wash. Perfect for layering and adding style to any outfit.",
                "productType": "Clothing",
                "tags": ["clothing", "jacket", "denim", "vintage", "classic"],
                "price_range": (65, 95),
                "inventory_range": (5, 15),
                "has_video": True,
                "has_3d": True,
                "seo_optimized": True,
                "on_sale": False,
                "created_days_ago": 40,
            },
            {
                "title": "Maxi Dress",
                "handle": "maxi-dress",
                "description": "Elegant maxi dress in flowing fabric. Perfect for special occasions or casual elegance.",
                "productType": "Clothing",
                "tags": ["clothing", "dress", "maxi", "elegant", "flowing"],
                "price_range": (45, 75),
                "inventory_range": (3, 12),
                "has_video": True,
                "has_3d": False,
                "seo_optimized": True,
                "on_sale": True,
                "created_days_ago": 35,
            },
            {
                "title": "Cargo Pants",
                "handle": "cargo-pants",
                "description": "Functional cargo pants with multiple pockets. Durable and comfortable for outdoor activities.",
                "productType": "Clothing",
                "tags": ["clothing", "pants", "cargo", "functional", "outdoor"],
                "price_range": (40, 65),
                "inventory_range": (8, 20),
                "has_video": False,
                "has_3d": False,
                "seo_optimized": False,
                "on_sale": False,
                "created_days_ago": 10,
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

        return self._build_product_payloads(electronics_products, 15)

    def _generate_home_garden_products(self) -> List[Dict[str, Any]]:
        """Generate home & garden products with realistic data."""
        home_garden_products = [
            {
                "title": "Ceramic Plant Pot",
                "handle": "ceramic-plant-pot",
                "description": "Handcrafted ceramic plant pot with drainage holes. Perfect for indoor plants and succulents.",
                "productType": "Home & Garden",
                "tags": ["home", "garden", "pot", "ceramic", "plants"],
                "price_range": (15, 35),
                "inventory_range": (10, 25),
                "has_video": False,
                "has_3d": False,
                "seo_optimized": True,
                "on_sale": False,
                "created_days_ago": 20,
            },
            {
                "title": "LED String Lights",
                "handle": "led-string-lights",
                "description": "Warm white LED string lights for indoor and outdoor use. Weather resistant and energy efficient.",
                "productType": "Home & Garden",
                "tags": ["home", "lights", "led", "outdoor", "decorative"],
                "price_range": (12, 25),
                "inventory_range": (15, 30),
                "has_video": False,
                "has_3d": False,
                "seo_optimized": True,
                "on_sale": True,
                "created_days_ago": 30,
            },
            {
                "title": "Bamboo Cutting Board",
                "handle": "bamboo-cutting-board",
                "description": "Eco-friendly bamboo cutting board with antimicrobial properties. Easy to clean and maintain.",
                "productType": "Home & Garden",
                "tags": ["home", "kitchen", "bamboo", "cutting-board", "eco-friendly"],
                "price_range": (20, 40),
                "inventory_range": (8, 20),
                "has_video": True,
                "has_3d": False,
                "seo_optimized": True,
                "on_sale": False,
                "created_days_ago": 25,
            },
            {
                "title": "Garden Tool Set",
                "handle": "garden-tool-set",
                "description": "Complete garden tool set with ergonomic handles. Includes trowel, pruners, and cultivator.",
                "productType": "Home & Garden",
                "tags": ["garden", "tools", "set", "ergonomic", "complete"],
                "price_range": (35, 65),
                "inventory_range": (5, 15),
                "has_video": True,
                "has_3d": False,
                "seo_optimized": True,
                "on_sale": False,
                "created_days_ago": 40,
            },
            {
                "title": "Aromatherapy Diffuser",
                "handle": "aromatherapy-diffuser",
                "description": "Ultrasonic aromatherapy diffuser with LED color changing lights. Perfect for relaxation and wellness.",
                "productType": "Home & Garden",
                "tags": ["home", "wellness", "diffuser", "aromatherapy", "led"],
                "price_range": (25, 50),
                "inventory_range": (6, 18),
                "has_video": True,
                "has_3d": True,
                "seo_optimized": True,
                "on_sale": True,
                "created_days_ago": 15,
            },
        ]

        return self._build_product_payloads(home_garden_products, 21)

    def _generate_sports_fitness_products(self) -> List[Dict[str, Any]]:
        """Generate sports & fitness products with realistic data."""
        sports_fitness_products = [
            {
                "title": "Yoga Mat",
                "handle": "yoga-mat",
                "description": "Premium non-slip yoga mat with excellent grip and cushioning. Perfect for yoga, pilates, and fitness.",
                "productType": "Sports & Fitness",
                "tags": ["sports", "fitness", "yoga", "mat", "non-slip"],
                "price_range": (25, 45),
                "inventory_range": (12, 25),
                "has_video": True,
                "has_3d": False,
                "seo_optimized": True,
                "on_sale": False,
                "created_days_ago": 35,
            },
            {
                "title": "Resistance Bands Set",
                "handle": "resistance-bands-set",
                "description": "Complete resistance bands set with different resistance levels. Includes handles and door anchor.",
                "productType": "Sports & Fitness",
                "tags": ["sports", "fitness", "resistance", "bands", "workout"],
                "price_range": (20, 40),
                "inventory_range": (8, 20),
                "has_video": True,
                "has_3d": False,
                "seo_optimized": True,
                "on_sale": True,
                "created_days_ago": 28,
            },
            {
                "title": "Water Bottle",
                "handle": "water-bottle",
                "description": "Insulated stainless steel water bottle that keeps drinks cold for 24 hours. BPA-free and leak-proof.",
                "productType": "Sports & Fitness",
                "tags": [
                    "sports",
                    "fitness",
                    "water-bottle",
                    "insulated",
                    "stainless-steel",
                ],
                "price_range": (15, 30),
                "inventory_range": (20, 40),
                "has_video": False,
                "has_3d": False,
                "seo_optimized": True,
                "on_sale": False,
                "created_days_ago": 18,
            },
            {
                "title": "Running Headband",
                "handle": "running-headband",
                "description": "Moisture-wicking running headband that stays in place during intense workouts. Multiple colors available.",
                "productType": "Sports & Fitness",
                "tags": [
                    "sports",
                    "fitness",
                    "headband",
                    "running",
                    "moisture-wicking",
                ],
                "price_range": (8, 18),
                "inventory_range": (25, 50),
                "has_video": False,
                "has_3d": False,
                "seo_optimized": False,
                "on_sale": False,
                "created_days_ago": 12,
            },
            {
                "title": "Foam Roller",
                "handle": "foam-roller",
                "description": "High-density foam roller for muscle recovery and massage therapy. Helps improve flexibility and reduce soreness.",
                "productType": "Sports & Fitness",
                "tags": ["sports", "fitness", "foam-roller", "recovery", "massage"],
                "price_range": (18, 35),
                "inventory_range": (6, 15),
                "has_video": True,
                "has_3d": False,
                "seo_optimized": True,
                "on_sale": False,
                "created_days_ago": 22,
            },
        ]

        return self._build_product_payloads(sports_fitness_products, 26)

    def _generate_clothing_variants(self, product_config: Dict) -> List[Dict[str, Any]]:
        """Generate realistic variants for clothing products with size and color options."""
        variants = []
        base_price = random.uniform(*product_config["price_range"])

        # Select 3-5 colors and 4-6 sizes for each clothing item
        selected_colors = random.sample(self.clothing_colors, random.randint(3, 5))
        selected_sizes = random.sample(self.clothing_sizes, random.randint(4, 6))

        variant_index = 1
        for color in selected_colors:
            for size in selected_sizes:
                # Price variation based on size (larger sizes cost more)
                size_multiplier = 1.0
                if size in ["XL", "XXL"]:
                    size_multiplier = 1.05
                elif size in ["XS", "S"]:
                    size_multiplier = 0.98

                price = round(base_price * size_multiplier, 2)
                compare_at_price = None
                if product_config["on_sale"]:
                    compare_at_price = round(price * random.uniform(1.2, 1.4), 2)

                # Inventory varies by size (medium sizes have more stock)
                base_inventory = random.randint(*product_config["inventory_range"])
                if size == "M":
                    inventory = base_inventory + random.randint(5, 10)
                elif size in ["XS", "XXL"]:
                    inventory = max(1, base_inventory - random.randint(3, 8))
                else:
                    inventory = base_inventory

                variants.append(
                    {
                        "title": f"{size} / {color}",
                        "price": str(price),
                        "compareAtPrice": (
                            str(compare_at_price) if compare_at_price else None
                        ),
                        "sku": f"{product_config['handle'].upper().replace('-', '')}-{size}-{color[:3].upper()}-{variant_index:03d}",
                        "inventoryQuantity": inventory,
                        "taxable": True,
                        "inventoryPolicy": "DENY",
                        "option1": size,
                        "option2": color,
                        "position": variant_index,
                    }
                )
                variant_index += 1

        return variants

    def _generate_electronics_variants(
        self, product_config: Dict
    ) -> List[Dict[str, Any]]:
        """Generate realistic variants for electronics products with color and storage options."""
        variants = []
        base_price = random.uniform(*product_config["price_range"])

        # Select 2-4 colors and 2-3 storage options
        selected_colors = random.sample(self.electronics_colors, random.randint(2, 4))
        selected_storage = random.sample(self.electronics_storage, random.randint(2, 3))

        variant_index = 1
        for color in selected_colors:
            for storage in selected_storage:
                # Price variation based on storage capacity
                storage_multiplier = 1.0
                if storage in ["512GB", "1TB"]:
                    storage_multiplier = 1.3 + (0.1 if storage == "1TB" else 0)
                elif storage in ["32GB", "64GB"]:
                    storage_multiplier = 0.8 + (0.1 if storage == "64GB" else 0)

                price = round(base_price * storage_multiplier, 2)
                compare_at_price = None
                if product_config["on_sale"]:
                    compare_at_price = round(price * random.uniform(1.15, 1.3), 2)

                # Inventory varies by storage (higher capacity = lower stock)
                base_inventory = random.randint(*product_config["inventory_range"])
                if storage in ["1TB", "512GB"]:
                    inventory = max(1, base_inventory - random.randint(3, 6))
                else:
                    inventory = base_inventory

                variants.append(
                    {
                        "title": f"{color} / {storage}",
                        "price": str(price),
                        "compareAtPrice": (
                            str(compare_at_price) if compare_at_price else None
                        ),
                        "sku": f"{product_config['handle'].upper().replace('-', '')}-{color[:3].upper()}-{storage}-{variant_index:03d}",
                        "inventoryQuantity": inventory,
                        "taxable": True,
                        "inventoryPolicy": "DENY",
                        "option1": color,
                        "option2": storage,
                        "position": variant_index,
                    }
                )
                variant_index += 1

        return variants

    def _generate_accessories_variants(
        self, product_config: Dict
    ) -> List[Dict[str, Any]]:
        """Generate realistic variants for accessories with color and material options."""
        variants = []
        base_price = random.uniform(*product_config["price_range"])

        # Select 2-4 colors and 2-3 materials
        selected_colors = random.sample(self.accessories_colors, random.randint(2, 4))
        selected_materials = random.sample(
            self.accessories_materials, random.randint(2, 3)
        )

        variant_index = 1
        for color in selected_colors:
            for material in selected_materials:
                # Price variation based on material (leather costs more)
                material_multiplier = 1.0
                if material == "Leather":
                    material_multiplier = 1.2
                elif material == "Metal":
                    material_multiplier = 1.1
                elif material == "Synthetic":
                    material_multiplier = 0.9

                price = round(base_price * material_multiplier, 2)
                compare_at_price = None
                if product_config["on_sale"]:
                    compare_at_price = round(price * random.uniform(1.1, 1.3), 2)

                # Inventory varies by material
                base_inventory = random.randint(*product_config["inventory_range"])
                if material == "Leather":
                    inventory = max(1, base_inventory - random.randint(2, 5))
                else:
                    inventory = base_inventory

                variants.append(
                    {
                        "title": f"{color} / {material}",
                        "price": str(price),
                        "compareAtPrice": (
                            str(compare_at_price) if compare_at_price else None
                        ),
                        "sku": f"{product_config['handle'].upper().replace('-', '')}-{color[:3].upper()}-{material[:3].upper()}-{variant_index:03d}",
                        "inventoryQuantity": inventory,
                        "taxable": True,
                        "inventoryPolicy": "DENY",
                        "option1": color,
                        "option2": material,
                        "position": variant_index,
                    }
                )
                variant_index += 1

        return variants

    def _generate_home_garden_variants(
        self, product_config: Dict
    ) -> List[Dict[str, Any]]:
        """Generate realistic variants for home & garden products with size and color options."""
        variants = []
        base_price = random.uniform(*product_config["price_range"])

        # Select 2-4 colors and 2-3 sizes
        selected_colors = random.sample(self.home_colors, random.randint(2, 4))
        selected_sizes = random.sample(self.home_sizes, random.randint(2, 3))

        variant_index = 1
        for color in selected_colors:
            for size in selected_sizes:
                # Price variation based on size
                size_multiplier = 1.0
                if size == "Extra Large":
                    size_multiplier = 1.3
                elif size == "Large":
                    size_multiplier = 1.1
                elif size == "Small":
                    size_multiplier = 0.8

                price = round(base_price * size_multiplier, 2)
                compare_at_price = None
                if product_config["on_sale"]:
                    compare_at_price = round(price * random.uniform(1.1, 1.25), 2)

                # Inventory varies by size
                base_inventory = random.randint(*product_config["inventory_range"])
                if size == "Extra Large":
                    inventory = max(1, base_inventory - random.randint(2, 4))
                else:
                    inventory = base_inventory

                variants.append(
                    {
                        "title": f"{size} / {color}",
                        "price": str(price),
                        "compareAtPrice": (
                            str(compare_at_price) if compare_at_price else None
                        ),
                        "sku": f"{product_config['handle'].upper().replace('-', '')}-{size[:1]}-{color[:3].upper()}-{variant_index:03d}",
                        "inventoryQuantity": inventory,
                        "taxable": True,
                        "inventoryPolicy": "DENY",
                        "option1": size,
                        "option2": color,
                        "position": variant_index,
                    }
                )
                variant_index += 1

        return variants

    def _generate_sports_fitness_variants(
        self, product_config: Dict
    ) -> List[Dict[str, Any]]:
        """Generate realistic variants for sports & fitness products with size, color, and resistance options."""
        variants = []
        base_price = random.uniform(*product_config["price_range"])

        # For different product types, use different variant combinations
        if "band" in product_config["handle"].lower():
            # Resistance bands - use resistance level and color
            selected_colors = random.sample(self.sports_colors, random.randint(2, 4))
            selected_resistance = random.sample(
                self.sports_resistance, random.randint(2, 3)
            )

            variant_index = 1
            for color in selected_colors:
                for resistance in selected_resistance:
                    # Price variation based on resistance level
                    resistance_multiplier = 1.0
                    if resistance == "Extra Heavy":
                        resistance_multiplier = 1.2
                    elif resistance == "Heavy":
                        resistance_multiplier = 1.1
                    elif resistance == "Light":
                        resistance_multiplier = 0.9

                    price = round(base_price * resistance_multiplier, 2)
                    compare_at_price = None
                    if product_config["on_sale"]:
                        compare_at_price = round(price * random.uniform(1.1, 1.25), 2)

                    # Inventory varies by resistance level
                    base_inventory = random.randint(*product_config["inventory_range"])
                    if resistance in ["Extra Heavy", "Light"]:
                        inventory = max(1, base_inventory - random.randint(2, 4))
                    else:
                        inventory = base_inventory

                    variants.append(
                        {
                            "title": f"{color} / {resistance}",
                            "price": str(price),
                            "compareAtPrice": (
                                str(compare_at_price) if compare_at_price else None
                            ),
                            "sku": f"{product_config['handle'].upper().replace('-', '')}-{color[:3].upper()}-{resistance[:1]}-{variant_index:03d}",
                            "inventoryQuantity": inventory,
                            "taxable": True,
                            "inventoryPolicy": "DENY",
                            "option1": color,
                            "option2": resistance,
                            "position": variant_index,
                        }
                    )
                    variant_index += 1
        else:
            # Other sports products - use size and color
            selected_colors = random.sample(self.sports_colors, random.randint(2, 4))
            selected_sizes = random.sample(self.sports_sizes, random.randint(3, 5))

            variant_index = 1
            for color in selected_colors:
                for size in selected_sizes:
                    # Price variation based on size
                    size_multiplier = 1.0
                    if size in ["XL", "XXL"]:
                        size_multiplier = 1.05
                    elif size in ["XS", "S"]:
                        size_multiplier = 0.95

                    price = round(base_price * size_multiplier, 2)
                    compare_at_price = None
                    if product_config["on_sale"]:
                        compare_at_price = round(price * random.uniform(1.1, 1.25), 2)

                    # Inventory varies by size
                    base_inventory = random.randint(*product_config["inventory_range"])
                    if size == "M":
                        inventory = base_inventory + random.randint(3, 8)
                    elif size in ["XS", "XXL"]:
                        inventory = max(1, base_inventory - random.randint(2, 5))
                    else:
                        inventory = base_inventory

                    variants.append(
                        {
                            "title": f"{size} / {color}",
                            "price": str(price),
                            "compareAtPrice": (
                                str(compare_at_price) if compare_at_price else None
                            ),
                            "sku": f"{product_config['handle'].upper().replace('-', '')}-{size}-{color[:3].upper()}-{variant_index:03d}",
                            "inventoryQuantity": inventory,
                            "taxable": True,
                            "inventoryPolicy": "DENY",
                            "option1": size,
                            "option2": color,
                            "position": variant_index,
                        }
                    )
                    variant_index += 1

        return variants

    def _build_product_payloads(
        self, product_configs: List[Dict], start_index: int
    ) -> List[Dict[str, Any]]:
        """Build complete product payloads from configurations with realistic variants."""
        products = []

        for i, config in enumerate(product_configs):
            product_index = start_index + i
            product_id = self.dynamic_ids[f"product_{product_index}_id"]

            # Generate variants based on product type
            variants = self._generate_variants_for_product(config, product_index)

            # Calculate total inventory from all variants
            total_inventory = sum(
                variant["node"]["inventoryQuantity"] for variant in variants
            )

            # Build media array
            media_edges = self._build_media_edges(product_index, config)

            # Build SEO data
            seo_data = (
                self._build_seo_data(config)
                if config["seo_optimized"]
                else {"title": None, "description": None}
            )

            # Build product options based on variant structure
            product_options = self._build_product_options(variants)

            product_payload = {
                "id": product_id,
                "title": config["title"],
                "handle": config["handle"],
                "description": config["description"],
                "productType": config["productType"],
                "vendor": self.get_vendor(config["productType"]),
                "totalInventory": total_inventory,
                "onlineStoreUrl": f"https://{self.shop_domain}/products/{config['handle']}",
                "onlineStorePreviewUrl": f"https://{self.shop_domain}/products/{config['handle']}",
                "seo": seo_data,
                "templateSuffix": (
                    "custom-template" if config["seo_optimized"] else None
                ),
                "media": {"edges": media_edges},
                "variants": {"edges": variants},
                "options": product_options,
                "tags": config["tags"],
                "createdAt": self.past_date(config["created_days_ago"]).isoformat(),
            }

            products.append(product_payload)

        return products

    def _generate_variants_for_product(
        self, config: Dict, product_index: int
    ) -> List[Dict[str, Any]]:
        """Generate variants for a specific product based on its type."""
        product_type = config["productType"]

        if product_type == "Clothing":
            variants = self._generate_clothing_variants(config)
        elif product_type == "Electronics":
            variants = self._generate_electronics_variants(config)
        elif product_type == "Accessories":
            variants = self._generate_accessories_variants(config)
        elif product_type == "Home & Garden":
            variants = self._generate_home_garden_variants(config)
        elif product_type == "Sports & Fitness":
            variants = self._generate_sports_fitness_variants(config)
        else:
            # Fallback to simple variant
            variants = self._generate_simple_variant(config, product_index)

        # Convert to GraphQL format with proper IDs
        variant_edges = []
        for i, variant in enumerate(variants):
            variant_id = f"gid://shopify/ProductVariant/{self.base_id + 1000 + product_index + i}"
            variant_edges.append(
                {
                    "node": {
                        "id": variant_id,
                        "title": variant["title"],
                        "sku": variant["sku"],
                        "price": variant["price"],
                        "inventoryQuantity": variant["inventoryQuantity"],
                        "compareAtPrice": variant.get("compareAtPrice"),
                        "taxable": variant["taxable"],
                        "inventoryPolicy": variant["inventoryPolicy"],
                        "position": variant["position"],
                        "option1": variant.get("option1"),
                        "option2": variant.get("option2"),
                        "option3": variant.get("option3"),
                        "createdAt": self.past_date(
                            config["created_days_ago"]
                        ).isoformat(),
                        "updatedAt": self.past_date(
                            config["created_days_ago"]
                        ).isoformat(),
                    }
                }
            )

        return variant_edges

    def _generate_simple_variant(
        self, config: Dict, product_index: int
    ) -> List[Dict[str, Any]]:
        """Generate a simple single variant for products that don't need complex variants."""
        min_price, max_price = config["price_range"]
        price = round(random.uniform(min_price, max_price), 2)
        compare_at_price = None
        if config["on_sale"]:
            compare_at_price = round(price * random.uniform(1.2, 1.5), 2)

        min_inv, max_inv = config["inventory_range"]
        inventory = random.randint(min_inv, max_inv)

        return [
            {
                "title": "Default Title",
                "price": str(price),
                "compareAtPrice": str(compare_at_price) if compare_at_price else None,
                "sku": f"{config['handle'].upper().replace('-', '')}-001",
                "inventoryQuantity": inventory,
                "taxable": True,
                "inventoryPolicy": "DENY",
                "position": 1,
            }
        ]

    def _build_product_options(
        self, variants: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build product options based on variant structure."""
        if not variants:
            return []

        # Determine option names based on the first variant
        first_variant = variants[0]["node"]
        options = []

        if first_variant.get("option1"):
            # Determine option name based on the values
            option1_values = [
                v["node"]["option1"] for v in variants if v["node"].get("option1")
            ]
            if option1_values and option1_values[0] in [
                "XS",
                "S",
                "M",
                "L",
                "XL",
                "XXL",
            ]:
                option_name = "Size"
            elif option1_values and option1_values[0] in self.clothing_colors:
                option_name = "Color"
            elif option1_values and option1_values[0] in self.home_sizes:
                option_name = "Size"
            else:
                option_name = "Option 1"

            options.append(
                {
                    "name": option_name,
                    "position": 1,
                    "values": list(
                        set(
                            v["node"]["option1"]
                            for v in variants
                            if v["node"].get("option1")
                        )
                    ),
                }
            )

        if first_variant.get("option2"):
            # Determine option name based on the values
            option2_values = [
                v["node"]["option2"] for v in variants if v["node"].get("option2")
            ]
            if option2_values and option2_values[0] in self.clothing_colors:
                option_name = "Color"
            elif option2_values and option2_values[0] in self.accessories_materials:
                option_name = "Material"
            elif option2_values and option2_values[0] in self.electronics_storage:
                option_name = "Storage"
            elif option2_values and option2_values[0] in self.sports_resistance:
                option_name = "Resistance"
            else:
                option_name = "Style"

            options.append(
                {
                    "name": option_name,
                    "position": 2,
                    "values": list(
                        set(
                            v["node"]["option2"]
                            for v in variants
                            if v["node"].get("option2")
                        )
                    ),
                }
            )

        if first_variant.get("option3"):
            options.append(
                {
                    "name": "Storage",
                    "position": 3,
                    "values": list(
                        set(
                            v["node"]["option3"]
                            for v in variants
                            if v["node"].get("option3")
                        )
                    ),
                }
            )

        return options

    def _build_media_edges(self, product_index: int, config: Dict) -> List[Dict]:
        """Build media edges for product with real image URLs."""
        media_edges = []

        # Real image URLs for different product categories
        real_images = {
            # Clothing images
            "clothing": [
                "https://images.unsplash.com/photo-1551698618-1dfe5d97d256?w=800&h=800&fit=crop",
                "https://images.unsplash.com/photo-1594633312681-425c7b97ccd1?w=800&h=800&fit=crop",
                "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=800&h=800&fit=crop",
                "https://images.unsplash.com/photo-1571945153237-4929e783af4a?w=800&h=800&fit=crop",
                "https://images.unsplash.com/photo-1583743814966-8936f37f0c7e?w=800&h=800&fit=crop",
            ],
            # Accessories images
            "accessories": [
                "https://images.unsplash.com/photo-1511499767150-a48a237f0cfe?w=800&h=800&fit=crop",
                "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=800&h=800&fit=crop",
                "https://images.unsplash.com/photo-1583394838336-acd977736f90?w=800&h=800&fit=crop",
                "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=800&h=800&fit=crop",
                "https://images.unsplash.com/photo-1583394838336-acd977736f90?w=800&h=800&fit=crop",
            ],
            # Electronics images
            "electronics": [
                "https://images.unsplash.com/photo-1592750475338-74b7b21085ab?w=800&h=800&fit=crop",
                "https://images.unsplash.com/photo-1572569511254-d8f925fe2cbb?w=800&h=800&fit=crop",
                "https://images.unsplash.com/photo-1601972602288-d1bcf3b5b8b5?w=800&h=800&fit=crop",
                "https://images.unsplash.com/photo-1592750475338-74b7b21085ab?w=800&h=800&fit=crop",
                "https://images.unsplash.com/photo-1572569511254-d8f925fe2cbb?w=800&h=800&fit=crop",
            ],
            # Home & Garden images
            "home": [
                "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=800&h=800&fit=crop",
                "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=800&h=800&fit=crop",
                "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=800&h=800&fit=crop",
                "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=800&h=800&fit=crop",
                "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=800&h=800&fit=crop",
            ],
            # Sports & Fitness images
            "sports": [
                "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=800&h=800&fit=crop",
                "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=800&h=800&fit=crop",
                "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=800&h=800&fit=crop",
                "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=800&h=800&fit=crop",
                "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=800&h=800&fit=crop",
            ],
        }

        # Determine product category and select appropriate images
        product_type = config.get("productType", "Clothing").lower()
        if "clothing" in product_type or "apparel" in product_type:
            category_images = real_images["clothing"]
        elif (
            "accessories" in product_type
            or "bag" in product_type
            or "sunglasses" in product_type
        ):
            category_images = real_images["accessories"]
        elif (
            "electronics" in product_type
            or "tech" in product_type
            or "gadget" in product_type
        ):
            category_images = real_images["electronics"]
        elif (
            "home" in product_type
            or "garden" in product_type
            or "decor" in product_type
        ):
            category_images = real_images["home"]
        elif (
            "sports" in product_type
            or "fitness" in product_type
            or "athletic" in product_type
        ):
            category_images = real_images["sports"]
        else:
            category_images = real_images["clothing"]  # Default to clothing

        # Add main product image
        main_image_url = category_images[product_index % len(category_images)]
        media_edges.append(
            {
                "node": {
                    "id": f"gid://shopify/MediaImage/{product_index}",
                    "image": {
                        "url": main_image_url,
                        "altText": f"{config['title']} - Main view",
                        "width": 800,
                        "height": 800,
                    },
                }
            }
        )

        # Add additional product images (2-3 more)
        for i in range(1, 4):
            additional_image_url = category_images[
                (product_index + i) % len(category_images)
            ]
            media_edges.append(
                {
                    "node": {
                        "id": f"gid://shopify/MediaImage/{product_index}_{i}",
                        "image": {
                            "url": additional_image_url,
                            "altText": f"{config['title']} - View {i+1}",
                            "width": 800,
                            "height": 800,
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
