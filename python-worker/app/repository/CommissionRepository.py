"""
Commission Repository

Repository for CommissionRecord table operations.
"""

import logging
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.models import CommissionRecord

logger = logging.getLogger(__name__)


class CommissionRepository:
    """Repository for CommissionRecord operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, commission_id: str) -> Optional[CommissionRecord]:
        """Get commission record by ID."""
        query = select(CommissionRecord).where(CommissionRecord.id == commission_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_purchase_attribution_id(
        self, purchase_attribution_id: str
    ) -> Optional[CommissionRecord]:
        """Get commission record by purchase attribution ID."""
        query = select(CommissionRecord).where(
            CommissionRecord.purchase_attribution_id == purchase_attribution_id
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_shop(
        self, shop_id: str, limit: int = 100
    ) -> List[CommissionRecord]:
        """Get commission records for a shop."""
        query = (
            select(CommissionRecord)
            .where(CommissionRecord.shop_id == shop_id)
            .order_by(CommissionRecord.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create(self, commission: CommissionRecord) -> CommissionRecord:
        """Create a new commission record."""
        self.session.add(commission)
        await self.session.flush()
        return commission

    async def update(self, commission: CommissionRecord) -> CommissionRecord:
        """Update an existing commission record."""
        await self.session.flush()
        return commission

    async def save(self, commission: CommissionRecord) -> CommissionRecord:
        """Save a commission record (create or update)."""
        if commission.id is None:
            self.session.add(commission)
        await self.session.flush()
        return commission

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self.session.commit()

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        await self.session.rollback()

    async def get_all(self, limit: int = 1000) -> List[CommissionRecord]:
        """Get all commission records."""
        query = (
            select(CommissionRecord)
            .order_by(CommissionRecord.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
