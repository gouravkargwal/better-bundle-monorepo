from typing import List, Dict, Any
from app.core.database.session import get_session_context
from app.core.database.models.user_interaction import UserInteraction
from sqlalchemy import select


class UserInteractionRepository:
    """
    Handles all database operations related to user interaction events.
    """

    def __init__(self, session_factory=None):
        self.session_factory = session_factory or get_session_context

    async def get_by_product_id(
        self, shop_id: str, product_id: str
    ) -> List[Dict[str, Any]]:
        """
        Fetches all behavioral events related to a specific product.
        """
        async with self.session_factory() as session:
            stmt = select(UserInteraction).where(
                UserInteraction.shop_id == shop_id,
                UserInteraction.interaction_metadata["productId"].astext == product_id,
            )
            result = await session.execute(stmt)
            user_interactions = result.scalars().all()
            return [
                user_interaction.to_dict() for user_interaction in user_interactions
            ]
