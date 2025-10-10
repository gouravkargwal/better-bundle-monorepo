from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database.session import get_session_context
from app.core.database.models.order_data import OrderData, LineItemData


class OrderRepository:
    """
    Handles all database operations related to OrderData, including its line items.
    """

    def __init__(self, session_factory=None):
        self.session_factory = session_factory or get_session_context

    async def get_by_product_id(
        self, shop_id: str, product_id: str
    ) -> List[Dict[str, Any]]:
        """
        Fetches all orders that contain a specific product by joining
        with the order_line_items table.
        """
        async with self.session_factory() as session:
            stmt = (
                select(OrderData)
                .join(LineItemData, OrderData.id == LineItemData.order_id)
                .where(
                    OrderData.shop_id == shop_id, LineItemData.product_id == product_id
                )
                # Eagerly load line_items via the root entity's relationship
                .options(selectinload(OrderData.line_items))
            )
            result = await session.execute(stmt)

            # .unique() is important to avoid duplicate orders if a product appears multiple times
            orders = result.scalars().unique().all()

            return [order.to_dict() for order in orders]
