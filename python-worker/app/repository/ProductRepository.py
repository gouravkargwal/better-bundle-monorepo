from typing import Dict, Any, Optional
from sqlalchemy import select
from app.core.database.session import get_session_context
from app.core.database.models.product_data import ProductData


class ProductRepository:
    """
    Handles all database operations related to ProductData.
    """

    def __init__(self, session_factory=None):
        self.session_factory = session_factory or get_session_context

    async def get_by_id(
        self, shop_id: str, product_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches a single product by its ID for a given shop.
        """
        async with self.session_factory() as session:
            stmt = select(ProductData).where(
                ProductData.shop_id == shop_id, ProductData.product_id == product_id
            )
            result = await session.execute(stmt)
            product = result.scalars().first()
            return product.to_dict() if product else None
