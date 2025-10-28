"""
Customer Linking Scheduler

This module handles periodic backfilling of customer IDs for anonymous events
based on the UserIdentityLink table.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from app.core.logging import get_logger
from app.core.database.session import get_session_context
from app.core.database.models.identity import UserIdentityLink
from app.core.database.models.user_interaction import UserInteraction
from app.core.database.models.user_session import UserSession
from sqlalchemy import select, func, and_, or_
from app.shared.helpers.datetime_utils import now_utc

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
        pass

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
            async with get_session_context() as session:
                # Find links that haven't been backfilled
                # We'll use a simple approach: check if there are any events with this clientId
                # that still have customerId = None
                unprocessed_links = []

                # Get all UserIdentityLink records
                all_links_result = await session.execute(
                    select(UserIdentityLink)
                    .order_by(UserIdentityLink.linked_at.desc())
                    .limit(batch_size)
                )
                all_links = all_links_result.scalars().all()

                for link in all_links:
                    # Check if there are any events with this identifier that still need backfilling
                    # We need to find sessions with this identifier first, then check their interactions
                    # Try both client_id and browser_session_id matching
                    sessions_result = await session.execute(
                        select(UserSession).where(
                            and_(
                                UserSession.shop_id == link.shop_id,
                                or_(
                                    UserSession.client_id
                                    == link.identifier,  # Try client_id first
                                    UserSession.browser_session_id
                                    == link.identifier,  # Fallback to browser_session_id
                                ),
                            )
                        )
                    )
                    sessions_with_identifier = sessions_result.scalars().all()

                    # If no sessions found by identifier, try to find sessions by customer_id
                    # This handles cases where Apollo sessions are separate from unified sessions
                    if not sessions_with_identifier:
                        sessions_result = await session.execute(
                            select(UserSession).where(
                                and_(
                                    UserSession.shop_id == link.shop_id,
                                    UserSession.customer_id == link.customer_id,
                                )
                            )
                        )
                        sessions_with_identifier = sessions_result.scalars().all()

                    if sessions_with_identifier:
                        # Check if any interactions for these sessions need backfilling
                        session_ids = [s.id for s in sessions_with_identifier]
                        events_needing_backfill_result = await session.execute(
                            select(UserInteraction)
                            .where(
                                and_(
                                    UserInteraction.shop_id == link.shop_id,
                                    UserInteraction.session_id.in_(session_ids),
                                    UserInteraction.customer_id.is_(None),
                                )
                            )
                            .limit(1)
                        )
                        events_needing_backfill = (
                            events_needing_backfill_result.scalar_one_or_none()
                        )

                        if events_needing_backfill:
                            unprocessed_links.append(link)

                logger.info(
                    f"Found {len(unprocessed_links)} unprocessed customer links"
                )
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
            async with get_session_context() as session:
                for link in links:
                    try:
                        # Find sessions with this identifier (try both client_id and browser_session_id)
                        sessions_result = await session.execute(
                            select(UserSession).where(
                                and_(
                                    UserSession.shop_id == link.shop_id,
                                    or_(
                                        UserSession.client_id == link.identifier,
                                        UserSession.browser_session_id
                                        == link.identifier,
                                    ),
                                )
                            )
                        )
                        sessions_with_identifier = sessions_result.scalars().all()

                        # If no sessions found by identifier, try to find sessions by customer_id
                        # This handles cases where Apollo sessions are separate from unified sessions
                        if not sessions_with_identifier:
                            sessions_result = await session.execute(
                                select(UserSession).where(
                                    and_(
                                        UserSession.shop_id == link.shop_id,
                                        UserSession.customer_id == link.customer_id,
                                    )
                                )
                            )
                            sessions_with_identifier = sessions_result.scalars().all()

                        if not sessions_with_identifier:
                            logger.warning(
                                f"No sessions found for identifier: {link.identifier}"
                            )
                            continue

                        # Get session IDs
                        session_ids = [s.id for s in sessions_with_identifier]

                        # Update all events for these sessions that don't have a customerId
                        from sqlalchemy import update

                        update_stmt = (
                            update(UserInteraction)
                            .where(
                                and_(
                                    UserInteraction.shop_id == link.shop_id,
                                    UserInteraction.session_id.in_(session_ids),
                                    UserInteraction.customer_id.is_(None),
                                )
                            )
                            .values(
                                customer_id=link.customer_id,
                                updated_at=now_utc(),
                            )
                        )

                        result = await session.execute(update_stmt)
                        updated_count = result.rowcount
                        await session.commit()

                        stats["processed_links"] += 1
                        stats["total_events_backfilled"] += updated_count

                        logger.info(
                            f"Backfilled {updated_count} events for link: {link.identifier} → {link.customer_id}"
                        )

                    except Exception as e:
                        logger.error(
                            f"Failed to backfill link {link.identifier} → {link.customer_id}: {e}"
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
        start_time = now_utc()
        logger.info("Starting customer linking backfill job")

        try:
            # Find unprocessed links
            unprocessed_links = await self.find_unprocessed_links(batch_size)

            if not unprocessed_links:
                logger.info("No unprocessed customer links found")
                return {
                    "status": "success",
                    "message": "No unprocessed links found",
                    "duration_seconds": (now_utc() - start_time).total_seconds(),
                    "processed_links": 0,
                    "total_events_backfilled": 0,
                    "errors": 0,
                }

            # Backfill the links
            backfill_stats = await self.backfill_customer_links(unprocessed_links)

            duration = (now_utc() - start_time).total_seconds()

            logger.info(
                f"Customer linking backfill job completed in {duration:.2f}s. "
                f"Processed {backfill_stats['processed_links']} links, "
                f"backfilled {backfill_stats['total_events_backfilled']} events, "
                f"errors: {backfill_stats['errors']}"
            )

            return {"status": "success", "duration_seconds": duration, **backfill_stats}

        except Exception as e:
            duration = (now_utc() - start_time).total_seconds()
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
