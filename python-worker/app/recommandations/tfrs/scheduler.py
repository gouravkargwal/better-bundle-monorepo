"""
Training scheduler for TFRS models.

Triggers per-shop model training on a schedule.
Can be called:
1. On-demand via admin API endpoint
2. On a schedule via cron/APScheduler
3. After data sync completes
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from .trainer import TfrsTrainer
from .config import TfrsConfig
from .serving import TfrsServing

logger = logging.getLogger(__name__)


class TfrsScheduler:
    """Schedules and manages TFRS model training."""

    def __init__(self, config: Optional[TfrsConfig] = None):
        self.config = config or TfrsConfig()
        self.trainer = TfrsTrainer(self.config)
        self.serving = TfrsServing(self.config)
        self._training_lock: Dict[str, bool] = {}  # shop_id -> is_training

    async def train_shop(self, shop_id: str, force: bool = False) -> Dict[str, Any]:
        """Train model for a specific shop."""
        if self._training_lock.get(shop_id) and not force:
            return {"status": "skipped", "reason": "already_training"}

        self._training_lock[shop_id] = True
        try:
            result = await self.trainer.train_for_shop(shop_id)

            # Invalidate serving cache so new model is loaded
            if result.get("status") == "success":
                self.serving.invalidate_cache(shop_id)

            return result
        finally:
            self._training_lock[shop_id] = False

    async def train_all_shops(
        self, shop_ids: Optional[List[str]] = None, concurrency: int = 3
    ) -> List[Dict[str, Any]]:
        """Train models for multiple shops (usually all active shops)."""
        if shop_ids is None:
            shop_ids = await self._get_active_shops()

        logger.info(
            f"Training TFRS models for {len(shop_ids)} shops (concurrency={concurrency})"
        )

        semaphore = asyncio.Semaphore(concurrency)

        async def _train_one(shop_id: str) -> Dict[str, Any]:
            async with semaphore:
                return await self.train_shop(shop_id)

        tasks = [_train_one(sid) for sid in shop_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        summary = {"trained": 0, "skipped": 0, "failed": 0, "results": []}
        for shop_id, result in zip(shop_ids, results):
            if isinstance(result, Exception):
                summary["failed"] += 1
                summary["results"].append({"shop_id": shop_id, "error": str(result)})
            elif result.get("status") == "success":
                summary["trained"] += 1
                summary["results"].append(result)
            else:
                summary["skipped"] += 1
                summary["results"].append(result)

        logger.info(
            f"Training complete: {summary['trained']} trained, "
            f"{summary['skipped']} skipped, {summary['failed']} failed"
        )
        return summary

    async def _get_active_shops(self) -> List[str]:
        """Get list of active shop IDs that need training."""
        from app.core.database.models import Shop
        from app.core.database.session import get_transaction_context
        from sqlalchemy import select

        async with get_transaction_context() as session:
            result = await session.execute(
                select(Shop.shop_id).where(Shop.status == "ACTIVE")
            )
            return [row[0] for row in result.all()]

    async def scheduled_training(self) -> Dict[str, Any]:
        """Called by scheduler on a timer. Trains shops that need updating."""
        logger.info("Starting scheduled TFRS training...")
        result = await self.train_all_shops()
        logger.info(f"Scheduled training complete: {result.get('trained', 0)} trained")
        return result
