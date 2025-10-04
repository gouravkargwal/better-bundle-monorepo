from typing import Dict, Any, List

from app.core.logging import get_logger
from app.core.database.session import get_transaction_context
from app.core.database.models.shop import Shop
from app.core.database.models.product_data import ProductData
from sqlalchemy import select, and_


logger = get_logger(__name__)


class ProductEnrichment:
    """Service to enrich Gorse item IDs with Shopify product data"""

    def __init__(self):
        pass

    def enhance_recommendations_with_currency(
        self, recommendations: List[Dict[str, Any]], shop_currency: str
    ) -> List[Dict[str, Any]]:
        """
        Centralized function to enhance all recommendations with consistent currency information

        Args:
            recommendations: List of recommendation dictionaries
            shop_currency: Shop's currency code (e.g., "USD", "INR")

        Returns:
            Enhanced recommendations with consistent currency
        """
        enhanced_recommendations = []

        for rec in recommendations:
            # Create a copy to avoid modifying the original
            enhanced_rec = rec.copy()

            # Ensure price has currency_code
            if "price" in enhanced_rec and isinstance(enhanced_rec["price"], dict):
                enhanced_rec["price"]["currency_code"] = shop_currency
            else:
                # If price is not a dict, create proper structure
                enhanced_rec["price"] = {
                    "amount": str(enhanced_rec.get("price", "0")),
                    "currency_code": shop_currency,
                }

            # Enhance variants with currency information
            if "variants" in enhanced_rec and isinstance(
                enhanced_rec["variants"], list
            ):
                enhanced_variants = []
                for variant in enhanced_rec["variants"]:
                    if isinstance(variant, dict):
                        enhanced_variant = variant.copy()
                        enhanced_variant["currency_code"] = shop_currency
                        enhanced_variants.append(enhanced_variant)
                    else:
                        enhanced_variants.append(variant)
                enhanced_rec["variants"] = enhanced_variants

            enhanced_recommendations.append(enhanced_rec)

        return enhanced_recommendations

    def _extract_image_from_media(
        self, media_data: Any, fallback_title: str
    ) -> Dict[str, str] | None:
        """Extract image URL and alt text from media JSON data"""
        if not media_data or not isinstance(media_data, list) or len(media_data) == 0:
            return None

        # Get the first media item (usually the main product image)
        first_media = media_data[0]

        # Handle different media structures
        if isinstance(first_media, dict):
            # Check for direct image properties
            if "image" in first_media and isinstance(first_media["image"], dict):
                image_data = first_media["image"]
                return {
                    "url": image_data.get("url", ""),
                    "alt_text": image_data.get("altText", fallback_title),
                }
            # Check for direct URL properties
            elif "url" in first_media:
                return {
                    "url": first_media.get("url", ""),
                    "alt_text": first_media.get("altText", fallback_title),
                }

        return None

    async def enrich_items(
        self,
        shop_id: str,
        item_ids: List[str],
        context: str = "product_page",
        source: str = "unknown",
    ) -> List[Dict[str, Any]]:
        """
        Enrich Gorse item IDs with Shopify product data

        Args:
            shop_id: Shop ID
            item_ids: List of Gorse item IDs (which are Shopify product IDs)
            context: Recommendation context
            source: Recommendation source

        Returns:
            List of enriched product data
        """
        try:
            logger.debug(
                f"🎨 Starting enrichment | shop_id={shop_id} | item_count={len(item_ids)} | context={context} | source={source}"
            )

            async with get_transaction_context() as session:
                # Get shop details to determine the correct domain for product URLs and currency
                shop_result = await session.execute(
                    select(Shop).where(Shop.id == shop_id)
                )
                shop = shop_result.scalar_one_or_none()

                # Use custom domain if available, otherwise fall back to myshopify domain
                product_domain = (
                    shop.custom_domain
                    if shop and shop.custom_domain
                    else (shop.shop_domain if shop else None)
                )

            # Strip prefixes from Gorse item IDs to match database format
            # Gorse uses: shop_cmff7mzru0000v39c3jkk4anm_7903465537675
            # Database uses: 7903465537675
            # Only include items from the current shop for multi-tenancy
            clean_item_ids = []
            for item_id in item_ids:
                # Handle both string item IDs and dictionary items
                if isinstance(item_id, dict):
                    # Extract the actual item ID from the dictionary
                    actual_item_id = item_id.get("Id", item_id.get("id", str(item_id)))
                else:
                    actual_item_id = item_id

                # Skip empty or invalid item IDs
                if not actual_item_id or actual_item_id.strip() == "":
                    logger.debug(f"🚫 Skipping empty item ID: {item_id}")
                    continue

                if actual_item_id.startswith("shop_"):
                    # Extract shop ID and product ID
                    parts = actual_item_id.split("_")
                    if len(parts) >= 3:
                        gorse_shop_id = parts[
                            1
                        ]  # shop_cmff7mzru0000v39c3jkk4anm_7903465537675
                        product_id = parts[2]  # 7903465537675

                        # Only include if it's from the current shop and product_id is not empty
                        if (
                            gorse_shop_id == shop_id
                            and product_id
                            and product_id.strip()
                        ):
                            clean_item_ids.append(product_id)
                        else:
                            logger.debug(
                                f"🚫 Skipping product from different shop or empty product_id | gorse_shop={gorse_shop_id} | current_shop={shop_id} | product={product_id}"
                            )
                    else:
                        logger.warning(
                            f"⚠️ Invalid Gorse item ID format: {actual_item_id}"
                        )
                else:
                    # Assume it's already a clean product ID, but check it's not empty
                    if actual_item_id.strip():
                        clean_item_ids.append(actual_item_id)
                    else:
                        logger.debug(
                            f"🚫 Skipping empty clean product ID: {actual_item_id}"
                        )

            # Fetch products from database using cleaned IDs
            products_result = await session.execute(
                select(ProductData).where(
                    and_(
                        ProductData.shop_id == shop_id,
                        ProductData.product_id.in_(clean_item_ids),
                    )
                )
            )
            products = products_result.scalars().all()

            logger.debug(
                f"📊 Database query complete | found_products={len(products)} | requested={len(clean_item_ids)}"
            )

            # Create a mapping for quick lookup using cleaned IDs
            product_map = {p.product_id: p for p in products}

            # Enrich items in the same order as requested
            enriched_items = []
            missing_items = []
            for item_id in item_ids:
                # Handle both string item IDs and dictionary items
                if isinstance(item_id, dict):
                    # Extract the actual item ID from the dictionary
                    actual_item_id = item_id.get("Id", item_id.get("id", str(item_id)))
                else:
                    actual_item_id = item_id

                # Find the corresponding clean_id for this item_id
                clean_id = None
                if actual_item_id.startswith("shop_"):
                    parts = actual_item_id.split("_")
                    if len(parts) >= 3:
                        gorse_shop_id = parts[1]
                        product_id = parts[2]
                        if gorse_shop_id == shop_id:
                            clean_id = product_id
                else:
                    clean_id = actual_item_id

                if clean_id and clean_id in product_map:
                    product = product_map[clean_id]
                    # Extract variant information for cart permalinks
                    variants = product.variants if product.variants else []
                    default_variant = None
                    variant_id = None
                    selected_variant_id = None

                    logger.debug(
                        f"🔍 Product {product.product_id} variants: {variants}"
                    )
                    logger.debug(
                        f"🔍 Product {product.product_id} options: {product.options}"
                    )
                    logger.debug(
                        f"🔍 Product {product.product_id} inventory: {product.total_inventory}"
                    )

                    if variants and len(variants) > 0:
                        # Get the first variant (usually the default)
                        default_variant = (
                            variants[0] if isinstance(variants, list) else None
                        )
                        if default_variant and isinstance(default_variant, dict):
                            # Extract variant ID - handle both GraphQL format and numeric format
                            # Try different possible keys for variant ID
                            raw_variant_id = (
                                default_variant.get("variant_id")
                                or default_variant.get("id")
                                or default_variant.get("variantId", "")
                            )
                            if raw_variant_id:
                                # If it's a GraphQL ID, extract the numeric part
                                if "/" in str(raw_variant_id):
                                    variant_id = str(raw_variant_id).split("/")[-1]
                                else:
                                    variant_id = str(raw_variant_id)
                                selected_variant_id = variant_id
                                logger.debug(
                                    f"✅ Extracted variant_id: {variant_id} from {raw_variant_id}"
                                )
                            else:
                                logger.warning(
                                    f"⚠️ No variant ID found in variant: {default_variant}"
                                )

                    # Determine availability based on overall and per-variant inventory
                    total_inventory = getattr(product, "total_inventory", None)
                    any_variant_instock = False
                    if isinstance(variants, list) and len(variants) > 0:
                        for v in variants:
                            try:
                                inv = (
                                    v.get("inventory") if isinstance(v, dict) else None
                                )
                                if isinstance(inv, int) and inv > 0:
                                    any_variant_instock = True
                                    break
                            except Exception:
                                pass
                    is_available = (product.status == "ACTIVE") and (
                        (isinstance(total_inventory, int) and total_inventory > 0)
                        or any_variant_instock
                    )

                    # Skip products that are unavailable (sold out or inactive)
                    if not is_available:
                        continue

                    # Format for frontend ProductRecommendation interface
                    enriched_items.append(
                        {
                            "id": product.product_id,
                            "title": product.title,
                            "handle": product.handle,
                            "url": f"https://{product_domain}/products/{product.handle}",
                            "price": {
                                "amount": str(product.price),
                            },
                            "image": self._extract_image_from_media(
                                product.media, product.title
                            ),
                            "vendor": product.vendor or "",
                            "product_type": product.product_type or "",
                            "available": is_available,
                            "score": 0.8,  # Default recommendation score
                            "variant_id": variant_id,
                            "selectedVariantId": selected_variant_id,
                            "variants": variants,  # Include all variants for flexibility
                            "options": product.options
                            or [],  # Product options for variant selection
                            "inventory": product.total_inventory
                            or 0,  # Total inventory count
                        }
                    )
                else:
                    # Item not found in database, skip it
                    if clean_id:
                        missing_items.append(clean_id)

            if missing_items:
                logger.warning(
                    f"⚠️ Missing products in database | shop_id={shop_id} | missing_count={len(missing_items)} | missing_ids={missing_items[:5]}{'...' if len(missing_items) > 5 else ''}"
                )

            return enriched_items

        except Exception as e:
            logger.error(f"💥 Failed to enrich items: {str(e)}")
            return []

    def _get_recommendation_reason(self, context: str, source: str) -> str:
        """Get contextual recommendation reason based on context and source"""

        # More specific reasons based on ML source
        if "item_neighbors" in source:
            return "Similar products"
        elif "user_recommendations" in source:
            return "Recommended for you"
        elif "session_recommendations" in source:
            return "Based on your browsing"
        elif "popular" in source:
            return "Popular choice"
        elif "latest" in source:
            return "New arrival"
        elif "fallback" in source:
            return "Trending now"
        else:
            # Context-based fallback reasons
            context_reasons = {
                "product_page": "Customers also bought",
                "homepage": "Featured product",
                "cart": "Perfect addition",
                "profile": "Just for you",
                "checkout": "Don't miss out",
            }
            return context_reasons.get(context, "Recommended for you")
