"""
Commission Service V2

[READ-ONLY] Service for accessing historical commission records.

With flat fee pricing, commissions are no longer created for individual purchases.
This service is kept for READ-ONLY access to historical commission data from
the legacy usage-based billing system.
"""

import logging
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.models import (
    CommissionRecord,
)
from app.core.database.models.enums import (
    BillingPhase,
    CommissionStatus,
)
from ..repositories.billing_repository_v2 import BillingRepositoryV2
from app.repository.CommissionRepository import CommissionRepository
from app.repository.PurchaseAttributionRepository import PurchaseAttributionRepository

logger = logging.getLogger(__name__)


class CommissionServiceV2:
    """
    [READ-ONLY] Service for accessing historical commission records.

    With flat fee pricing, commissions are no longer created for individual purchases.
    This service is kept for READ-ONLY access to historical commission data from
    the legacy usage-based billing system.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.billing_repository = BillingRepositoryV2(session)
        self.commission_repository = CommissionRepository(session)
        self.purchase_attribution_repository = PurchaseAttributionRepository(session)

    # ============= READ-ONLY METHODS =============

    async def get_commissions_by_shop(
        self,
        shop_id: str,
        billing_phase: Optional[BillingPhase] = None,
        status: Optional[CommissionStatus] = None,
        limit: int = 100,
    ) -> List[CommissionRecord]:
        """Get commission records for a shop (read-only)"""
        try:
            commissions = await self.commission_repository.get_by_shop(shop_id, limit)
            if billing_phase:
                commissions = [
                    c for c in commissions if c.billing_phase == billing_phase
                ]
            if status:
                commissions = [c for c in commissions if c.status == status]
            return commissions
        except Exception as e:
            logger.error(f"Error getting commissions: {e}")
            return []

    async def get_commission_stats_for_cycle(
        self, billing_cycle_id: str
    ) -> Dict[str, Any]:
        """Get commission statistics for a billing cycle (read-only)"""
        try:
            query = select(
                func.count(CommissionRecord.id).label("count"),
                func.coalesce(func.sum(CommissionRecord.commission_earned), 0).label(
                    "total_earned"
                ),
                func.coalesce(func.sum(CommissionRecord.commission_charged), 0).label(
                    "total_charged"
                ),
                func.coalesce(func.sum(CommissionRecord.commission_overflow), 0).label(
                    "total_overflow"
                ),
            ).where(CommissionRecord.billing_cycle_id == billing_cycle_id)

            result = await self.session.execute(query)
            stats = result.one()

            return {
                "count": stats.count,
                "total_earned": float(stats.total_earned),
                "total_charged": float(stats.total_charged),
                "total_overflow": float(stats.total_overflow),
                "charge_rate": (
                    float(stats.total_charged / stats.total_earned * 100)
                    if stats.total_earned > 0
                    else 0
                ),
            }
        except Exception as e:
            logger.error(f"Error getting commission stats: {e}")
            return {
                "count": 0,
                "total_earned": 0,
                "total_charged": 0,
                "total_overflow": 0,
                "charge_rate": 0,
            }

    # ============= DEPRECATED METHODS (LOG WARNINGS) =============

    async def create_commission_record(
        self, purchase_attribution_id: str, shop_id: str
    ) -> Optional[CommissionRecord]:
        """
        [DEPRECATED] Create commission record for a purchase attribution.

        With flat fee pricing, this method should NOT be called.
        It logs a warning and returns None.
        """
        logger.warning(
            f"[DEPRECATED] create_commission_record called - flat fee pricing "
            f"does not use commissions. Skipping for attribution {purchase_attribution_id}."
        )
        return None

    async def get_pending_commissions(self, limit: int = 100) -> List[CommissionRecord]:
        """[DEPRECATED] Get pending commissions - flat fee pricing has no commissions"""
        logger.warning(
            "[DEPRECATED] get_pending_commissions called - flat fee pricing has no commissions"
        )
        return []

    async def record_commission_to_shopify(
        self, commission_id: str, shopify_billing_service=None
    ) -> Dict[str, Any]:
        """[DEPRECATED] Record commission to Shopify - not used in flat fee pricing"""
        logger.warning(
            f"[DEPRECATED] record_commission_to_shopify called for commission {commission_id}"
        )
        return {"success": False, "error": "deprecated_flat_fee_pricing"}
