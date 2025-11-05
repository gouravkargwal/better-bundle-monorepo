from typing import Optional
from sqlalchemy import select
from app.core.database.models import Shop
from app.core.database.session import get_session_context
from sqlalchemy import and_
from app.core.database.models.shop_subscription import ShopSubscription
from app.core.database.models.enums import SubscriptionStatus


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

    async def get_active_by_domain(self, shop_domain: str) -> Optional[Shop]:
        """
        Fetches a single active shop by its domain.
        Repository handles its own session management.

        Args:
            shop_domain: The domain of the shop to retrieve.

        Returns:
            A SQLAlchemy 'Shop' model instance if found and active, otherwise None.
        """
        async with self.session_factory() as session:
            # Construct the select statement
            statement = select(Shop).where(
                (Shop.shop_domain == shop_domain) & (Shop.is_active == True)
            )

            # Execute the query
            result = await session.execute(statement)

            # Return a single result or None
            return result.scalar_one_or_none()

    async def is_shop_active(self, shop_id: str) -> bool:
        """
        Check if a shop is active.
        """
        async with self.session_factory() as session:
            statement = select(Shop.is_active).where(Shop.id == shop_id)
            result = await session.execute(statement)
            return result.scalar_one_or_none() is not None

    async def get_shop_by_id(self, shop_id: str):
        """
        Fetches shop info by shop ID (for token refresh flow).
        Raises NoResultFound if shop not found (bubbles up automatically).
        """
        async with self.session_factory() as session:
            # Query shop
            shop_statement = select(Shop).where(
                and_(Shop.id == shop_id, Shop.is_active == True)
            )
            shop_result = await session.execute(shop_statement)
            shop = shop_result.scalar_one()

            # Query active subscription separately (more efficient)
            subscription_statement = (
                select(ShopSubscription.status)
                .where(
                    and_(
                        ShopSubscription.shop_id == shop.id,
                        ShopSubscription.is_active == True,
                    )
                )
                .order_by(ShopSubscription.created_at.desc())  # Get most recent
                .limit(1)
            )
            subscription_result = await session.execute(subscription_statement)
            subscription_row = subscription_result.first()

            # Determine if service is active (simple boolean)
            # Service is active ONLY if subscription status is ACTIVE
            # All other statuses (TRIAL, SUSPENDED, CANCELLED, etc.) = inactive
            is_service_active = False  # Default to inactive
            if subscription_row:
                sub_status = subscription_row[0]
                # Only ACTIVE status means service is active
                if (
                    sub_status == SubscriptionStatus.ACTIVE
                    or sub_status == SubscriptionStatus.TRIAL
                ):
                    is_service_active = True

            return {
                "shop_id": shop.id,
                "shop_domain": shop.shop_domain,
                "is_service_active": is_service_active,
                "shopify_plus": shop.shopify_plus,
            }

    async def get_shop_info_from_domain(self, shop_domain: str):
        """
        Fetches a single shop by its domain.
        Raises NoResultFound if shop not found (bubbles up automatically).
        """
        async with self.session_factory() as session:
            # Query shop
            shop_statement = select(Shop).where(
                and_(Shop.shop_domain == shop_domain, Shop.is_active == True)
            )
            shop_result = await session.execute(shop_statement)
            shop = shop_result.scalar_one()

            # Query active subscription separately (more efficient)
            subscription_statement = (
                select(ShopSubscription.status)
                .where(
                    and_(
                        ShopSubscription.shop_id == shop.id,
                        ShopSubscription.is_active == True,
                    )
                )
                .order_by(ShopSubscription.created_at.desc())  # Get most recent
                .limit(1)
            )
            subscription_result = await session.execute(subscription_statement)
            subscription_row = subscription_result.first()

            # Determine if service is active (simple boolean)
            # Service is active ONLY if subscription status is ACTIVE
            # All other statuses (TRIAL, SUSPENDED, CANCELLED, etc.) = inactive
            is_service_active = False  # Default to inactive
            if subscription_row:
                sub_status = subscription_row[0]
                # Only ACTIVE status means service is active
                if (
                    sub_status == SubscriptionStatus.ACTIVE
                    or sub_status == SubscriptionStatus.TRIAL
                ):
                    is_service_active = True

            return {
                "shop_id": shop.id,
                "shop_domain": shop.shop_domain,
                "is_service_active": is_service_active,
                "shopify_plus": shop.shopify_plus,
            }
