"""
Customer Linking Scheduler

This module handles periodic backfilling of customer IDs for anonymous events
based on the UserIdentityLink table.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from app.core.logging import get_logger
from app.core.database.simple_db_client import get_database

logger = get_logger(__name__)


class CustomerLinkingScheduler:
    """
    Scheduler for periodic customer linking and backfilling operations.

    This service:
    1. Finds new UserIdentityLink records that haven't been backfilled
    2. Backfills customer_id for all anonymous events with matching clientId
    3. Marks links as processed to avoid duplicate work
    """

    def __init__(self):
        self.db = None

    async def _get_database(self):
        """Get database connection"""
        if not self.db:
            self.db = await get_database()
        return self.db

    async def find_unprocessed_links(
        self, batch_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Find UserIdentityLink records that haven't been backfilled yet.

        Args:
            batch_size: Maximum number of links to process in one batch

        Returns:
            List of unprocessed link records
        """
        try:
            db = await self._get_database()

            # Find links that haven't been backfilled
            # We'll use a simple approach: check if there are any events with this clientId
            # that still have customerId = None
            unprocessed_links = []

            # Get all UserIdentityLink records
            all_links = await db.useridentitylink.find_many(
                take=batch_size, order={"linkedAt": "desc"}
            )

            for link in all_links:
                # Check if there are any events with this clientId that still need backfilling
                # We need to find sessions with this clientId first, then check their interactions
                sessions_with_client_id = await db.usersession.find_many(
                    where={
                        "shopId": link.shopId,
                        "browserSessionId": link.clientId,  # clientId maps to browserSessionId
                    }
                )
                
                if sessions_with_client_id:
                    # Check if any interactions for these sessions need backfilling
                    session_ids = [s.id for s in sessions_with_client_id]
                    events_needing_backfill = await db.userinteraction.find_first(
                        where={
                            "shopId": link.shopId,
                            "sessionId": {"in": session_ids},
                            "customerId": None,
                        }
                    )

                    if events_needing_backfill:
                        unprocessed_links.append(link)

            logger.info(f"Found {len(unprocessed_links)} unprocessed customer links")
            return unprocessed_links

        except Exception as e:
            logger.error(f"Failed to find unprocessed links: {e}")
            return []

    async def backfill_customer_links(
        self, links: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Backfill customer_id for events based on the provided links.

        Args:
            links: List of UserIdentityLink records to process

        Returns:
            Dictionary with backfill statistics
        """
        stats = {"processed_links": 0, "total_events_backfilled": 0, "errors": 0}

        try:
            db = await self._get_database()

            for link in links:
                try:
                    # Find sessions with this clientId (browserSessionId)
                    sessions_with_client_id = await db.usersession.find_many(
                        where={
                            "shopId": link.shopId,
                            "browserSessionId": link.clientId,
                        }
                    )
                    
                    if not sessions_with_client_id:
                        logger.warning(f"No sessions found for clientId: {link.clientId}")
                        continue
                    
                    # Get session IDs
                    session_ids = [s.id for s in sessions_with_client_id]
                    
                    # Update all events for these sessions that don't have a customerId
                    from datetime import datetime

                    now_utc = lambda: datetime.now()

                    updated_count = await db.userinteraction.update_many(
                        where={
                            "shopId": link.shopId,
                            "sessionId": {"in": session_ids},
                            "customerId": None,
                        },
                        data={
                            "customerId": link.customerId,
                            "updatedAt": now_utc(),  # Update timestamp to trigger feature computation
                        },
                    )

                    stats["processed_links"] += 1
                    stats["total_events_backfilled"] += updated_count

                    logger.info(
                        f"Backfilled {updated_count} events for link: {link.clientId} → {link.customerId}"
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to backfill link {link.clientId} → {link.customerId}: {e}"
                    )
                    stats["errors"] += 1

            return stats

        except Exception as e:
            logger.error(f"Failed to backfill customer links: {e}")
            stats["errors"] += 1
            return stats

    async def run_backfill_job(self, batch_size: int = 100) -> Dict[str, Any]:
        """
        Run a complete backfill job.

        Args:
            batch_size: Maximum number of links to process in one batch

        Returns:
            Job execution statistics
        """
        start_time = datetime.now()
        logger.info("Starting customer linking backfill job")

        try:
            # Find unprocessed links
            unprocessed_links = await self.find_unprocessed_links(batch_size)

            if not unprocessed_links:
                logger.info("No unprocessed customer links found")
                return {
                    "status": "success",
                    "message": "No unprocessed links found",
                    "duration_seconds": (datetime.now() - start_time).total_seconds(),
                    "processed_links": 0,
                    "total_events_backfilled": 0,
                    "errors": 0,
                }

            # Backfill the links
            backfill_stats = await self.backfill_customer_links(unprocessed_links)

            duration = (datetime.now() - start_time).total_seconds()

            logger.info(
                f"Customer linking backfill job completed in {duration:.2f}s. "
                f"Processed {backfill_stats['processed_links']} links, "
                f"backfilled {backfill_stats['total_events_backfilled']} events, "
                f"errors: {backfill_stats['errors']}"
            )

            return {"status": "success", "duration_seconds": duration, **backfill_stats}

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(
                f"Customer linking backfill job failed after {duration:.2f}s: {e}"
            )
            return {"status": "error", "error": str(e), "duration_seconds": duration}

    async def run_periodic_backfill(self, interval_minutes: int = 30):
        """
        Run periodic backfill jobs.

        Args:
            interval_minutes: Interval between backfill jobs in minutes
        """
        logger.info(
            f"Starting periodic customer linking backfill (interval: {interval_minutes} minutes)"
        )

        while True:
            try:
                await self.run_backfill_job()
                await asyncio.sleep(interval_minutes * 60)
            except Exception as e:
                logger.error(f"Error in periodic backfill: {e}")
                # Wait a bit before retrying
                await asyncio.sleep(60)


# Global scheduler instance
customer_linking_scheduler = CustomerLinkingScheduler()
