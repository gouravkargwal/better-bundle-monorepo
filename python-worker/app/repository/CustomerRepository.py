from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from app.core.database.session import get_session_context
from app.core.database.models.customer_data import CustomerData
from app.core.logging import get_logger

logger = get_logger(__name__)


class CustomerRepository:
    """
    Handles all database operations related to CustomerData.
    """

    def __init__(self, session_factory=None):
        self.session_factory = session_factory or get_session_context

    async def get_shop_domain_from_id(self, customer_id: str) -> Optional[str]:
        """
        Fetches shop domain for a customer by customer ID.

        Uses eager loading to fetch the related Shop data in a single query.

        Args:
            customer_id: Unique customer identifier from Shopify

        Returns:
            Shop domain string if customer exists, None otherwise
        """
        try:
            async with self.session_factory() as session:
                # Use joinedload for eager loading the relationship
                stmt = (
                    select(CustomerData)
                    .where(CustomerData.customer_id == customer_id)
                    .options(joinedload(CustomerData.shop))
                )

                result = await session.execute(stmt)
                customer = result.unique().scalars().first()

                if not customer or not customer.shop:
                    logger.debug(
                        f"Customer or shop not found for customer_id: {customer_id}"
                    )
                    return None

                shop_domain = customer.shop.shop_domain
                logger.debug(
                    f"Retrieved shop domain: {shop_domain} for customer: {customer_id}"
                )
                return shop_domain

        except Exception as e:
            logger.error(
                f"Error fetching shop domain for customer {customer_id}: {str(e)}"
            )
            raise
