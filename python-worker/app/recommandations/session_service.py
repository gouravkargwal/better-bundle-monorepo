"""
Session Data Service
Handles extraction and processing of session data from behavioral events
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.core.logging import get_logger
from app.core.database.session import get_transaction_context
from app.core.database.models.user_interaction import UserInteraction

logger = get_logger(__name__)


class SessionDataService:
    """Service for extracting and processing session data from behavioral events"""

    async def extract_session_data_from_behavioral_events(
        self, user_id: str, shop_id: str
    ) -> Dict[str, Any]:
        """Extract recent cart and browsing data from behavioral events for session recommendations"""
        try:
            now = datetime.now(timezone.utc)
            cutoff_time = now - timedelta(hours=24)

            async with get_transaction_context() as session:
                # Get recent cart interactions (last 24 hours) - both cart_viewed and individual cart events
                cart_events_result = await session.execute(
                    select(UserInteraction)
                    .where(
                        and_(
                            UserInteraction.customer_id == user_id,
                            UserInteraction.shop_id == shop_id,
                            UserInteraction.interaction_type.in_(
                                [
                                    "cart_viewed",
                                    "product_added_to_cart",
                                    "product_removed_from_cart",
                                ]
                            ),
                            UserInteraction.created_at >= cutoff_time,
                        )
                    )
                    .order_by(desc(UserInteraction.created_at))
                    .limit(20)
                )
                recent_cart_events = cart_events_result.scalars().all()

                # Get recent product_viewed events (last 24 hours)
                view_events_result = await session.execute(
                    select(UserInteraction)
                    .where(
                        and_(
                            UserInteraction.customer_id == user_id,
                            UserInteraction.shop_id == shop_id,
                            UserInteraction.interaction_type == "product_viewed",
                            UserInteraction.created_at >= cutoff_time,
                        )
                    )
                    .order_by(desc(UserInteraction.created_at))
                    .limit(20)
                )
                recent_view_events = view_events_result.scalars().all()

                # Get recent add_to_cart events (last 24 hours)
                add_events_result = await session.execute(
                    select(UserInteraction)
                    .where(
                        and_(
                            UserInteraction.customer_id == user_id,
                            UserInteraction.shop_id == shop_id,
                            UserInteraction.interaction_type == "product_added_to_cart",
                            UserInteraction.created_at >= cutoff_time,
                        )
                    )
                    .order_by(desc(UserInteraction.created_at))
                    .limit(10)
                )
                recent_add_events = add_events_result.scalars().all()

                # Extract cart contents from cart events
                cart_contents = []
                cart_data = None
                for event in recent_cart_events:
                    metadata = event.metadata or {}

                    # Handle cart_viewed events (full cart data)
                    if event.interaction_type == "cart_viewed" and metadata.get(
                        "cart", {}
                    ).get("lines"):
                        cart_data = metadata["cart"]
                        for line in metadata["cart"]["lines"]:
                            if line.get("merchandise", {}).get("product", {}).get("id"):
                                product_id = line["merchandise"]["product"]["id"]
                                if product_id not in cart_contents:
                                    cart_contents.append(product_id)

                    # Handle individual cart events (product_added_to_cart, product_removed_from_cart)
                    elif event.interaction_type in [
                        "product_added_to_cart",
                        "product_removed_from_cart",
                    ]:
                        product_id = self._extract_product_id_from_metadata(metadata)

                        if product_id:
                            if (
                                event.interaction_type == "product_added_to_cart"
                                and product_id not in cart_contents
                            ):
                                cart_contents.append(product_id)
                            elif (
                                event.interactionType == "product_removed_from_cart"
                                and product_id in cart_contents
                            ):
                                cart_contents.remove(product_id)

            # Extract recent views
            recent_views = []
            product_types = set()
            for event in recent_view_events:
                metadata = event.metadata or {}
                product_id = self._extract_product_id_from_metadata(metadata)

                if product_id and product_id not in recent_views:
                    recent_views.append(product_id)

                # Extract product type
                product_type = metadata.get("product_type")
                if product_type:
                    product_types.add(product_type)

            # Extract recent adds to cart
            recent_adds = []
            for event in recent_add_events:
                metadata = event.metadata or {}
                product_id = self._extract_product_id_from_metadata(metadata)

                if product_id and product_id not in recent_adds:
                    recent_adds.append(product_id)

            # Build session metadata
            session_metadata = {
                "cart_contents": cart_contents,
                "recent_views": recent_views,
                "recent_adds": recent_adds,
                "product_types": list(product_types),
                "cart_data": cart_data,  # Full cart data for detailed analysis
                "session_context": {
                    "total_cart_items": len(cart_contents),
                    "total_views": len(recent_views),
                    "total_adds": len(recent_adds),
                    "categories": list(product_types),
                    "last_activity": (
                        recent_cart_events[0].createdAt.isoformat()
                        if recent_cart_events
                        else None
                    ),
                },
            }

            return session_metadata

        except Exception as e:
            logger.error(
                f"💥 Failed to extract session data from behavioral events: {str(e)}"
            )
            return {
                "cart_contents": [],
                "recent_views": [],
                "recent_adds": [],
                "product_types": [],
                "cart_data": None,
                "session_context": {},
            }

    def _extract_product_id_from_metadata(
        self, metadata: Dict[str, Any]
    ) -> Optional[str]:
        """Extract product ID from various metadata structures"""
        product_id = None

        # Try different metadata structures for product ID
        if "product_id" in metadata:
            product_id = metadata.get("product_id")
        elif "data" in metadata and "cartLine" in metadata["data"]:
            cart_line = metadata["data"]["cartLine"]
            if "merchandise" in cart_line and "product" in cart_line["merchandise"]:
                product_id = cart_line["merchandise"]["product"].get("id")
        elif "productId" in metadata:
            product_id = metadata.get("productId")

        return product_id

    def extract_session_id_from_cart_data(
        self, cart_data: Dict[str, Any]
    ) -> Optional[str]:
        """Extract session ID from cart attributes"""
        try:
            if not cart_data:
                return None

            attributes = cart_data.get("attributes", [])
            if isinstance(attributes, list):
                for attr in attributes:
                    if (
                        isinstance(attr, dict)
                        and attr.get("key") == "bb_recommendation_session_id"
                        and attr.get("value")
                    ):
                        return attr["value"]
            return None
        except Exception:
            return None

    def get_effective_category_for_mixed_cart(
        self, original_category: Optional[str], product_types: List[str]
    ) -> Optional[str]:
        """
        Determine effective category when cart spans multiple categories.
        Avoid over-filtering by returning None for mixed categories.
        """
        try:
            if not product_types:
                return original_category

            unique_types = {t for t in product_types if t}
            if len(unique_types) > 1:
                # Mixed categories: avoid over-filtering
                return None
            return original_category
        except Exception:
            # Non-fatal: fallback to original category
            return original_category
