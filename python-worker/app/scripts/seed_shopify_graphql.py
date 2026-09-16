"""
Shopify Development Store Seeder using GraphQL API
Creates products, customers, collections, and orders in a Shopify development store using GraphQL.

Usage:
  - Env vars: export SHOP_DOMAIN=your-store.myshopify.com SHOPIFY_ACCESS_TOKEN=shpat_...
  - Or CLI:   python seed_shopify_graphql.py --shop your-store.myshopify.com --token shpat_...
"""

import asyncio
import sys
import os
import argparse
import requests
import time
import random
import json
from typing import Dict, Any, List, Optional, Tuple

# Add the python-worker directory to Python path
python_worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, python_worker_dir)

from app.scripts.seed_data_generators.base_generator import BaseGenerator
from app.scripts.seed_data_generators.csv_product_generator import CsvProductGenerator
from app.scripts.seed_data_generators.customer_generator import CustomerGenerator
from app.scripts.seed_data_generators.order_generator import OrderGenerator


class ShopifyGraphQLSeeder:
    """Seeds products, customers, collections, and orders into a Shopify store using GraphQL."""

    def __init__(self, shop_domain: str, access_token: str):
        self.shop_domain = shop_domain
        self.access_token = access_token
        self.api_version = "2026-07"  # newest version Shopify still supports
        self.base_url = f"https://{shop_domain}/admin/api/{self.api_version}"

        # Generators
        self.base_generator = BaseGenerator(shop_domain)
        self.product_generator = CsvProductGenerator(shop_domain)
        self.customer_generator = CustomerGenerator(shop_domain)
        self.order_generator = OrderGenerator(shop_domain)

        # Track created resources
        self.created_products: Dict[str, Dict[str, Any]] = {}
        self.created_customers: Dict[str, Dict[str, Any]] = {}
        self.created_orders: Dict[str, Dict[str, Any]] = {}
        self.created_collections: Dict[str, Dict[str, Any]] = {}

        # Cache for publication ID and location ID
        self._online_store_publication_id: Optional[str] = None
        self._store_location_id: Optional[str] = None

        # Checkpoint for resume capability
        self._checkpoint_path = os.path.join(
            os.path.dirname(__file__), f"checkpoint_{shop_domain.replace('.', '_')}.json"
        )
        self._checkpoint = self._load_checkpoint()

    def _load_checkpoint(self) -> Dict[str, Any]:
        """Load checkpoint from disk if it exists."""
        if os.path.exists(self._checkpoint_path):
            try:
                with open(self._checkpoint_path, "r") as f:
                    data = json.load(f)
                print(f"  📋 Loaded checkpoint: {len(data.get('created_products', {}))} products, "
                      f"{len(data.get('created_customers', {}))} customers, "
                      f"{len(data.get('created_orders', {}))} orders")
                return data
            except Exception as e:
                print(f"  ⚠️ Failed to load checkpoint: {e}")
        return {
            "created_products": {},
            "created_customers": {},
            "created_orders": {},
            "created_collections": {},
            "step": "products",
        }

    def _save_checkpoint(self) -> None:
        """Save current progress to disk."""
        self._checkpoint["created_products"] = self.created_products
        self._checkpoint["created_customers"] = self.created_customers
        self._checkpoint["created_orders"] = self.created_orders
        self._checkpoint["created_collections"] = self.created_collections
        try:
            with open(self._checkpoint_path, "w") as f:
                json.dump(self._checkpoint, f, indent=2)
        except Exception as e:
            print(f"  ⚠️ Failed to save checkpoint: {e}")

    def _clear_checkpoint(self) -> None:
        """Remove checkpoint file after successful completion."""
        try:
            if os.path.exists(self._checkpoint_path):
                os.remove(self._checkpoint_path)
                print("  🧹 Checkpoint cleared (seed complete)")
        except Exception:
            pass

    def _graphql_request(
        self,
        query: str,
        variables: Optional[Dict] = None,
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/graphql.json"
        headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

        # Add delay to respect rate limits
        if retry_count > 0:
            delay = min(
                2**retry_count + random.uniform(0, 1), 10
            )  # Exponential backoff with jitter
            print(f"    ⏳ Rate limited, waiting {delay:.1f}s...")
            time.sleep(delay)
        else:
            # Small delay between requests to avoid hitting rate limits
            time.sleep(0.5)

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            resp = requests.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            result = resp.json()

            # Check for GraphQL errors
            if "errors" in result:
                error_messages = [
                    error.get("message", "Unknown error") for error in result["errors"]
                ]
                raise Exception(f"GraphQL errors: {', '.join(error_messages)}")

            return result

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429 and retry_count < 3:  # Rate limited
                return self._graphql_request(query, variables, retry_count + 1)
            else:
                # Add detailed error logging
                error_details = (
                    f"Status: {e.response.status_code}, Response: {e.response.text}"
                )
                print(f"    🔍 Detailed error: {error_details}")
                raise e

    def _get_product_by_handle(self, handle: str) -> Optional[Dict[str, Any]]:
        """Query Shopify for an existing product by handle."""
        query = """
        query productByHandle($handle: String!) {
            productByHandle(handle: $handle) {
                id
                title
                handle
                variants(first: 50) {
                    nodes {
                        id
                        title
                        price
                    }
                }
            }
        }
        """
        try:
            result = self._graphql_request(query, {"handle": handle})
            return result.get("data", {}).get("productByHandle")
        except Exception:
            return None

    def _get_online_store_publication_id(self) -> str:
        """Fetch the Online Store publication ID for this shop."""
        if self._online_store_publication_id:
            return self._online_store_publication_id

        query = """
        query {
            publications(first: 10) {
                nodes {
                    id
                    name
                }
            }
        }
        """

        try:
            result = self._graphql_request(query)
            publications = result["data"]["publications"]["nodes"]

            # Find the Online Store publication
            for pub in publications:
                if pub["name"] == "Online Store":
                    self._online_store_publication_id = pub["id"]
                    return self._online_store_publication_id

            # Fallback to first publication if Online Store not found
            if publications:
                self._online_store_publication_id = publications[0]["id"]
                return self._online_store_publication_id
            else:
                raise Exception("No publications found")

        except Exception as e:
            print(f"    ⚠️ Failed to fetch publications: {e}")
            # Fallback to hardcoded ID
            self._online_store_publication_id = "gid://shopify/Publication/1"
            return self._online_store_publication_id

    def _get_store_location_id(self) -> str:
        """Fetch the first available location ID for this shop."""
        if self._store_location_id:
            return self._store_location_id

        query = """
        query {
            locations(first: 10) {
                nodes {
                    id
                    name
                }
            }
        }
        """

        try:
            result = self._graphql_request(query)
            locations = result["data"]["locations"]["nodes"]

            # Use the first available location
            if locations:
                self._store_location_id = locations[0]["id"]
                return self._store_location_id
            else:
                raise Exception("No locations found")

        except Exception as e:
            print(f"    ⚠️ Failed to fetch locations: {e}")
            # Fallback to hardcoded ID
            self._store_location_id = "gid://shopify/Location/1"
            return self._store_location_id

    def _create_staged_upload(
        self, filename: str, mime_type: str, file_size: str
    ) -> Dict[str, Any]:
        """Create a staged upload target for an image file."""
        mutation = """
        mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
            stagedUploadsCreate(input: $input) {
                stagedTargets {
                    url
                    resourceUrl
                    parameters {
                        name
                        value
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """

        variables = {
            "input": [
                {
                    "filename": filename,
                    "mimeType": mime_type,
                    "resource": "IMAGE",
                    "fileSize": file_size,
                    "httpMethod": "POST",
                }
            ]
        }

        result = self._graphql_request(mutation, variables)

        if result["data"]["stagedUploadsCreate"]["userErrors"]:
            errors = [
                error["message"]
                for error in result["data"]["stagedUploadsCreate"]["userErrors"]
            ]
            raise Exception(f"Staging upload error: {', '.join(errors)}")

        return result["data"]["stagedUploadsCreate"]["stagedTargets"][0]

    def _upload_to_staged_target(
        self, staged_target: Dict[str, Any], image_url: str
    ) -> str:
        """Download image from external URL and upload to Shopify's staged target."""
        try:
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            image_data = response.content

            form_data = {}
            for param in staged_target["parameters"]:
                form_data[param["name"]] = param["value"]

            files = {"file": image_data}
            upload_response = requests.post(
                staged_target["url"], data=form_data, files=files, timeout=60
            )
            upload_response.raise_for_status()

            return staged_target["resourceUrl"]

        except requests.exceptions.RequestException as e:
            print(f"      ❌ Upload failed: {e}")
            raise

    def _attach_media_to_product(
        self, product_id: str, media_inputs: List[Dict[str, Any]]
    ) -> None:
        """Attach media to product using productCreateMedia mutation."""
        if not media_inputs:
            return

        mutation = """
        mutation productCreateMedia($productId: ID!, $media: [CreateMediaInput!]!) {
            productCreateMedia(productId: $productId, media: $media) {
                media {
                    id
                    alt
                    mediaContentType
                    status
                }
                mediaUserErrors {
                    field
                    message
                    code
                }
            }
        }
        """

        variables = {"productId": product_id, "media": media_inputs}

        try:
            result = self._graphql_request(mutation, variables)

            if result["data"]["productCreateMedia"]["mediaUserErrors"]:
                errors = [
                    f"{error.get('code', 'ERROR')}: {error['message']}"
                    for error in result["data"]["productCreateMedia"]["mediaUserErrors"]
                ]
                print(f"    ⚠️ Media errors: {', '.join(errors)}")

        except Exception as e:
            print(f"    ⚠️ Failed to attach media: {e}")

    def _add_media_to_product_from_urls(
        self, product_id: str, media_edges: List[Dict]
    ) -> None:
        """
        Process external image URLs through staged uploads and attach to product.
        This is the proper way to add images from external URLs.
        """
        media_inputs = []

        for i, media_edge in enumerate(media_edges, 1):
            media_node = media_edge["node"]

            if media_node.get("image"):
                try:
                    image_url = media_node["image"]["url"]
                    filename = (
                        image_url.split("/")[-1].split("?")[0] or f"image_{i}.jpg"
                    )

                    response = requests.head(image_url, timeout=10)
                    file_size = response.headers.get("Content-Length", "0")

                    content_type = response.headers.get("Content-Type", "image/jpeg")
                    if not content_type.startswith("image/"):
                        content_type = "image/jpeg"

                    staged_target = self._create_staged_upload(
                        filename, content_type, file_size
                    )

                    resource_url = self._upload_to_staged_target(
                        staged_target, image_url
                    )

                    media_inputs.append(
                        {
                            "originalSource": resource_url,
                            "mediaContentType": "IMAGE",
                            "alt": media_node["image"].get("altText", filename),
                        }
                    )

                except Exception as e:
                    print(f"    ⚠️ Image {i} failed: {e}")
                    continue

        if media_inputs:
            self._attach_media_to_product(product_id, media_inputs)

    def _batch_publish_products(
        self, product_ids: List[str], publication_id: str
    ) -> bool:
        """Publish multiple products to Online Store in a single batch operation."""
        if not product_ids:
            return True

        print(f"  📡 Publishing {len(product_ids)} products to Online Store...")

        mutation = """
        mutation publishablePublish($id: ID!, $input: [PublicationInput!]!) {
            publishablePublish(id: $id, input: $input) {
                publishable {
                    ... on Product {
                        id
                        title
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """

        success_count = 0
        for product_id in product_ids:
            try:
                variables = {
                    "id": product_id,
                    "input": [{"publicationId": publication_id}],
                }

                result = self._graphql_request(mutation, variables)

                if result["data"]["publishablePublish"]["userErrors"]:
                    errors = [
                        error["message"]
                        for error in result["data"]["publishablePublish"]["userErrors"]
                    ]
                    print(f"    ⚠️ Failed to publish {product_id}: {', '.join(errors)}")
                else:
                    success_count += 1

            except Exception as e:
                print(f"    ⚠️ Failed to publish {product_id}: {e}")

        print(
            f"  ✅ Published {success_count}/{len(product_ids)} products"
        )
        return success_count > 0

    def _batch_publish_collections(
        self, collection_ids: List[str], publication_id: str
    ) -> bool:
        """Publish multiple collections to Online Store in a single batch operation."""
        if not collection_ids:
            return True

        print(f"  📡 Publishing {len(collection_ids)} collections to Online Store...")

        mutation = """
        mutation publishablePublish($id: ID!, $input: [PublicationInput!]!) {
            publishablePublish(id: $id, input: $input) {
                publishable {
                    ... on Collection {
                        id
                        title
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """

        success_count = 0
        for collection_id in collection_ids:
            try:
                variables = {
                    "id": collection_id,
                    "input": [{"publicationId": publication_id}],
                }

                result = self._graphql_request(mutation, variables)

                if result["data"]["publishablePublish"]["userErrors"]:
                    errors = [
                        error["message"]
                        for error in result["data"]["publishablePublish"]["userErrors"]
                    ]
                    print(
                        f"    ⚠️ Failed to publish collection {collection_id}: {', '.join(errors)}"
                    )
                else:
                    success_count += 1

            except Exception as e:
                print(f"    ⚠️ Failed to publish collection {collection_id}: {e}")

        print(
            f"  ✅ Successfully published {success_count}/{len(collection_ids)} collections"
        )
        return success_count > 0

    async def create_products(self) -> Dict[str, Dict[str, Any]]:
        print("📦 Creating products...")
        products = self.product_generator.generate_products()
        total = len(products)

        # Resume from checkpoint — skip already-created products
        already_created = self._checkpoint.get("created_products", {})
        created_handles = {v["handle"] for v in already_created.values()}
        if created_handles:
            self.created_products.update(already_created)
            print(f"  ⏩ Resuming: {len(created_handles)}/{total} products")

        # Get publication ID once at the beginning
        publication_id = self._get_online_store_publication_id()

        # Collect all product IDs for batch publishing (include previously created)
        created_product_ids = [p["id"] for p in self.created_products.values()]

        for i, product_data in enumerate(products, 1):
            # Skip products that were already created in a previous run
            if product_data["handle"] in created_handles:
                continue

            try:
                # Convert product data to GraphQL format
                variants = []
                for v_edge in product_data["variants"]["edges"]:
                    v = v_edge["node"]
                    variants.append(
                        {
                            "title": v["title"],
                            "price": v["price"],
                            "sku": v["sku"],
                            "inventoryQuantity": v["inventoryQuantity"],
                            "compareAtPrice": v.get("compareAtPrice"),
                            "taxable": v["taxable"],
                            "inventoryPolicy": v["inventoryPolicy"],
                            "requiresShipping": True,
                            "fulfillmentService": "manual",
                            "option1": v.get("option1"),
                            "option2": v.get("option2"),
                            "option3": v.get("option3"),
                        }
                    )

                # Create product mutation (without media)
                mutation = """
                mutation productSet($input: ProductSetInput!) {
                    productSet(input: $input) {
                        product {
                            id
                            title
                            handle
                            variants(first: 10) {
                                nodes {
                                    id
                                    title
                                    price
                                    sku
                                }
                            }
                        }
                        userErrors {
                            field
                            message
                        }
                    }
                }
                """

                # Create product options from the product data
                product_options = []
                if product_data.get("options"):
                    for option in product_data["options"]:
                        product_options.append(
                            {
                                "name": option["name"],
                                "position": option["position"],
                                "values": [
                                    {"name": value} for value in option["values"]
                                ],
                            }
                        )

                # Convert variants to productSet format with proper option values and inventory
                product_variants = []
                for variant_data in variants:
                    # Build option values from the variant data
                    option_values = []
                    if variant_data.get("option1") and len(product_options) > 0:
                        option_values.append(
                            {
                                "optionName": product_options[0]["name"],
                                "name": variant_data["option1"],
                            }
                        )
                    if variant_data.get("option2") and len(product_options) > 1:
                        option_values.append(
                            {
                                "optionName": product_options[1]["name"],
                                "name": variant_data["option2"],
                            }
                        )
                    if variant_data.get("option3") and len(product_options) > 2:
                        option_values.append(
                            {
                                "optionName": product_options[2]["name"],
                                "name": variant_data["option3"],
                            }
                        )

                    product_variants.append(
                        {
                            "price": variant_data["price"],
                            "sku": variant_data["sku"],
                            "compareAtPrice": variant_data.get("compareAtPrice"),
                            "taxable": variant_data["taxable"],
                            "inventoryPolicy": variant_data["inventoryPolicy"],
                            "inventoryItem": {
                                "tracked": True,
                                "requiresShipping": True,
                            },
                            "inventoryQuantities": [
                                {
                                    "locationId": self._get_store_location_id(),
                                    "name": "available",
                                    "quantity": variant_data["inventoryQuantity"],
                                }
                            ],
                            "optionValues": option_values,
                        }
                    )

                variables = {
                    "input": {
                        "title": product_data["title"],
                        "vendor": product_data["vendor"],
                        "productType": product_data["productType"],
                        "handle": product_data["handle"],
                        "tags": product_data.get("tags", []),
                        "status": "ACTIVE",
                        "productOptions": product_options,
                        "variants": product_variants,
                    }
                }

                result = self._graphql_request(mutation, variables)

                if result["data"]["productSet"]["userErrors"]:
                    errors = [
                        error["message"]
                        for error in result["data"]["productSet"]["userErrors"]
                    ]
                    error_msg = ", ".join(errors)

                    # Handle "handle already in use" — product was created in a previous run
                    if "already in use" in error_msg:
                        existing = self._get_product_by_handle(product_data["handle"])
                        if existing:
                            variant_ids = [v["id"] for v in existing["variants"]["nodes"]]
                            self.created_products[f"product_{i}"] = {
                                "id": existing["id"],
                                "handle": existing["handle"],
                                "title": existing["title"],
                                "variants": variant_ids,
                            }
                            print(f"  ⏩ [{i}/{total}] {existing['title']} (already exists, skipping)")
                            self._save_checkpoint()
                            continue

                    raise Exception(f"Product creation errors: {error_msg}")

                product = result["data"]["productSet"]["product"]

                # Extract variant IDs for order creation
                variant_ids = []
                for variant_node in product["variants"]["nodes"]:
                    variant_ids.append(variant_node["id"])

                # Add media after product is created using staged uploads
                if product_data.get("media", {}).get("edges"):
                    self._add_media_to_product_from_urls(
                        product["id"], product_data["media"]["edges"]
                    )

                self.created_products[f"product_{i}"] = {
                    "id": product["id"],
                    "handle": product["handle"],
                    "title": product["title"],
                    "variants": variant_ids,
                }
                created_product_ids.append(product["id"])
                print(f"  ✅ [{i}/{total}] {product['title']} ({product['id']})")

                # Save checkpoint after every product
                self._save_checkpoint()

            except Exception as e:
                print(f"  ❌ [{i}/{total}] {product_data['title']} failed: {e}")

        # Batch publish all new products to Online Store
        new_ids = [pid for pid in created_product_ids if pid not in [p["id"] for p in already_created.values()]]
        if new_ids:
            self._batch_publish_products(new_ids, publication_id)

        return self.created_products

    async def create_customers(self) -> Dict[str, Dict[str, Any]]:
        print("👥 Creating customers...")
        customers = self.customer_generator.generate_customers()
        total = len(customers)

        # Resume from checkpoint
        already_created = self._checkpoint.get("created_customers", {})
        if already_created:
            self.created_customers.update(already_created)
            print(f"  ⏩ Resuming: {len(already_created)}/{total} customers already created")

        for i, customer_data in enumerate(customers, 1):
            # Skip already-created customers
            if f"customer_{i}" in already_created:
                continue

            try:
                # Prepare addresses
                addresses = []
                if customer_data.get("defaultAddress"):
                    addr = customer_data["defaultAddress"]
                    addresses.append(
                        {
                            "address1": addr["address1"],
                            "city": addr["city"],
                            "province": addr["province"],
                            "country": addr["country"],
                            "zip": addr["zip"],
                            "phone": addr["phone"],
                            "firstName": customer_data["firstName"],
                            "lastName": customer_data["lastName"],
                        }
                    )

                # Create customer mutation
                mutation = """
                mutation customerCreate($input: CustomerInput!) {
                    customerCreate(input: $input) {
                        customer {
                            id
                            displayName
                        }
                        userErrors {
                            field
                            message
                        }
                    }
                }
                """

                variables = {
                    "input": {
                        "firstName": customer_data["firstName"],
                        "lastName": customer_data["lastName"],
                        "tags": customer_data.get("tags", []),
                        "addresses": addresses,
                    }
                }

                result = self._graphql_request(mutation, variables)

                if result["data"]["customerCreate"]["userErrors"]:
                    errors = [
                        error["message"]
                        for error in result["data"]["customerCreate"]["userErrors"]
                    ]
                    raise Exception(f"Customer creation errors: {', '.join(errors)}")

                customer = result["data"]["customerCreate"]["customer"]
                self.created_customers[f"customer_{i}"] = {
                    "id": customer["id"],
                    "displayName": customer.get(
                        "displayName",
                        f"{customer_data['firstName']} {customer_data['lastName']}",
                    ),
                }
                print(f"  ✅ [{i}/{total}] {customer['displayName']}")
                self._save_checkpoint()

            except Exception as e:
                print(f"  ❌ [{i}/{total}] Customer failed: {e}")
        return self.created_customers

    def _generate_collections_from_products(self) -> List[Dict[str, Any]]:
        # Build two collections with proper product distribution
        product_ids = [p["id"] for p in self.created_products.values()]
        collections = []

        # Use timestamp to make handles unique
        timestamp = int(time.time())

        # Split products evenly
        mid_point = len(product_ids) // 2

        collections.append(
            {
                "title": "Summer Essentials",
                "handle": f"summer-essentials-{timestamp}",
                "descriptionHtml": "Perfect for summer - clothing and accessories",
                "productIds": product_ids[:mid_point],
            }
        )
        collections.append(
            {
                "title": "Tech Gear",
                "handle": f"tech-gear-{timestamp}",
                "descriptionHtml": "Latest technology and electronics",
                "productIds": product_ids[mid_point:],
            }
        )
        return collections

    async def create_collections(self) -> Dict[str, Dict[str, Any]]:
        print("📚 Creating collections and linking products...")
        if not self.created_products:
            print("  ⚠️ No products available to add to collections")
            return {}

        # Resume from checkpoint
        already_created = self._checkpoint.get("created_collections", {})
        if already_created:
            self.created_collections.update(already_created)
            print(f"  ⏩ Resuming: {len(already_created)} collections already created")
            return self.created_collections

        collections = self._generate_collections_from_products()
        created_collection_ids = []

        for i, c in enumerate(collections, 1):
            try:
                # Create collection mutation
                create_mutation = """
                mutation collectionCreate($input: CollectionInput!) {
                    collectionCreate(input: $input) {
                        collection {
                            id
                            title
                        }
                        userErrors {
                            field
                            message
                        }
                    }
                }
                """

                create_variables = {
                    "input": {
                        "title": c["title"],
                        "descriptionHtml": c["descriptionHtml"],
                        "handle": c["handle"],
                    }
                }

                result = self._graphql_request(create_mutation, create_variables)

                if result["data"]["collectionCreate"]["userErrors"]:
                    errors = [
                        error["message"]
                        for error in result["data"]["collectionCreate"]["userErrors"]
                    ]
                    raise Exception(f"Collection creation errors: {', '.join(errors)}")

                collection = result["data"]["collectionCreate"]["collection"]
                self.created_collections[f"collection_{i}"] = {
                    "id": collection["id"],
                    "title": collection["title"],
                }
                created_collection_ids.append(collection["id"])

                # Add products to collection
                if c["productIds"]:
                    add_products_mutation = """
                    mutation collectionAddProducts($id: ID!, $productIds: [ID!]!) {
                        collectionAddProducts(id: $id, productIds: $productIds) {
                            collection {
                                id
                                title
                            }
                            userErrors {
                                field
                                message
                            }
                        }
                    }
                    """

                    add_variables = {
                        "id": collection["id"],
                        "productIds": c["productIds"],
                    }

                    add_result = self._graphql_request(
                        add_products_mutation, add_variables
                    )

                    if add_result["data"]["collectionAddProducts"]["userErrors"]:
                        errors = [
                            error["message"]
                            for error in add_result["data"]["collectionAddProducts"][
                                "userErrors"
                            ]
                        ]
                        print(
                            f"    ⚠️ Failed to add products to collection: {', '.join(errors)}"
                        )

                self._save_checkpoint()

            except Exception as e:
                print(f"  ❌ Collection '{c['title']}' failed: {e}")

        # Publish all collections to Online Store after creation
        if created_collection_ids:
            publication_id = self._get_online_store_publication_id()
            self._batch_publish_collections(created_collection_ids, publication_id)

        return self.created_collections

    async def create_orders(self) -> Dict[str, Dict[str, Any]]:
        print("📋 Creating orders...")
        if not self.created_products or not self.created_customers:
            print("  ⚠️ Need products and customers before creating orders")
            return {}

        # Resume from checkpoint
        already_created = self._checkpoint.get("created_orders", {})
        if already_created:
            self.created_orders.update(already_created)
            print(f"  ⏩ Resuming: {len(already_created)} orders already created")

        # Get some products and customers for orders
        customer_ids = [c["id"] for c in self.created_customers.values()]
        product_list = list(self.created_products.values())

        # Baskets are deliberate, not random.
        baskets = self.order_generator.realistic_baskets()
        by_title = {p.get("title"): p for p in product_list if p.get("title")}

        missing = sorted(
            {t for basket in baskets for t in basket if t not in by_title}
        )
        if missing:
            print(f"  ⚠️ Baskets reference {len(missing)} unknown products: {missing}")

        resolved = [
            [by_title[t] for t in basket if t in by_title] for basket in baskets
        ]
        resolved = [b for b in resolved if len(b) >= 2]
        if not resolved:
            print("  ⚠️ No basket could be resolved; falling back to random pairs")
            resolved = [
                random.sample(product_list, min(2, len(product_list)))
                for _ in range(40)
            ]

        repeats_per_basket = 8
        order_count = len(resolved) * repeats_per_basket

        for i in range(1, order_count + 1):
            # Skip already-created orders
            if f"order_{i}" in already_created:
                continue

            try:
                customer_id = random.choice(customer_ids)
                selected_products = resolved[(i - 1) % len(resolved)]

                # Create line items using product variants
                line_items = []
                for product in selected_products:
                    if product.get("variants"):
                        variant_id = product["variants"][0]  # Use first variant
                        quantity = random.randint(1, 3)
                        line_items.append(
                            {
                                "variantId": variant_id,
                                "quantity": quantity,
                            }
                        )

                if not line_items:
                    continue

                # Step 1: Create draft order
                draft_mutation = """
                mutation draftOrderCreate($input: DraftOrderInput!) {
                    draftOrderCreate(input: $input) {
                        draftOrder {
                            id
                            name
                            invoiceUrl
                        }
                        userErrors {
                            field
                            message
                        }
                    }
                }
                """

                draft_variables = {
                    "input": {
                        "lineItems": line_items,
                        "customerId": customer_id,
                        "tags": ["Test Order", f"Order-{i}"],
                    }
                }

                draft_result = self._graphql_request(draft_mutation, draft_variables)

                if draft_result["data"]["draftOrderCreate"]["userErrors"]:
                    errors = [
                        error["message"]
                        for error in draft_result["data"]["draftOrderCreate"][
                            "userErrors"
                        ]
                    ]
                    print(f"  ⚠️ [{i}/{order_count}] Draft order errors: {', '.join(errors)}")
                    continue

                draft_order = draft_result["data"]["draftOrderCreate"]["draftOrder"]

                # Step 2: Complete the draft order to create paid order
                complete_mutation = """
                mutation draftOrderComplete($id: ID!) {
                    draftOrderComplete(id: $id) {
                        draftOrder {
                            id
                            order {
                                id
                                name
                                displayFinancialStatus
                                totalPrice
                            }
                        }
                        userErrors {
                            field
                            message
                        }
                    }
                }
                """

                complete_variables = {"id": draft_order["id"]}
                complete_result = self._graphql_request(
                    complete_mutation, complete_variables
                )

                if complete_result["data"]["draftOrderComplete"]["userErrors"]:
                    errors = [
                        error["message"]
                        for error in complete_result["data"]["draftOrderComplete"][
                            "userErrors"
                        ]
                    ]
                    print(f"  ⚠️ [{i}/{order_count}] Order completion errors: {', '.join(errors)}")
                    continue

                order = complete_result["data"]["draftOrderComplete"]["draftOrder"][
                    "order"
                ]
                self.created_orders[f"order_{i}"] = {
                    "id": order["id"],
                    "name": order["name"],
                    "totalPrice": order["totalPrice"],
                    "financialStatus": order["displayFinancialStatus"],
                }
                print(
                    f"  ✅ [{i}/{order_count}] {order['name']} - ${order['totalPrice']} ({order['displayFinancialStatus']})"
                )

                # Save checkpoint every 10 orders to avoid excessive I/O
                if i % 10 == 0:
                    self._save_checkpoint()

            except Exception as e:
                print(f"  ❌ [{i}/{order_count}] Order failed: {e}")

        # Final checkpoint save
        self._save_checkpoint()
        return self.created_orders

    async def run(self) -> bool:
        print(f"🚀 Seeding: {self.shop_domain}")

        await self.create_products()
        await self.create_customers()
        await self.create_collections()
        await self.create_orders()

        print(f"\n✅ Done: {len(self.created_products)} products, {len(self.created_customers)} customers, {len(self.created_orders)} orders")
        print(f"  🔗 https://{self.shop_domain}/admin")

        # Clear checkpoint on successful completion
        self._clear_checkpoint()
        return bool(self.created_products and self.created_customers)


async def main() -> bool:
    shop_domain = os.environ.get("SHOP_DOMAIN") or os.environ.get("SHOPIFY_SHOP_DOMAIN")
    access_token = os.environ.get("ACCESS_TOKEN") or os.environ.get("SHOPIFY_ACCESS_TOKEN")

    if not shop_domain or not access_token:
        print("Missing env vars: SHOP_DOMAIN and ACCESS_TOKEN")
        return False

    seeder = ShopifyGraphQLSeeder(shop_domain, access_token)
    return await seeder.run()


if __name__ == "__main__":
    asyncio.run(main())
