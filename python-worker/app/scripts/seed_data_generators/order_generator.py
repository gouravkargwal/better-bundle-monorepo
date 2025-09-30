"""
Order data generator for creating realistic purchase patterns.
"""

import random
from typing import Dict, Any, List
from .base_generator import BaseGenerator


class OrderGenerator(BaseGenerator):
    """Generates realistic order data with diverse purchase patterns."""

    def generate_orders(
        self,
        customer_ids: List[str],
        product_variant_ids: List[str],
        product_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """Generate 12 diverse orders with realistic patterns."""
        order_configs = [
            # Alice (VIP) - Multiple orders showing loyalty
            {
                "customer_index": 0,  # Alice
                "order_type": "clothing_bundle",
                "products": [0, 1, 2],  # Hoodie, T-shirt, Jeans
                "quantities": [1, 2, 1],
                "days_ago": 5,
                "order_name": "#1001",
                "description": "Alice's clothing bundle purchase",
            },
            {
                "customer_index": 0,  # Alice
                "order_type": "accessories",
                "products": [5, 6],  # Sunglasses, Bag
                "quantities": [1, 1],
                "days_ago": 3,
                "order_name": "#1002",
                "description": "Alice's accessories purchase",
            },
            {
                "customer_index": 0,  # Alice
                "order_type": "electronics",
                "products": [10, 11],  # Earbuds, Smart Watch
                "quantities": [1, 1],
                "days_ago": 1,
                "order_name": "#1003",
                "description": "Alice's electronics purchase",
            },
            # Charlie (Moderate) - Electronics focused
            {
                "customer_index": 2,  # Charlie
                "order_type": "electronics_bundle",
                "products": [10, 12],  # Earbuds, Phone Case
                "quantities": [1, 2],
                "days_ago": 7,
                "order_name": "#1004",
                "description": "Charlie's electronics bundle",
            },
            {
                "customer_index": 2,  # Charlie
                "order_type": "accessories",
                "products": [5, 7],  # Sunglasses, Scarf
                "quantities": [1, 1],
                "days_ago": 4,
                "order_name": "#1005",
                "description": "Charlie's accessories purchase",
            },
            # Eve (Cross-category) - Diverse purchases
            {
                "customer_index": 4,  # Eve
                "order_type": "cross_category",
                "products": [0, 10],  # Hoodie, Earbuds
                "quantities": [1, 1],
                "days_ago": 6,
                "order_name": "#1006",
                "description": "Eve's cross-category purchase",
            },
            {
                "customer_index": 4,  # Eve
                "order_type": "fashion_accessories",
                "products": [7, 8],  # Scarf, Belt
                "quantities": [2, 1],
                "days_ago": 2,
                "order_name": "#1007",
                "description": "Eve's fashion accessories",
            },
            # Frank (Tech Enthusiast) - Electronics only
            {
                "customer_index": 5,  # Frank
                "order_type": "tech_bundle",
                "products": [11, 12, 13],  # Smart Watch, Phone Case, Charger
                "quantities": [1, 1, 1],
                "days_ago": 8,
                "order_name": "#1008",
                "description": "Frank's tech bundle",
            },
            {
                "customer_index": 5,  # Frank
                "order_type": "electronics",
                "products": [14],  # Bluetooth Speaker
                "quantities": [1],
                "days_ago": 3,
                "order_name": "#1009",
                "description": "Frank's speaker purchase",
            },
            # Grace (Fashion Lover) - Clothing and accessories
            {
                "customer_index": 6,  # Grace
                "order_type": "fashion_bundle",
                "products": [1, 2, 6],  # T-shirt, Jeans, Bag
                "quantities": [3, 1, 1],
                "days_ago": 4,
                "order_name": "#1010",
                "description": "Grace's fashion bundle",
            },
            {
                "customer_index": 6,  # Grace
                "order_type": "accessories",
                "products": [5, 7],  # Sunglasses, Scarf
                "quantities": [1, 2],
                "days_ago": 1,
                "order_name": "#1011",
                "description": "Grace's accessories purchase",
            },
            # Henry (Bargain Hunter) - Sale items
            {
                "customer_index": 7,  # Henry
                "order_type": "bargain_bundle",
                "products": [2, 4, 9],  # Jeans (on sale), Sweater, Cap
                "quantities": [1, 1, 2],
                "days_ago": 6,
                "order_name": "#1012",
                "description": "Henry's bargain purchase",
            },
        ]

        return self._build_order_payloads(
            order_configs, customer_ids, product_variant_ids, product_ids
        )

    def _build_order_payloads(
        self,
        order_configs: List[Dict],
        customer_ids: List[str],
        product_variant_ids: List[str],
        product_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """Build complete order payloads from configurations."""
        orders = []

        for i, config in enumerate(order_configs, 1):
            order_id = self.dynamic_ids[f"order_{i}_id"]
            customer_id = customer_ids[config["customer_index"]]

            # Build line items
            line_items = []
            total_amount = 0.0

            for j, (product_index, quantity) in enumerate(
                zip(config["products"], config["quantities"])
            ):
                line_item_id = self.dynamic_ids[f"line_item_{len(line_items) + 1}_id"]
                variant_id = product_variant_ids[product_index]

                # Get product details (simplified pricing)
                price = self._get_product_price(product_index)
                line_total = price * quantity
                total_amount += line_total

                line_item = {
                    "node": {
                        "id": line_item_id,
                        "quantity": quantity,
                        "originalUnitPriceSet": {
                            "shopMoney": {
                                "amount": str(price),
                                "currencyCode": "USD",
                            }
                        },
                        "discountedUnitPriceSet": {
                            "shopMoney": {
                                "amount": str(price),
                                "currencyCode": "USD",
                            }
                        },
                        "title": self._get_product_title(product_index),
                        "variant": {
                            "id": variant_id,
                            "title": "Default Title",
                            "price": str(price),
                            "sku": f"SKU-{product_index:03d}",
                            "barcode": None,
                            "taxable": True,
                            "inventoryPolicy": "DENY",
                            "position": 1,
                            "createdAt": self.past_date(30).isoformat(),
                            "updatedAt": self.past_date(30).isoformat(),
                            "product": {
                                "id": (
                                    product_ids[product_index]
                                    if product_index < len(product_ids)
                                    else f"gid://shopify/Product/{product_index}"
                                )
                            },
                        },
                    }
                }
                line_items.append(line_item)

            # Build customer data
            customer_data = self._build_customer_data(
                customer_id, config["customer_index"]
            )

            # Build order payload
            order_payload = {
                "id": order_id,
                "name": config["order_name"],
                "email": customer_data["email"],
                "customer": customer_data,
                "lineItems": {"edges": line_items},
                "totalPriceSet": {
                    "shopMoney": {
                        "amount": str(round(total_amount, 2)),
                        "currencyCode": "USD",
                    }
                },
                "subtotalPriceSet": {
                    "shopMoney": {
                        "amount": str(round(total_amount, 2)),
                        "currencyCode": "USD",
                    }
                },
                "totalTaxSet": {"shopMoney": {"amount": "0.00", "currencyCode": "USD"}},
                "totalShippingPriceSet": {
                    "shopMoney": {"amount": "0.00", "currencyCode": "USD"}
                },
                "totalRefundedSet": {
                    "shopMoney": {"amount": "0.00", "currencyCode": "USD"}
                },
                "totalOutstandingSet": {
                    "shopMoney": {
                        "amount": str(round(total_amount, 2)),
                        "currencyCode": "USD",
                    }
                },
                "fulfillments": [],
                "transactions": [
                    {
                        "id": f"gid://shopify/OrderTransaction/{i}",
                        "kind": "SALE",
                        "status": "SUCCESS",
                        "amount": str(round(total_amount, 2)),
                        "gateway": "shopify_payments",
                        "createdAt": self.past_date(config["days_ago"]).isoformat(),
                    }
                ],
                "createdAt": self.past_date(config["days_ago"]).isoformat(),
                "updatedAt": self.past_date(config["days_ago"]).isoformat(),
                "processedAt": self.past_date(config["days_ago"]).isoformat(),
                "cancelledAt": None,
                "cancelReason": None,
                "tags": ["processed", config["order_type"]],
                "note": config["description"],
                "confirmed": True,
                "test": False,
                "customerLocale": "en-US",
                "currencyCode": "USD",
                "presentmentCurrencyCode": "USD",
                "discountApplications": {"edges": []},
                "metafields": {"edges": []},
            }

            orders.append(order_payload)

        return orders

    def _get_product_price(self, product_index: int) -> float:
        """Get realistic price for product index."""
        # Simplified pricing based on category
        if product_index < 5:  # Clothing
            return round(random.uniform(20, 80), 2)
        elif product_index < 10:  # Accessories
            return round(random.uniform(15, 60), 2)
        else:  # Electronics
            return round(random.uniform(25, 150), 2)

    def _get_product_title(self, product_index: int) -> str:
        """Get product title for index."""
        titles = [
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
        return (
            titles[product_index]
            if product_index < len(titles)
            else f"Product {product_index + 1}"
        )

    def _build_customer_data(
        self, customer_id: str, customer_index: int
    ) -> Dict[str, Any]:
        """Build customer data for order."""
        customer_names = [
            "Alice Johnson",
            "Bob Smith",
            "Charlie Brown",
            "Dana Lee",
            "Eve Adams",
            "Frank Wilson",
            "Grace Taylor",
            "Henry Davis",
        ]
        customer_emails = [
            "alice.johnson@email.com",
            "bob.smith@email.com",
            "charlie.brown@email.com",
            "dana.lee@email.com",
            "eve.adams@email.com",
            "frank.wilson@email.com",
            "grace.taylor@email.com",
            "henry.davis@email.com",
        ]

        return {
            "id": customer_id,
            "displayName": customer_names[customer_index],
            "email": customer_emails[customer_index],
            "createdAt": self.past_date(60).isoformat(),
            "updatedAt": self.past_date(5).isoformat(),
            "state": "ENABLED",
            "verifiedEmail": True,
            "defaultAddress": {
                "id": f"gid://shopify/MailingAddress/{customer_index + 1}",
                "address1": "123 Main Street",
                "city": "New York",
                "province": "New York",
                "country": "United States",
                "zip": "10001",
                "phone": "+1-555-0123",
                "provinceCode": "NY",
                "countryCodeV2": "US",
            },
        }
