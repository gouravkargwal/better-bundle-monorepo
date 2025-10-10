"""
Shop Lookup Service
Handles shop domain lookup and validation logic
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.logging import get_logger
from app.core.database.session import get_transaction_context
from app.core.database.models.shop import Shop
from app.core.database.models.customer_data import CustomerData

logger = get_logger(__name__)


class ShopLookupService:
    """Service for handling shop domain lookup and validation"""

    async def get_shop_domain_from_customer_id(self, customer_id: str) -> Optional[str]:
        """
        Get shop domain from customer ID using SQLAlchemy
        """
        try:
            async with get_transaction_context() as session:
                # First, find the customer by customer_id
                result = await session.execute(
                    select(CustomerData).where(CustomerData.customer_id == customer_id)
                )
                customer = result.scalar_one_or_none()

                if not customer:
                    logger.warning(
                        f"⚠️ Customer not found with customer_id: {customer_id}"
                    )
                    return None

                # Get the shop_id from the customer
                shop_id = customer.shop_id
                if not shop_id:
                    logger.warning(f"⚠️ No shop_id found for customer {customer_id}")
                    return None

                # Now find the shop by shop_id to get shop_domain
                shop_result = await session.execute(
                    select(Shop).where(Shop.id == shop_id)
                )
                shop = shop_result.scalar_one_or_none()

                if shop and shop.shop_domain:
                    shop_domain = shop.shop_domain
                    return shop_domain
                else:
                    logger.warning(f"⚠️ No shop_domain found for shop {shop_id}")
                    return None

        except Exception as e:
            logger.error(
                f"❌ Error looking up shop_domain for customer {customer_id}: {e}"
            )
            return None

    async def validate_shop_exists(self, shop_domain: str) -> Optional[Shop]:
        """
        Validate that a shop exists and return the shop object
        """
        try:
            async with get_transaction_context() as session:
                result = await session.execute(
                    select(Shop).where(Shop.shop_domain == shop_domain)
                )
                shop = result.scalar_one_or_none()
                return shop
        except Exception as e:
            logger.error(f"❌ Error validating shop {shop_domain}: {e}")
            return None
