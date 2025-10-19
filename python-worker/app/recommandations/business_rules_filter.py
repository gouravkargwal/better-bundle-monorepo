"""
Business Rules Filter for FBT Recommendations
Layer 2 of three-layer system (+5-10% quality improvement)

Applies business logic to filter and boost FBT recommendations:
- Price relativity filtering
- Category affinity
- Inventory awareness
- Margin optimization
- Temporal patterns
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio

from app.core.logging import get_logger
from app.core.database.session import get_transaction_context
from app.core.database.models.product_data import ProductData
from app.core.database.models.order_data import OrderData, LineItemData
from sqlalchemy import select, and_, func

logger = get_logger(__name__)


@dataclass
class BusinessRulesConfig:
    """Configuration for business rules filtering"""

    # Price filtering
    price_ratio_min: float = 0.2  # 20% of cart average
    price_ratio_max: float = 1.5  # 150% of cart average

    # Category affinity weights
    category_affinity_boost: float = 1.2  # 20% boost for high affinity
    category_affinity_demote: float = 0.5  # 50% demote for low affinity

    # Inventory thresholds
    min_inventory: int = 1  # Minimum inventory to recommend
    low_inventory_threshold: int = 3  # Demote if inventory < this

    # Margin optimization (if available)
    margin_boost_factor: float = 1.1  # 10% boost for higher margin

    # Temporal patterns
    seasonal_boost: float = 1.3  # 30% boost for seasonal items
    off_season_demote: float = 0.7  # 30% demote for off-season


class BusinessRulesFilter:
    """
    Applies business rules to FBT recommendations

    Filters and boosts recommendations based on:
    - Price relativity to cart
    - Category affinity
    - Inventory levels
    - Margin optimization
    - Seasonal patterns
    """

    def __init__(self, config: BusinessRulesConfig = None):
        self.config = config or BusinessRulesConfig()
        self._category_affinity_cache = {}
        self._inventory_cache = {}
        self._category_affinity_matrix = self._load_category_affinity_matrix()

    async def filter_recommendations(
        self,
        shop_id: str,
        cart_items: List[str],
        cart_value: float,
        recommendations: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Apply business rules filtering to recommendations

        Args:
            shop_id: Shop identifier
            cart_items: List of product IDs in cart
            cart_value: Total cart value
            recommendations: Raw FBT recommendations

        Returns:
            Filtered and boosted recommendations
        """
        if not recommendations:
            return recommendations

        logger.info(
            f"🎯 Applying business rules to {len(recommendations)} recommendations"
        )

        try:
            # Step 1: Price relativity filtering
            price_filtered = await self._apply_price_filter(
                shop_id, cart_items, cart_value, recommendations
            )
            logger.info(
                f"💰 Price filter: {len(price_filtered)}/{len(recommendations)} passed"
            )

            # Step 2: Category affinity boosting
            category_boosted = await self._apply_category_affinity(
                shop_id, cart_items, price_filtered
            )
            logger.info(
                f"🏷️  Category affinity: {len(category_boosted)} recommendations"
            )

            # Step 3: Inventory awareness
            inventory_filtered = await self._apply_inventory_filter(
                shop_id, category_boosted
            )
            logger.info(
                f"📦 Inventory filter: {len(inventory_filtered)}/{len(category_boosted)} passed"
            )

            # Step 4: Margin optimization (if data available)
            margin_optimized = await self._apply_margin_optimization(
                shop_id, inventory_filtered
            )
            logger.info(
                f"💵 Margin optimization: {len(margin_optimized)} recommendations"
            )

            # Step 5: Temporal patterns
            temporal_boosted = await self._apply_temporal_patterns(
                shop_id, margin_optimized
            )
            logger.info(
                f"📅 Temporal patterns: {len(temporal_boosted)} recommendations"
            )

            # Step 6: Final ranking
            final_recommendations = self._final_ranking(temporal_boosted)

            logger.info(
                f"✅ Business rules applied: {len(final_recommendations)} final recommendations"
            )
            return final_recommendations

        except Exception as e:
            logger.error(f"❌ Error applying business rules: {str(e)}")
            return recommendations  # Return original if filtering fails

    async def _apply_price_filter(
        self,
        shop_id: str,
        cart_items: List[str],
        cart_value: float,
        recommendations: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Filter recommendations by price relativity to cart"""
        if not cart_items or cart_value <= 0:
            return recommendations

        # Calculate average cart item price
        avg_cart_price = cart_value / len(cart_items)
        min_price = avg_cart_price * self.config.price_ratio_min
        max_price = avg_cart_price * self.config.price_ratio_max

        filtered = []
        for rec in recommendations:
            try:
                # Get product price
                product_price = await self._get_product_price(shop_id, rec["id"])
                if product_price is None:
                    continue

                # Check price range
                if min_price <= product_price <= max_price:
                    rec["price_filter_passed"] = True
                    rec["price_ratio"] = product_price / avg_cart_price
                    filtered.append(rec)
                else:
                    logger.debug(
                        f"💰 Price filter: {rec['id']} price {product_price} outside range [{min_price:.2f}, {max_price:.2f}]"
                    )

            except Exception as e:
                logger.warning(f"⚠️ Error checking price for {rec['id']}: {str(e)}")
                continue

        return filtered

    async def _apply_category_affinity(
        self, shop_id: str, cart_items: List[str], recommendations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Apply category affinity boosting/demoting"""
        if not cart_items:
            return recommendations

        # Get cart categories
        cart_categories = await self._get_product_categories(shop_id, cart_items)
        if not cart_categories:
            return recommendations

        boosted = []
        for rec in recommendations:
            try:
                # Get recommendation category
                rec_categories = await self._get_product_categories(
                    shop_id, [rec["id"]]
                )
                if not rec_categories:
                    boosted.append(rec)
                    continue

                # Calculate category affinity
                affinity_score = self._calculate_category_affinity(
                    cart_categories, rec_categories
                )

                # Apply boost/demote
                if affinity_score > 0.7:  # High affinity
                    rec["score"] *= self.config.category_affinity_boost
                    rec["category_affinity"] = "high"
                elif affinity_score < 0.3:  # Low affinity
                    rec["score"] *= self.config.category_affinity_demote
                    rec["category_affinity"] = "low"
                else:
                    rec["category_affinity"] = "medium"

                boosted.append(rec)

            except Exception as e:
                logger.warning(
                    f"⚠️ Error checking category affinity for {rec['id']}: {str(e)}"
                )
                boosted.append(rec)

        return boosted

    async def _apply_inventory_filter(
        self, shop_id: str, recommendations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter by inventory levels"""
        filtered = []

        for rec in recommendations:
            try:
                # Get inventory level
                inventory = await self._get_product_inventory(shop_id, rec["id"])
                if inventory is None:
                    continue  # Skip if can't get inventory

                # Hard filter: no inventory
                if inventory < self.config.min_inventory:
                    logger.debug(
                        f"📦 Inventory filter: {rec['id']} has {inventory} inventory (below {self.config.min_inventory})"
                    )
                    continue

                # Soft filter: low inventory (demote)
                if inventory < self.config.low_inventory_threshold:
                    rec["score"] *= 0.8  # 20% demote for low inventory
                    rec["inventory_status"] = "low"
                else:
                    rec["inventory_status"] = "good"

                rec["inventory"] = inventory
                filtered.append(rec)

            except Exception as e:
                logger.warning(f"⚠️ Error checking inventory for {rec['id']}: {str(e)}")
                continue

        return filtered

    async def _apply_margin_optimization(
        self, shop_id: str, recommendations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Apply margin optimization if margin data is available"""
        try:
            optimized = []

            for rec in recommendations:
                product_id = rec["id"]

                # Try to get margin data
                margin = await self._get_product_margin(shop_id, product_id)

                if margin is not None:
                    # Apply margin-based boosting
                    if margin > 0.3:  # High margin (>30%)
                        rec["score"] *= 1.15  # 15% boost
                        rec["margin_boost"] = "high"
                    elif margin > 0.15:  # Medium margin (15-30%)
                        rec["score"] *= 1.05  # 5% boost
                        rec["margin_boost"] = "medium"
                    else:  # Low margin (<15%)
                        rec["score"] *= 0.95  # 5% demote
                        rec["margin_boost"] = "low"

                    rec["margin"] = margin
                else:
                    # No margin data available
                    rec["margin_boost"] = "unknown"
                    rec["margin"] = None

                optimized.append(rec)

            logger.info(
                f"💵 Applied margin optimization to {len(optimized)} recommendations"
            )
            return optimized

        except Exception as e:
            logger.warning(f"⚠️ Error in margin optimization: {str(e)}")
            return recommendations

    async def _get_product_margin(
        self, shop_id: str, product_id: str
    ) -> Optional[float]:
        """Get product margin from database"""
        try:
            async with get_transaction_context() as session:
                # Try to get margin from ProductData (if you have margin columns)
                result = await session.execute(
                    select(ProductData).where(
                        and_(
                            ProductData.shop_id == shop_id,
                            ProductData.product_id == product_id,
                        )
                    )
                )
                product = result.scalar_one_or_none()

                if product:
                    # Method 1: If you have margin columns
                    if hasattr(product, "margin") and product.margin is not None:
                        return float(product.margin)

                    # Method 2: Calculate from price and cost (if you have cost data)
                    if (
                        hasattr(product, "cost")
                        and product.cost is not None
                        and product.price is not None
                    ):
                        cost = float(product.cost)
                        price = float(product.price)
                        if price > 0:
                            return (price - cost) / price

                    # Method 3: Estimate based on category (fallback)
                    category = product.product_type or "Unknown"
                    estimated_margin = self._get_estimated_margin_by_category(category)
                    if estimated_margin is not None:
                        return estimated_margin

                return None

        except Exception as e:
            logger.warning(f"⚠️ Error getting margin for {product_id}: {str(e)}")
            return None

    def _get_estimated_margin_by_category(self, category: str) -> Optional[float]:
        """Estimate margin based on product category"""
        category_margins = {
            "Electronics": 0.25,  # 25% margin
            "Clothing": 0.50,  # 50% margin
            "Accessories": 0.60,  # 60% margin
            "Beauty": 0.40,  # 40% margin
            "Home": 0.35,  # 35% margin
            "Sports": 0.30,  # 30% margin
            "Books": 0.20,  # 20% margin
            "Toys": 0.35,  # 35% margin
            "Garden": 0.40,  # 40% margin
        }

        return category_margins.get(category, 0.30)  # Default 30% margin

    async def _apply_temporal_patterns(
        self, shop_id: str, recommendations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Apply seasonal and temporal patterns"""
        try:
            current_month = datetime.now().month
            current_season = self._get_current_season(current_month)

            boosted = []

            for rec in recommendations:
                product_id = rec["id"]

                # Check if product has seasonal tags
                seasonal_boost = await self._get_seasonal_boost(
                    shop_id, product_id, current_season
                )

                if seasonal_boost > 1.0:
                    rec["score"] *= seasonal_boost
                    rec["seasonal_boost"] = f"{seasonal_boost:.2f}x"
                    rec["seasonal_reason"] = f"Seasonal: {current_season}"
                else:
                    rec["seasonal_boost"] = "1.00x"
                    rec["seasonal_reason"] = "Not seasonal"

                boosted.append(rec)

            logger.info(
                f"📅 Applied seasonal patterns to {len(boosted)} recommendations"
            )
            return boosted

        except Exception as e:
            logger.warning(f"⚠️ Error in seasonal patterns: {str(e)}")
            return recommendations

    def _get_current_season(self, month: int) -> str:
        """Get current season based on month"""
        if month in [12, 1, 2]:
            return "Winter"
        elif month in [3, 4, 5]:
            return "Spring"
        elif month in [6, 7, 8]:
            return "Summer"
        else:  # 9, 10, 11
            return "Fall"

    async def _get_seasonal_boost(
        self, shop_id: str, product_id: str, current_season: str
    ) -> float:
        """Get seasonal boost factor for product"""
        try:
            async with get_transaction_context() as session:
                # Try to get seasonal tags from product
                result = await session.execute(
                    select(ProductData.tags, ProductData.product_type).where(
                        and_(
                            ProductData.shop_id == shop_id,
                            ProductData.product_id == product_id,
                        )
                    )
                )
                row = result.fetchone()

                if row:
                    tags, product_type = row

                    # Check tags for seasonal keywords
                    seasonal_keywords = {
                        "Winter": [
                            "winter",
                            "christmas",
                            "holiday",
                            "cold",
                            "snow",
                            "cozy",
                        ],
                        "Spring": [
                            "spring",
                            "easter",
                            "fresh",
                            "renewal",
                            "garden",
                            "flowers",
                        ],
                        "Summer": [
                            "summer",
                            "beach",
                            "vacation",
                            "hot",
                            "outdoor",
                            "swim",
                        ],
                        "Fall": [
                            "fall",
                            "autumn",
                            "harvest",
                            "back-to-school",
                            "pumpkin",
                            "thanksgiving",
                        ],
                    }

                    # Check if product has seasonal tags
                    if tags:
                        tags_lower = tags.lower()
                        for keyword in seasonal_keywords.get(current_season, []):
                            if keyword in tags_lower:
                                return 1.3  # 30% boost for seasonal products

                    # Check product type for seasonal categories
                    seasonal_categories = {
                        "Winter": ["Clothing", "Accessories", "Home", "Sports"],
                        "Spring": ["Garden", "Clothing", "Home", "Beauty"],
                        "Summer": ["Sports", "Clothing", "Accessories", "Beauty"],
                        "Fall": ["Clothing", "Home", "Garden", "Books"],
                    }

                    if product_type in seasonal_categories.get(current_season, []):
                        return 1.1  # 10% boost for seasonal categories

                return 1.0  # No seasonal boost

        except Exception as e:
            logger.warning(
                f"⚠️ Error checking seasonal boost for {product_id}: {str(e)}"
            )
            return 1.0

    def _final_ranking(
        self, recommendations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Final ranking and limiting of recommendations"""
        # Sort by final score
        sorted_recs = sorted(
            recommendations, key=lambda x: x.get("score", 0), reverse=True
        )

        # Add ranking metadata
        for i, rec in enumerate(sorted_recs):
            rec["rank"] = i + 1
            rec["final_score"] = rec.get("score", 0)

        return sorted_recs

    async def _get_product_price(
        self, shop_id: str, product_id: str
    ) -> Optional[float]:
        """Get product price from database"""
        try:
            async with get_transaction_context() as session:
                result = await session.execute(
                    select(ProductData.price).where(
                        and_(
                            ProductData.shop_id == shop_id,
                            ProductData.product_id == product_id,
                        )
                    )
                )
                price = result.scalar_one_or_none()
                return float(price) if price is not None else None
        except Exception as e:
            logger.warning(f"⚠️ Error getting price for {product_id}: {str(e)}")
            return None

    async def _get_product_categories(
        self, shop_id: str, product_ids: List[str]
    ) -> List[str]:
        """Get product categories from database"""
        try:
            async with get_transaction_context() as session:
                result = await session.execute(
                    select(ProductData.product_type).where(
                        and_(
                            ProductData.shop_id == shop_id,
                            ProductData.product_id.in_(product_ids),
                        )
                    )
                )
                categories = [row[0] for row in result.fetchall() if row[0]]
                return categories
        except Exception as e:
            logger.warning(f"⚠️ Error getting categories: {str(e)}")
            return []

    def _calculate_category_affinity(
        self, cart_categories: List[str], rec_categories: List[str]
    ) -> float:
        """Calculate category affinity score using pre-computed matrix"""
        if not cart_categories or not rec_categories:
            return 0.5  # Neutral if no category data

        # Use pre-computed affinity matrix
        total_affinity = 0.0
        count = 0

        for cart_category in cart_categories:
            for rec_category in rec_categories:
                # Get affinity from matrix
                affinity = self._category_affinity_matrix.get(cart_category, {}).get(
                    rec_category, 0.5
                )
                total_affinity += affinity
                count += 1

        if count == 0:
            return 0.5

        # Return average affinity
        avg_affinity = total_affinity / count

        # Fallback to Jaccard similarity if matrix doesn't have the categories
        if avg_affinity == 0.5:  # Default value, might not be in matrix
            cart_set = set(cart_categories)
            rec_set = set(rec_categories)

            intersection = len(cart_set.intersection(rec_set))
            union = len(cart_set.union(rec_set))

            if union == 0:
                return 0.5

            return intersection / union

        return avg_affinity

    async def _get_product_inventory(
        self, shop_id: str, product_id: str
    ) -> Optional[int]:
        """Get product inventory level from ProductData"""
        try:
            async with get_transaction_context() as session:
                # Get inventory from ProductData table
                result = await session.execute(
                    select(ProductData.inventory_quantity).where(
                        and_(
                            ProductData.shop_id == shop_id,
                            ProductData.product_id == product_id,
                        )
                    )
                )
                inventory = result.scalar_one_or_none()

                # Return actual inventory (if column exists)
                if inventory is not None:
                    return int(inventory)

                # Fallback: Check if product is marked as available
                result = await session.execute(
                    select(ProductData.available).where(
                        and_(
                            ProductData.shop_id == shop_id,
                            ProductData.product_id == product_id,
                        )
                    )
                )
                available = result.scalar_one_or_none()

                # If available=true, assume in stock; else out of stock
                return 10 if available else 0

        except Exception as e:
            logger.warning(f"⚠️ Error getting inventory for {product_id}: {str(e)}")
            # Graceful fallback: assume in stock if can't determine
            return 10

    def _load_category_affinity_matrix(self) -> Dict[str, Dict[str, float]]:
        """Load pre-computed category affinity matrix"""
        return {
            # Clothing & Accessories
            "Clothing": {
                "Accessories": 0.9,
                "Shoes": 0.8,
                "Jewelry": 0.7,
                "Bags": 0.8,
                "Electronics": 0.2,
                "Home": 0.1,
                "Sports": 0.6,
                "Beauty": 0.5,
            },
            "Accessories": {
                "Clothing": 0.9,
                "Jewelry": 0.8,
                "Bags": 0.9,
                "Shoes": 0.7,
                "Electronics": 0.3,
                "Home": 0.2,
                "Sports": 0.5,
                "Beauty": 0.6,
            },
            "Shoes": {
                "Clothing": 0.8,
                "Accessories": 0.7,
                "Sports": 0.9,
                "Bags": 0.6,
                "Electronics": 0.2,
                "Home": 0.1,
                "Beauty": 0.3,
                "Jewelry": 0.4,
            },
            # Electronics
            "Electronics": {
                "Accessories": 0.7,
                "Home": 0.6,
                "Sports": 0.4,
                "Clothing": 0.2,
                "Beauty": 0.3,
                "Books": 0.5,
                "Toys": 0.6,
                "Garden": 0.3,
            },
            "Accessories": {
                "Electronics": 0.7,
                "Home": 0.4,
                "Sports": 0.5,
                "Clothing": 0.9,
                "Beauty": 0.6,
                "Books": 0.3,
                "Toys": 0.4,
                "Garden": 0.2,
            },
            # Home & Garden
            "Home": {
                "Garden": 0.8,
                "Electronics": 0.6,
                "Sports": 0.4,
                "Clothing": 0.1,
                "Beauty": 0.3,
                "Books": 0.4,
                "Toys": 0.5,
                "Accessories": 0.2,
            },
            "Garden": {
                "Home": 0.8,
                "Sports": 0.6,
                "Electronics": 0.3,
                "Clothing": 0.1,
                "Beauty": 0.2,
                "Books": 0.3,
                "Toys": 0.4,
                "Accessories": 0.1,
            },
            # Sports & Fitness
            "Sports": {
                "Clothing": 0.6,
                "Shoes": 0.9,
                "Electronics": 0.4,
                "Home": 0.4,
                "Garden": 0.6,
                "Beauty": 0.3,
                "Books": 0.4,
                "Toys": 0.5,
            },
            # Beauty & Personal Care
            "Beauty": {
                "Clothing": 0.5,
                "Accessories": 0.6,
                "Electronics": 0.3,
                "Home": 0.3,
                "Sports": 0.3,
                "Books": 0.2,
                "Toys": 0.2,
                "Garden": 0.1,
            },
            # Books & Media
            "Books": {
                "Electronics": 0.5,
                "Home": 0.4,
                "Sports": 0.4,
                "Clothing": 0.2,
                "Beauty": 0.2,
                "Toys": 0.6,
                "Garden": 0.3,
                "Accessories": 0.3,
            },
            # Toys & Games
            "Toys": {
                "Books": 0.6,
                "Electronics": 0.6,
                "Sports": 0.5,
                "Home": 0.5,
                "Clothing": 0.3,
                "Beauty": 0.2,
                "Garden": 0.4,
                "Accessories": 0.4,
            },
        }
