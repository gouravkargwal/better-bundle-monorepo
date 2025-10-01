from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database.session import get_session_context
from app.core.database.models.collection_data import CollectionData


class CollectionRepository:
    """
    Handles all database operations related to CollectionData.
    """

    def __init__(self, session_factory=None):
        self.session_factory = session_factory or get_session_context

    async def get_by_product_id(
        self, shop_id: str, product_id: str
    ) -> List[Dict[str, Any]]:
        """
        Fetches all collections that a specific product belongs to by querying
        the JSON 'products' column.
        """
        async with self.session_factory() as session:
            # We need to construct a query that can look inside the JSON array.
            # This creates a JSON array containing the product_id string to query for.
            product_id_to_query = [{"id": product_id}]

            # Cast JSON column to JSONB to enable @> containment in Postgres
            stmt = select(CollectionData).where(
                CollectionData.shop_id == shop_id,
                CollectionData.products.cast(JSONB).contains(product_id_to_query),
            )

            result = await session.execute(stmt)
            collections = result.scalars().all()

            return [collection.to_dict() for collection in collections]
