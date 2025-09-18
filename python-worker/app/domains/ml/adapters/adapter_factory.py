"""
Factory for creating interaction event adapters
"""

from typing import Dict, Any, Optional

from .base_adapter import BaseInteractionEventAdapter
from .product_viewed_adapter import ProductViewedAdapter
from .cart_add_adapter import CartAddAdapter
from .cart_remove_adapter import CartRemoveAdapter
from .page_viewed_adapter import PageViewedAdapter
from .cart_viewed_adapter import CartViewedAdapter
from .collection_viewed_adapter import CollectionViewedAdapter
from .search_submitted_adapter import SearchSubmittedAdapter
from .checkout_started_adapter import CheckoutStartedAdapter
from .checkout_completed_adapter import CheckoutCompletedAdapter
from .customer_linked_adapter import CustomerLinkedAdapter
from .recommendation_viewed_adapter import RecommendationViewedAdapter
from .recommendation_clicked_adapter import RecommendationClickedAdapter
from .recommendation_add_to_cart_adapter import RecommendationAddToCartAdapter

from app.core.logging import get_logger

logger = get_logger(__name__)


class InteractionEventAdapterFactory:
    """Factory for creating interaction event adapters"""

    def __init__(self):
        self._adapters = {
            # Product interaction events
            "product_viewed": ProductViewedAdapter(),
            "product_added_to_cart": CartAddAdapter(),
            "product_removed_from_cart": CartRemoveAdapter(),
            # Page and navigation events
            "page_viewed": PageViewedAdapter(),
            "cart_viewed": CartViewedAdapter(),
            "collection_viewed": CollectionViewedAdapter(),
            "search_submitted": SearchSubmittedAdapter(),
            # Checkout events
            "checkout_started": CheckoutStartedAdapter(),
            "checkout_completed": CheckoutCompletedAdapter(),
            # Customer events
            "customer_linked": CustomerLinkedAdapter(),
            # Recommendation events
            "recommendation_viewed": RecommendationViewedAdapter(),
            "recommendation_clicked": RecommendationClickedAdapter(),
            "recommendation_add_to_cart": RecommendationAddToCartAdapter(),
        }

    def get_adapter(self, event_type: str) -> Optional[BaseInteractionEventAdapter]:
        """Get adapter for specific event type"""
        return self._adapters.get(event_type)

    def get_all_adapters(self) -> Dict[str, BaseInteractionEventAdapter]:
        """Get all available adapters"""
        return self._adapters.copy()

    def extract_data_from_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from event using appropriate adapter"""
        try:
            event_type = event.get("interactionType", event.get("eventType", ""))
            adapter = self.get_adapter(event_type)

            if not adapter:
                logger.warning(f"No adapter found for event type: {event_type}")
                return {}

            if not adapter.is_valid_event(event):
                logger.warning(f"Event validation failed for type: {event_type}")
                return {}

            return adapter.extract_all_data(event)

        except Exception as e:
            logger.error(f"Error extracting data from event: {str(e)}")
            logger.error(f"Event data: {event}")
            return {}

    def extract_product_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from event using appropriate adapter"""
        try:
            event_type = event.get("interactionType", event.get("eventType", ""))
            adapter = self.get_adapter(event_type)

            if not adapter:
                return None

            return adapter.extract_product_id(event)

        except Exception as e:
            logger.error(f"Error extracting product ID from event: {str(e)}")
            return None

    def extract_customer_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract customer ID from event using appropriate adapter"""
        try:
            event_type = event.get("interactionType", event.get("eventType", ""))
            adapter = self.get_adapter(event_type)

            if not adapter:
                return None

            return adapter.extract_customer_id(event)

        except Exception as e:
            logger.error(f"Error extracting customer ID from event: {str(e)}")
            return None

    def extract_search_query(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract search query from event using appropriate adapter"""
        try:
            event_type = event.get("interactionType", event.get("eventType", ""))

            # Only search events have search queries
            if event_type != "search_submitted":
                return None

            adapter = self.get_adapter(event_type)

            if not adapter:
                return None

            # Extract search query from metadata
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})
            search_query = data.get("query", "")

            return search_query if search_query else None

        except Exception as e:
            logger.error(f"Error extracting search query from event: {str(e)}")
            return None

    def is_product_event(self, event: Dict[str, Any]) -> bool:
        """Check if event is related to a product"""
        event_type = event.get("interactionType", event.get("eventType", ""))
        return event_type in [
            "product_viewed",
            "product_added_to_cart",
            "product_removed_from_cart",
            "recommendation_clicked",
            "recommendation_add_to_cart",
        ]

    def is_cart_event(self, event: Dict[str, Any]) -> bool:
        """Check if event is related to cart operations"""
        event_type = event.get("interactionType", event.get("eventType", ""))
        return event_type in [
            "product_added_to_cart",
            "product_removed_from_cart",
            "cart_viewed",
            "recommendation_add_to_cart",
        ]

    def is_view_event(self, event: Dict[str, Any]) -> bool:
        """Check if event is a view event"""
        event_type = event.get("interactionType", event.get("eventType", ""))
        return event_type in [
            "product_viewed",
            "page_viewed",
            "collection_viewed",
            "recommendation_viewed",
        ]

    def is_purchase_event(self, event: Dict[str, Any]) -> bool:
        """Check if event is a purchase event"""
        event_type = event.get("interactionType", event.get("eventType", ""))
        return event_type in ["checkout_completed"]

    def is_search_event(self, event: Dict[str, Any]) -> bool:
        """Check if event is a search event"""
        event_type = event.get("interactionType", event.get("eventType", ""))
        return event_type in ["search_submitted"]

    def is_recommendation_event(self, event: Dict[str, Any]) -> bool:
        """Check if event is a recommendation event"""
        event_type = event.get("interactionType", event.get("eventType", ""))
        return event_type in [
            "recommendation_viewed",
            "recommendation_clicked",
            "recommendation_add_to_cart",
        ]
