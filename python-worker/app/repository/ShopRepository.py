from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database.models import Shop
from app.core.database.session import get_session_context


class ShopRepository:
    def __init__(self, session_factory=None):
        """
        Initializes the repository with a session factory.
        Repository handles its own session management.
        """
        self.session_factory = session_factory or get_session_context

    async def get_active_by_id(self, shop_id: str) -> Optional[Shop]:
        """
        Fetches a single active shop by its primary key (ID).
        Repository handles its own session management.

        Args:
            shop_id: The string ID of the shop to retrieve.

        Returns:
            A SQLAlchemy 'Shop' model instance if found and active, otherwise None.
        """
        async with self.session_factory() as session:
            # Construct the select statement
            statement = select(Shop).where(
                (Shop.id == shop_id) & (Shop.is_active == True)
            )

            # Execute the query
            result = await session.execute(statement)

            # Return a single result or None
            return result.scalar_one_or_none()
