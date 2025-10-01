from typing import Dict, Any, List
from app.repository.CollectionRepository import CollectionRepository
from app.repository.OrderRepository import OrderRepository
from app.repository.ProductRepository import ProductRepository
from app.repository.UserInteractionRepository import UserInteractionRepository
from app.core.logging import get_logger


logger = get_logger(__name__)


class DataFetcher:
    """
    Responsible for fetching all the necessary raw data from various sources
    to compute product features.
    """

    def __init__(self, shop_id: str):
        self.shop_id = shop_id
        self.product_repo = ProductRepository()
        self.order_repo = OrderRepository()
        self.user_interaction_repo = UserInteractionRepository()
        self.collection_repo = CollectionRepository()

    async def fetch_data_for_product(self, product_id: str) -> Dict[str, Any]:
        """
        Fetches and aggregates all data for a single product.
        This is the main public method of the class.
        """
        product_data = await self._fetch_product_data(product_id)
        orders = await self._fetch_orders_for_product(product_id)
        user_interactions = await self._fetch_user_interactions_for_product(product_id)
        collections = await self._fetch_collections_for_product(product_id)

        return {
            "product_data": product_data,
            "orders": orders,
            "user_interactions": user_interactions,
            "collections": collections,
        }

    async def _fetch_product_data(self, product_id: str) -> Dict[str, Any]:
        """Fetches the core data for a single product."""
        product = await self.product_repo.get_by_id(self.shop_id, product_id)
        return product

    async def _fetch_orders_for_product(self, product_id: str) -> List[Dict[str, Any]]:
        """Fetches all orders containing the specified product."""
        orders = await self.order_repo.get_by_product_id(self.shop_id, product_id)
        return orders

    async def _fetch_user_interactions_for_product(
        self, product_id: str
    ) -> List[Dict[str, Any]]:
        """Fetches all behavioral events related to the product."""
        user_interactions = await self.user_interaction_repo.get_by_product_id(
            self.shop_id, product_id
        )
        return user_interactions

    async def _fetch_collections_for_product(
        self, product_id: str
    ) -> List[Dict[str, Any]]:
        """Fetches the collections that the product belongs to."""
        collections = await self.collection_repo.get_by_product_id(
            self.shop_id, product_id
        )
        return collections
