"""
CSV-based product generator that parses Shopify product CSVs.
"""

import csv
import os
import random
from typing import Dict, Any, List, Optional
from .base_generator import BaseGenerator


class CsvProductGenerator(BaseGenerator):
    """Parses a Shopify product CSV and generates product payloads for GraphQL seeding."""

    def __init__(
        self,
        shop_domain: str = "fashion-store.myshopify.com",
        csv_path: Optional[str] = None,
    ):
        super().__init__(shop_domain)
        if csv_path is None:
            csv_path = os.path.join(
                os.path.dirname(__file__), "..", "csv_data", "fashion.csv"
            )
        self.csv_path = os.path.abspath(csv_path)

    def generate_products(self) -> List[Dict[str, Any]]:
        """Parse CSV and return product payloads matching ProductGenerator output format."""
        raw_products = self._parse_csv()
        return self._build_product_payloads(raw_products)

    def _parse_csv(self) -> List[Dict[str, Any]]:
        """Parse Shopify CSV format into structured product dicts.

        The CSV uses multi-row products:
        - First row per Handle: Title, Body, Vendor, Type, Tags, Option Names, first variant, first image
        - Subsequent rows: additional variants (have Option Values + SKU + Price)
          or additional images (have Image Src but empty variant fields)
        """
        products: Dict[str, Dict[str, Any]] = {}

        with open(self.csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                handle = row.get("Handle", "").strip()
                if not handle:
                    continue

                if handle not in products:
                    products[handle] = {
                        "handle": handle,
                        "title": row.get("Title", "").strip(),
                        "body_html": row.get("Body (HTML)", "").strip(),
                        "vendor": row.get("Vendor", "").strip(),
                        "product_type": row.get("Type", "").strip(),
                        "tags": [
                            t.strip()
                            for t in row.get("Tags", "").split(",")
                            if t.strip()
                        ],
                        "option1_name": row.get("Option1 Name", "").strip(),
                        "option2_name": row.get("Option2 Name", "").strip(),
                        "option3_name": row.get("Option3 Name", "").strip(),
                        "variants": [],
                        "images": [],
                    }

                product = products[handle]

                # Determine if this row is a variant or image-only
                sku = row.get("Variant SKU", "").strip()
                price = row.get("Variant Price", "").strip()
                has_variant_data = bool(sku or price)

                if has_variant_data:
                    compare_at = row.get("Variant Compare At Price", "").strip()
                    inv_qty = row.get("Variant Inventory Qty", "").strip()
                    product["variants"].append(
                        {
                            "option1": row.get("Option1 Value", "").strip(),
                            "option2": row.get("Option2 Value", "").strip(),
                            "option3": row.get("Option3 Value", "").strip(),
                            "sku": sku,
                            "price": price,
                            "compare_at_price": compare_at if compare_at else None,
                            "inventory_qty": (
                                int(inv_qty)
                                if inv_qty and inv_qty.isdigit()
                                else 0
                            ),
                            "requires_shipping": row.get(
                                "Variant Requires Shipping", ""
                            )
                            .strip()
                            .lower()
                            == "true",
                            "taxable": row.get("Variant Taxable", "")
                            .strip()
                            .lower()
                            == "true",
                            "weight_unit": row.get("Variant Weight Unit", "").strip()
                            or "kg",
                        }
                    )

                # Capture image (every row may have an Image Src)
                img_src = row.get("Image Src", "").strip()
                if img_src:
                    img_alt = row.get("Image Alt Text", "").strip()
                    product["images"].append(
                        {
                            "src": img_src,
                            "alt": img_alt or product["title"],
                        }
                    )

        return list(products.values())

    def _build_product_payloads(
        self, raw_products: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build GraphQL-ready product payloads from parsed CSV data."""
        products = []

        for i, raw in enumerate(raw_products):
            product_index = i + 1
            product_id = self.dynamic_ids.get(
                f"product_{product_index}_id"
            ) or f"gid://shopify/Product/{self.base_id + product_index}"

            # Build variants
            variant_edges = []
            for j, v in enumerate(raw["variants"]):
                variant_id = f"gid://shopify/ProductVariant/{self.base_id + 1000 + product_index * 10 + j}"
                variant_edges.append(
                    {
                        "node": {
                            "id": variant_id,
                            "title": self._build_variant_title(v),
                            "sku": v["sku"],
                            "price": v["price"],
                            "compareAtPrice": v["compare_at_price"],
                            "inventoryQuantity": v["inventory_qty"],
                            "taxable": v["taxable"],
                            "inventoryPolicy": "DENY",
                            "position": j + 1,
                            "option1": v["option1"] or None,
                            "option2": v["option2"] or None,
                            "option3": v["option3"] or None,
                            "createdAt": self.past_date(
                                random.randint(10, 90)
                            ).isoformat(),
                            "updatedAt": self.past_date(
                                random.randint(1, 10)
                            ).isoformat(),
                        }
                    }
                )

            # Build media edges from images (limit to 4 per product)
            media_edges = []
            for k, img in enumerate(raw["images"][:4]):
                media_edges.append(
                    {
                        "node": {
                            "id": f"gid://shopify/MediaImage/{product_index}_{k}",
                            "image": {
                                "url": img["src"],
                                "altText": img["alt"],
                                "width": 800,
                                "height": 800,
                            },
                        }
                    }
                )

            # Build product options
            product_options = self._build_product_options(raw, variant_edges)

            # Total inventory
            total_inventory = sum(v["inventory_qty"] for v in raw["variants"])

            # SEO from CSV or fallback
            seo_title = raw["title"]
            seo_description = (
                raw["body_html"][:160] if raw["body_html"] else raw["title"]
            )

            product_payload = {
                "id": product_id,
                "title": raw["title"],
                "handle": raw["handle"],
                "description": raw["body_html"],
                "productType": raw["product_type"] or "Fashion",
                "vendor": raw["vendor"] or "Unknown",
                "totalInventory": max(total_inventory, 1),
                "onlineStoreUrl": f"https://{self.shop_domain}/products/{raw['handle']}",
                "onlineStorePreviewUrl": f"https://{self.shop_domain}/products/{raw['handle']}",
                "seo": {"title": seo_title, "description": seo_description},
                "templateSuffix": None,
                "media": {"edges": media_edges},
                "variants": {"edges": variant_edges},
                "options": product_options,
                "tags": raw["tags"],
                "createdAt": self.past_date(random.randint(30, 120)).isoformat(),
            }

            products.append(product_payload)

        return products

    def _build_variant_title(self, variant: Dict) -> str:
        """Build variant title from option values."""
        parts = []
        if variant.get("option1"):
            parts.append(variant["option1"])
        if variant.get("option2"):
            parts.append(variant["option2"])
        if variant.get("option3"):
            parts.append(variant["option3"])
        return " / ".join(parts) if parts else "Default Title"

    def _build_product_options(
        self, raw: Dict, variant_edges: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build product options from CSV option names and variant values."""
        options = []

        if raw["option1_name"]:
            values = list(
                set(
                    v["node"]["option1"]
                    for v in variant_edges
                    if v["node"].get("option1")
                )
            )
            if values:
                options.append(
                    {
                        "name": raw["option1_name"],
                        "position": 1,
                        "values": values,
                    }
                )

        if raw["option2_name"]:
            values = list(
                set(
                    v["node"]["option2"]
                    for v in variant_edges
                    if v["node"].get("option2")
                )
            )
            if values:
                options.append(
                    {
                        "name": raw["option2_name"],
                        "position": 2,
                        "values": values,
                    }
                )

        if raw["option3_name"]:
            values = list(
                set(
                    v["node"]["option3"]
                    for v in variant_edges
                    if v["node"].get("option3")
                )
            )
            if values:
                options.append(
                    {
                        "name": raw["option3_name"],
                        "position": 3,
                        "values": values,
                    }
                )

        # Fallback for products with no option names
        if not options and variant_edges:
            options.append(
                {
                    "name": "Title",
                    "position": 1,
                    "values": ["Default Title"],
                }
            )

        return options
