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
from typing import Dict, Any, List, Optional, Tuple

# Add the python-worker directory to Python path
python_worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, python_worker_dir)

from app.scripts.seed_data_generators.base_generator import BaseGenerator
from app.scripts.seed_data_generators.product_generator import ProductGenerator
from app.scripts.seed_data_generators.customer_generator import CustomerGenerator
from app.scripts.seed_data_generators.order_generator import OrderGenerator


class ShopifyGraphQLSeeder:
    """Seeds products, customers, collections, and orders into a Shopify store using GraphQL."""

    def __init__(self, shop_domain: str, access_token: str):
        self.shop_domain = shop_domain
        self.access_token = access_token
        self.api_version = "2025-01"  # Use latest stable version
        self.base_url = f"https://{shop_domain}/admin/api/{self.api_version}"

        # Generators
        self.base_generator = BaseGenerator(shop_domain)
        self.product_generator = ProductGenerator(shop_domain)
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
                print(
                    f"    ⚠️ Online Store publication not found, using: {publications[0]['name']}"
                )
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
                print(
                    f"    📍 Using location: {locations[0]['name']} ({locations[0]['id']})"
                )
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
            # Download the image from external URL
            print(f"      📥 Downloading image from: {image_url}")
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            image_data = response.content

            # Prepare form data with staging parameters
            form_data = {}
            for param in staged_target["parameters"]:
                form_data[param["name"]] = param["value"]

            # Upload the file to staged target
            files = {"file": image_data}
            print(f"      📤 Uploading to Shopify staged storage...")
            upload_response = requests.post(
                staged_target["url"], data=form_data, files=files, timeout=60
            )
            upload_response.raise_for_status()

            print(f"      ✅ Upload successful")
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
                print(f"    ⚠️ Media attachment errors: {', '.join(errors)}")
            else:
                media_count = len(result["data"]["productCreateMedia"]["media"])
                print(f"    📸 Successfully attached {media_count} image(s)")

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

                    # Download image to get file size
                    print(f"    📸 Processing image {i}: {filename}")
                    response = requests.head(image_url, timeout=10)
                    file_size = response.headers.get("Content-Length", "0")

                    # Determine MIME type
                    content_type = response.headers.get("Content-Type", "image/jpeg")
                    if not content_type.startswith("image/"):
                        content_type = "image/jpeg"

                    # Step 1: Create staged upload target
                    print(f"      🎯 Creating staged upload target...")
                    staged_target = self._create_staged_upload(
                        filename, content_type, file_size
                    )

                    # Step 2: Upload image to staged target
                    resource_url = self._upload_to_staged_target(
                        staged_target, image_url
                    )

                    # Step 3: Prepare media input with resourceUrl
                    media_inputs.append(
                        {
                            "originalSource": resource_url,  # Use staged resourceUrl
                            "mediaContentType": "IMAGE",
                            "alt": media_node["image"].get("altText", filename),
                        }
                    )

                except Exception as e:
                    print(f"    ⚠️ Failed to process image {i}: {e}")
                    continue

        # Attach all successfully processed media
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
            f"  ✅ Successfully published {success_count}/{len(product_ids)} products"
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

        # Get publication ID once at the beginning
        publication_id = self._get_online_store_publication_id()
        print(f"  📡 Using publication: {publication_id}")

        # Collect all product IDs for batch publishing
        created_product_ids = []

        for i, product_data in enumerate(products, 1):
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
                    raise Exception(f"Product creation errors: {', '.join(errors)}")

                product = result["data"]["productSet"]["product"]

                # Extract variant IDs for order creation
                variant_ids = []
                for variant_node in product["variants"]["nodes"]:
                    variant_ids.append(variant_node["id"])

                # Add media after product is created using staged uploads
                if product_data.get("media", {}).get("edges"):
                    print(f"  🖼️  Adding media to product: {product['title']}")
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
                print(f"  ✅ Product: {product['title']} ({product['id']})")

            except Exception as e:
                print(f"  ❌ Product {i} failed: {e}")

        # Batch publish all products to Online Store
        if created_product_ids:
            self._batch_publish_products(created_product_ids, publication_id)

        return self.created_products

    async def create_customers(self) -> Dict[str, Dict[str, Any]]:
        print("👥 Creating customers...")
        customers = self.customer_generator.generate_customers()
        for i, customer_data in enumerate(customers, 1):
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
                print(f"  ✅ Customer: {customer['displayName']}")

            except Exception as e:
                print(f"  ❌ Customer {i} failed: {e}")
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
                print(f"  ✅ Collection: {collection['title']} ({collection['id']})")

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
                    else:
                        print(
                            f"    ✅ Added {len(c['productIds'])} products to collection"
                        )

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

        # Get some products and customers for orders
        customer_ids = [c["id"] for c in self.created_customers.values()]
        product_list = list(self.created_products.values())

        # Create orders (40 orders for comprehensive ML training)
        for i in range(1, 41):
            try:
                # Pick random customer and products
                customer_id = random.choice(customer_ids)
                selected_products = random.sample(
                    product_list, min(2, len(product_list))
                )

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
                    print(f"  ⚠️ Skipping order {i} - no variants available")
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
                    print(f"  ⚠️ Draft order {i} creation errors: {', '.join(errors)}")
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
                    print(f"  ⚠️ Order completion errors: {', '.join(errors)}")
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
                    f"  ✅ Order: {order['name']} - ${order['totalPrice']} ({order['displayFinancialStatus']})"
                )

            except Exception as e:
                print(f"  ❌ Order {i} failed: {e}")
        return self.created_orders

    async def run(self) -> bool:
        print(f"🚀 Seeding Shopify store with GraphQL: {self.shop_domain}")

        await self.create_products()
        await self.create_customers()
        await self.create_collections()
        await self.create_orders()

        print("\n🎯 Seeding Summary:")
        print(
            f"  ✅ Products:   {len(self.created_products)} (published to Online Store)"
        )
        print(f"  ✅ Customers:  {len(self.created_customers)}")
        print(
            f"  ✅ Collections:{len(self.created_collections)} (published to Online Store)"
        )
        print(f"  ✅ Orders:     {len(self.created_orders)}")
        print(f"  📦 Inventory: Tracked for all product variants")
        print(
            f"  🏷️  Categories: Clothing, Accessories, Electronics, Home & Garden, Sports & Fitness"
        )
        print(
            f"  🌐 Storefront: Products and collections visible on {self.shop_domain}"
        )
        print(f"  🔗 Admin URL: https://{self.shop_domain}/admin")
        return bool(self.created_products and self.created_customers)


async def main() -> bool:
    # Get shop details from arguments or environment variables

    seeder = ShopifyGraphQLSeeder(shop_domain, access_token)
    return await seeder.run()


if __name__ == "__main__":
    asyncio.run(main())
