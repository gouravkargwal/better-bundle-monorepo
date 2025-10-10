"""
Purchase Attribution Repository

Repository for PurchaseAttribution table operations.
"""

import logging
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.models import PurchaseAttribution

logger = logging.getLogger(__name__)


class PurchaseAttributionRepository:
    """Repository for PurchaseAttribution operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, attribution_id: str) -> Optional[PurchaseAttribution]:
        """Get purchase attribution by ID."""
        try:
            query = select(PurchaseAttribution).where(
                PurchaseAttribution.id == attribution_id
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting purchase attribution by ID: {e}")
            return None

    async def get_total_revenue_by_shop(self, shop_id: str) -> Decimal:
        """Get total revenue for a shop from all purchase attributions."""
        try:
            query = select(
                func.coalesce(func.sum(PurchaseAttribution.total_revenue), 0)
            ).where(PurchaseAttribution.shop_id == shop_id)

            result = await self.session.execute(query)
            return Decimal(str(result.scalar_one()))
        except Exception as e:
            logger.error(f"Error getting total revenue by shop: {e}")
            return Decimal("0")

    async def get_by_shop(
        self, shop_id: str, limit: int = 100
    ) -> List[PurchaseAttribution]:
        """Get purchase attributions for a shop."""
        try:
            query = (
                select(PurchaseAttribution)
                .where(PurchaseAttribution.shop_id == shop_id)
                .order_by(PurchaseAttribution.purchase_at.desc())
                .limit(limit)
            )

            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting purchase attributions by shop: {e}")
            return []

    async def create(self, attribution: PurchaseAttribution) -> PurchaseAttribution:
        """Create a new purchase attribution."""
        try:
            self.session.add(attribution)
            await self.session.flush()
            return attribution
        except Exception as e:
            logger.error(f"Error creating purchase attribution: {e}")
            raise

    async def save(self, attribution: PurchaseAttribution) -> PurchaseAttribution:
        """Save a purchase attribution (create or update)."""
        try:
            if attribution.id is None:
                self.session.add(attribution)
            await self.session.flush()
            return attribution
        except Exception as e:
            logger.error(f"Error saving purchase attribution: {e}")
            raise

    async def commit(self) -> None:
        """Commit the current transaction."""
        try:
            await self.session.commit()
        except Exception as e:
            logger.error(f"Error committing purchase attribution transaction: {e}")
            raise

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        try:
            await self.session.rollback()
        except Exception as e:
            logger.error(f"Error rolling back purchase attribution transaction: {e}")
            raise
