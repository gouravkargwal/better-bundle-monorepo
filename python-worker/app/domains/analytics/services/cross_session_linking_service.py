"""
Cross-Session Linking Service

Industry-standard service for linking customer sessions across time periods
using privacy-compliant methods and industry best practices.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from sqlalchemy import select, and_
from app.core.database.session import get_session_context
from app.core.database.models.user_session import UserSession as SAUserSession
from app.core.database.models.user_interaction import (
    UserInteraction as SAUserInteraction,
)
from app.core.database.models.identity import UserIdentityLink as SAUserIdentityLink
from app.domains.analytics.models.session import (
    UserSession,
    SessionStatus,
    SessionUpdate,
)
from app.domains.analytics.services.unified_session_service import UnifiedSessionService

# Removed deprecated CustomerIdentityResolutionService import
from app.shared.helpers.datetime_utils import utcnow
from app.core.logging.logger import get_logger
from app.core.messaging.event_publisher import EventPublisher
from app.core.config.kafka_settings import kafka_settings

logger = get_logger(__name__)


@dataclass
class SessionLink:
    """Represents a link between sessions"""

    from_session_id: str
    to_session_id: str
    link_type: str  # 'customer_id', 'browser_session', 'ip_user_agent'
    confidence: float
    created_at: datetime


class CrossSessionLinkingService:
    """
    Industry-standard cross-session linking service

    Implements privacy-compliant methods for linking customer sessions
    across different time periods and devices.
    """

    def __init__(self):
        self.session_service = UnifiedSessionService()

        # Industry-standard linking parameters
        self.max_journey_days = 30  # Maximum journey span to consider
        self.min_confidence_threshold = 0.60  # Minimum confidence for linking
        self.ip_ua_confidence_base = 0.70  # Base confidence for IP + UA matching

    async def link_customer_sessions(
        self, customer_id: str, shop_id: str, trigger_session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Link all sessions for a customer using industry-standard methods

        ✅ SCENARIO 33: Anonymous to Customer Conversion

        Story: Sarah browses anonymously, sees recommendations, then creates
        an account and logs in. We need to link her anonymous sessions to
        her new customer account for proper attribution.
        """
        try:

            # ✅ FIX: If trigger_session_id provided, update that session FIRST
            if trigger_session_id:
                # Update the trigger session with customer_id
                await self.session_service.update_session(
                    trigger_session_id, SessionUpdate(customer_id=customer_id)
                )
                # Backfill interactions in trigger session
                await self._update_session_interactions(trigger_session_id, customer_id)

            # Step 1: Get all existing sessions for this customer
            existing_sessions = await self._get_customer_sessions(customer_id, shop_id)

            if not existing_sessions:
                # If we updated trigger session, return that as success
                if trigger_session_id:
                    return {
                        "success": True,
                        "customer_id": customer_id,
                        "existing_sessions": 1,
                        "linked_sessions": [],
                        "total_sessions": 1,
                    }
                return {"success": False, "error": "No sessions found for customer"}

            # Step 2: Find unlinked anonymous sessions
            potential_sessions = await self._find_potential_sessions(
                existing_sessions, shop_id
            )

            # Step 3: Calculate confidence scores
            scored_sessions = await self._score_potential_sessions(
                existing_sessions, potential_sessions
            )

            # Step 4: Link high-confidence matches
            linked_sessions = await self._link_high_confidence_sessions(
                scored_sessions, customer_id
            )

            # Step 5: Create session links
            session_links = await self._create_session_links(
                existing_sessions, linked_sessions, customer_id
            )

            # Step 6: Store identity links in database
            await self._store_customer_identity_links(
                customer_id, shop_id, existing_sessions + linked_sessions
            )

            # Step 7: Generate journey summary
            journey_summary = await self._generate_journey_summary(
                customer_id, existing_sessions + linked_sessions
            )

            result = {
                "success": True,
                "customer_id": customer_id,
                "existing_sessions": len(existing_sessions),
                "linked_sessions": [
                    s.id for s in linked_sessions
                ],  # ✅ Return session IDs
                "total_sessions": len(existing_sessions) + len(linked_sessions),
                "session_links": len(session_links),
                "journey_summary": journey_summary,
                "linking_methods": self._get_linking_methods_summary(scored_sessions),
            }

            return result

        except Exception as e:
            logger.error(f"Error in cross-session linking: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _get_customer_sessions(
        self, customer_id: str, shop_id: str
    ) -> List[UserSession]:
        """Get all existing sessions for a customer"""
        try:
            async with get_session_context() as session:
                stmt = (
                    select(SAUserSession)
                    .where(
                        SAUserSession.shop_id == shop_id,
                        SAUserSession.customer_id == str(customer_id),
                    )
                    .order_by(SAUserSession.created_at.asc())
                )
                result = await session.execute(stmt)
                rows = result.scalars().all()

            sessions = [
                UserSession(
                    id=row.id,
                    shop_id=row.shop_id,
                    customer_id=row.customer_id,
                    browser_session_id=row.browser_session_id,
                    status=SessionStatus(row.status),
                    created_at=row.created_at,
                    last_active=row.last_active,
                    expires_at=row.expires_at,
                    user_agent=row.user_agent,
                    ip_address=row.ip_address,
                    referrer=row.referrer,
                    extensions_used=row.extensions_used,
                    total_interactions=row.total_interactions,
                )
                for row in rows
            ]

            return sessions

        except Exception as e:
            logger.error(f"Error getting customer sessions: {str(e)}")
            return []

    async def _find_potential_sessions(
        self, existing_sessions: List[UserSession], shop_id: str
    ) -> List[UserSession]:
        """Find anonymous sessions that might belong to this customer"""
        try:
            # Get unique identifiers from existing sessions
            ip_addresses = list(
                set(s.ip_address for s in existing_sessions if s.ip_address)
            )
            user_agents = list(
                set(s.user_agent for s in existing_sessions if s.user_agent)
            )
            browser_session_ids = list(
                set(s.browser_session_id for s in existing_sessions)
            )

            # If no identifiers, return empty
            if not (ip_addresses or user_agents or browser_session_ids):
                return []

            # ✅ FIX: Build OR conditions properly
            from sqlalchemy import or_

            or_conditions = []

            if ip_addresses:
                or_conditions.append(SAUserSession.ip_address.in_(ip_addresses))

            if user_agents:
                or_conditions.append(SAUserSession.user_agent.in_(user_agents))

            if browser_session_ids:
                or_conditions.append(
                    SAUserSession.browser_session_id.in_(browser_session_ids)
                )

            # If no conditions, return empty (shouldn't happen due to check above)
            if not or_conditions:
                return []

            async with get_session_context() as session:
                stmt = (
                    select(SAUserSession)
                    .where(
                        SAUserSession.shop_id == shop_id,
                        SAUserSession.customer_id.is_(None),
                        SAUserSession.status == "active",
                        SAUserSession.expires_at > utcnow(),
                        or_(*or_conditions),  # ✅ Use or_() properly
                    )
                    .order_by(SAUserSession.created_at.asc())
                )
                result = await session.execute(stmt)
                rows = result.scalars().all()

            existing_session_ids = {s.id for s in existing_sessions}
            potential_sessions = [
                UserSession(
                    id=row.id,
                    shop_id=row.shop_id,
                    customer_id=row.customer_id,
                    browser_session_id=row.browser_session_id,
                    status=SessionStatus(row.status),
                    created_at=row.created_at,
                    last_active=row.last_active,
                    expires_at=row.expires_at,
                    user_agent=row.user_agent,
                    ip_address=row.ip_address,
                    referrer=row.referrer,
                    extensions_used=row.extensions_used,
                    total_interactions=row.total_interactions,
                )
                for row in rows
                if row.id not in existing_session_ids
            ]

            return potential_sessions

        except Exception as e:
            logger.error(f"Error finding potential sessions: {str(e)}")
            return []

    async def _score_potential_sessions(
        self,
        existing_sessions: List[UserSession],
        potential_sessions: List[UserSession],
    ) -> List[Tuple[UserSession, float, str]]:
        """Score potential sessions based on matching criteria"""
        try:
            scored_sessions = []

            for potential_session in potential_sessions:
                confidence, match_type = self._calculate_session_confidence(
                    potential_session, existing_sessions
                )

                if confidence >= self.min_confidence_threshold:
                    scored_sessions.append((potential_session, confidence, match_type))

            # Sort by confidence score (highest first)
            scored_sessions.sort(key=lambda x: x[1], reverse=True)

            return scored_sessions

        except Exception as e:
            logger.error(f"Error scoring potential sessions: {str(e)}")
            return []

    def _calculate_session_confidence(
        self, potential_session: UserSession, existing_sessions: List[UserSession]
    ) -> Tuple[float, str]:
        """Calculate confidence score for a potential session match"""
        try:
            max_confidence = 0.0
            best_match_type = "unknown"

            for existing_session in existing_sessions:
                # Method 1: Browser session ID match (deterministic)
                if (
                    potential_session.browser_session_id
                    == existing_session.browser_session_id
                    and potential_session.browser_session_id
                ):
                    confidence = 0.95
                    match_type = "browser_session_id"
                    if confidence > max_confidence:
                        max_confidence = confidence
                        best_match_type = match_type

                # Method 2: IP + User Agent match (probabilistic)
                if (
                    potential_session.ip_address == existing_session.ip_address
                    and potential_session.user_agent == existing_session.user_agent
                    and potential_session.ip_address
                    and potential_session.user_agent
                ):

                    confidence = self._calculate_ip_ua_confidence(
                        potential_session, existing_session
                    )
                    match_type = "ip_user_agent"
                    if confidence > max_confidence:
                        max_confidence = confidence
                        best_match_type = match_type

                # Method 3: IP address only (lower confidence)
                if (
                    potential_session.ip_address == existing_session.ip_address
                    and potential_session.ip_address
                ):

                    confidence = 0.50  # Lower confidence for IP only
                    match_type = "ip_address"
                    if confidence > max_confidence:
                        max_confidence = confidence
                        best_match_type = match_type

                # Method 4: User Agent only (very low confidence)
                if (
                    potential_session.user_agent == existing_session.user_agent
                    and potential_session.user_agent
                ):

                    confidence = 0.30  # Very low confidence for UA only
                    match_type = "user_agent"
                    if confidence > max_confidence:
                        max_confidence = confidence
                        best_match_type = match_type

            return max_confidence, best_match_type

        except Exception as e:
            logger.error(f"Error calculating session confidence: {str(e)}")
            return 0.0, "error"

    def _calculate_ip_ua_confidence(
        self, potential_session: UserSession, existing_session: UserSession
    ) -> float:
        """Calculate confidence for IP + User Agent matching"""
        try:
            confidence = self.ip_ua_confidence_base

            # Boost confidence based on time proximity
            time_diff = abs(
                (
                    potential_session.created_at - existing_session.created_at
                ).total_seconds()
            )

            if time_diff < 3600:  # Within 1 hour
                confidence += 0.15
            elif time_diff < 86400:  # Within 1 day
                confidence += 0.10
            elif time_diff < 604800:  # Within 1 week
                confidence += 0.05

            # Boost confidence based on activity similarity
            if (
                potential_session.total_interactions > 0
                and existing_session.total_interactions > 0
            ):
                activity_ratio = min(
                    potential_session.total_interactions,
                    existing_session.total_interactions,
                ) / max(
                    potential_session.total_interactions,
                    existing_session.total_interactions,
                )
                confidence += activity_ratio * 0.10

            # Boost confidence based on extensions used
            common_extensions = set(potential_session.extensions_used) & set(
                existing_session.extensions_used
            )
            if common_extensions:
                confidence += len(common_extensions) * 0.05

            return min(confidence, 0.95)  # Cap at 95%

        except Exception as e:
            logger.error(f"Error calculating IP/UA confidence: {str(e)}")
            return self.ip_ua_confidence_base

    async def _link_high_confidence_sessions(
        self, scored_sessions: List[Tuple[UserSession, float, str]], customer_id: str
    ) -> List[UserSession]:
        """
        ✅ SCENARIO 8: Link high-confidence sessions to customer with attribution aggregation

        Story: Sarah browses anonymously, sees recommendations, then logs in.
        We need to link her anonymous sessions to her customer account and
        aggregate all her interactions for proper attribution.
        """
        linked_sessions = []

        for session, confidence, match_type in scored_sessions:
            try:
                # Check if updating customer_id would cause constraint violation
                if await self._would_cause_constraint_violation(session, customer_id):
                    logger.warning(
                        f"Skipping session {session.id} - would cause constraint violation"
                    )
                    continue

                # Link session to customer
                await self.session_service.update_session(
                    session.id,
                    SessionUpdate(customer_id=customer_id),
                )

                # ✅ SCENARIO 8: Update interactions in this session with customer attribution
                await self._update_session_interactions(session.id, customer_id)

                # ✅ SCENARIO 8: Aggregate customer-level attribution
                await self._aggregate_customer_attribution(customer_id, session.id)

                linked_sessions.append(session)

            except Exception as e:
                logger.error(f"Error linking session {session.id}: {str(e)}")

        return linked_sessions

    async def _aggregate_customer_attribution(
        self, customer_id: str, session_id: str
    ) -> None:
        """
        ✅ SCENARIO 8 & 10: Aggregate customer-level attribution across all sessions

        Story: When Sarah logs in, we need to aggregate all her interactions
        from anonymous sessions to provide complete attribution context.
        This also handles multiple sessions for the same customer.
        """
        try:
            from app.core.database.models.interaction import (
                Interaction as SAInteraction,
            )
            from app.core.database.models.user_session import (
                UserSession as SAUserSession,
            )

            async with get_session_context() as session:
                # Get all sessions for this customer
                customer_sessions_query = select(SAUserSession).where(
                    SAUserSession.customer_id == customer_id
                )
                customer_sessions_result = await session.execute(
                    customer_sessions_query
                )
                customer_sessions = customer_sessions_result.scalars().all()

                session_ids = [s.id for s in customer_sessions]

                # Get all interactions across all customer sessions
                interactions_query = select(SAInteraction).where(
                    SAInteraction.session_id.in_(session_ids)
                )
                interactions_result = await session.execute(interactions_query)
                all_interactions = interactions_result.scalars().all()

                # Group interactions by product for attribution
                product_interactions = {}
                for interaction in all_interactions:
                    product_id = interaction.product_id
                    if product_id not in product_interactions:
                        product_interactions[product_id] = []

                    product_interactions[product_id].append(
                        {
                            "id": interaction.id,
                            "session_id": interaction.session_id,
                            "extension_type": interaction.extension_type,
                            "interaction_type": interaction.interaction_type,
                            "product_id": interaction.product_id,
                            "created_at": interaction.created_at,
                            "metadata": interaction.metadata or {},
                        }
                    )

                # Log customer attribution aggregation
                logger.info(
                    f"🔗 Customer {customer_id} attribution aggregated: "
                    f"{len(customer_sessions)} sessions, "
                    f"{len(all_interactions)} interactions, "
                    f"{len(product_interactions)} products"
                )

                # Store aggregated attribution data for future use
                await self._store_customer_attribution_summary(
                    customer_id, product_interactions
                )

        except Exception as e:
            logger.error(
                f"Error aggregating customer attribution for {customer_id}: {e}"
            )

    async def _store_customer_attribution_summary(
        self, customer_id: str, product_interactions: Dict[str, List[Dict]]
    ) -> None:
        """
        Store customer attribution summary for future attribution calculations.

        This helps with cross-session attribution when the customer makes purchases.
        """
        try:
            # This could be stored in a customer_attribution_summary table
            # For now, we'll log the summary
            summary = {
                "customer_id": customer_id,
                "total_products": len(product_interactions),
                "total_interactions": sum(
                    len(interactions) for interactions in product_interactions.values()
                ),
                "products": list(product_interactions.keys()),
            }

            logger.info(f"📊 Customer attribution summary: {summary}")

        except Exception as e:
            logger.error(f"Error storing customer attribution summary: {e}")

    async def _handle_cross_session_attribution(
        self, customer_id: str, product_id: str
    ) -> Dict[str, Any]:
        """
        ✅ SCENARIO 10: Handle cross-session attribution for same customer

        Story: Sarah sees a recommendation in Session A, then makes a purchase
        in Session B. We need to link these sessions and attribute the purchase
        to the recommendation from Session A.

        Args:
            customer_id: Customer identifier
            product_id: Product that was purchased

        Returns:
            Cross-session attribution data
        """
        try:
            from app.core.database.models.interaction import (
                Interaction as SAInteraction,
            )
            from app.core.database.models.user_session import (
                UserSession as SAUserSession,
            )

            async with get_session_context() as session:
                # Get all sessions for this customer
                customer_sessions_query = select(SAUserSession).where(
                    SAUserSession.customer_id == customer_id
                )
                customer_sessions_result = await session.execute(
                    customer_sessions_query
                )
                customer_sessions = customer_sessions_result.scalars().all()

                # Get all interactions for this product across all customer sessions
                session_ids = [s.id for s in customer_sessions]
                interactions_query = select(SAInteraction).where(
                    and_(
                        SAInteraction.session_id.in_(session_ids),
                        SAInteraction.product_id == product_id,
                    )
                )
                interactions_result = await session.execute(interactions_query)
                product_interactions = interactions_result.scalars().all()

                # Group interactions by session
                session_interactions = {}
                for interaction in product_interactions:
                    session_id = interaction.session_id
                    if session_id not in session_interactions:
                        session_interactions[session_id] = []
                    session_interactions[session_id].append(interaction)

                # Calculate cross-session attribution
                attribution_data = {
                    "customer_id": customer_id,
                    "product_id": product_id,
                    "total_sessions": len(customer_sessions),
                    "sessions_with_interactions": len(session_interactions),
                    "total_interactions": len(product_interactions),
                    "session_breakdown": {},
                }

                for session_id, interactions in session_interactions.items():
                    attribution_data["session_breakdown"][session_id] = {
                        "interaction_count": len(interactions),
                        "interaction_types": [i.interaction_type for i in interactions],
                        "extensions": [i.extension_type for i in interactions],
                        "latest_interaction": max(
                            i.created_at for i in interactions
                        ).isoformat(),
                    }

                logger.info(
                    f"🔗 Cross-session attribution for customer {customer_id}, product {product_id}: "
                    f"{len(customer_sessions)} sessions, {len(product_interactions)} interactions"
                )

                return attribution_data

        except Exception as e:
            logger.error(f"Error handling cross-session attribution: {e}")
            return {}

    async def _would_cause_constraint_violation(
        self, session: UserSession, customer_id: str
    ) -> bool:
        """Check if updating session customer_id would cause constraint violation"""
        try:
            async with get_session_context() as db_session:
                from sqlalchemy import select, and_
                from app.core.database.models.user_session import (
                    UserSession as SAUserSession,
                )

                # Check if there's already a session with the same (shop_id, customer_id, browser_session_id)
                existing_query = select(SAUserSession).where(
                    and_(
                        SAUserSession.shop_id == session.shop_id,
                        SAUserSession.customer_id == customer_id,
                        SAUserSession.browser_session_id == session.browser_session_id,
                        SAUserSession.id != session.id,  # Exclude current session
                    )
                )
                result = await db_session.execute(existing_query)
                existing_session = result.scalar_one_or_none()

                return existing_session is not None

        except Exception as e:
            logger.error(f"Error checking constraint violation: {e}")
            # If we can't check, err on the side of caution
            return True

    async def _update_session_interactions(self, session_id: str, customer_id: str):
        """Update all interactions in a session with customer ID"""
        try:
            async with get_session_context() as session:
                stmt = select(SAUserInteraction).where(
                    SAUserInteraction.session_id == session_id
                )
                result = await session.execute(stmt)
                interactions = result.scalars().all()

                for interaction in interactions:
                    interaction.customer_id = customer_id
                await session.commit()

        except Exception as e:
            logger.error(f"Error updating session interactions: {str(e)}")

    async def _create_session_links(
        self,
        existing_sessions: List[UserSession],
        linked_sessions: List[UserSession],
        customer_id: str,
    ) -> List[SessionLink]:
        """Create session links for tracking relationships"""
        try:
            session_links = []
            all_sessions = existing_sessions + linked_sessions

            # Create links between chronologically adjacent sessions
            all_sessions.sort(key=lambda x: x.created_at)

            for i in range(len(all_sessions) - 1):
                current_session = all_sessions[i]
                next_session = all_sessions[i + 1]

                # Calculate time gap
                time_gap = (
                    next_session.created_at - current_session.last_active
                ).total_seconds()

                # Only create links for reasonable time gaps (within 7 days)
                if time_gap < 604800:  # 7 days in seconds
                    link = SessionLink(
                        from_session_id=current_session.id,
                        to_session_id=next_session.id,
                        link_type="temporal",
                        confidence=1.0
                        - (time_gap / 604800),  # Confidence decreases with time gap
                        created_at=utcnow(),
                    )
                    session_links.append(link)

            return session_links

        except Exception as e:
            logger.error(f"Error creating session links: {str(e)}")
            return []

    async def _generate_journey_summary(
        self, customer_id: str, all_sessions: List[UserSession]
    ) -> Dict[str, Any]:
        """Generate summary of customer journey"""
        try:
            if not all_sessions:
                return {}

            # Sort sessions by creation time
            all_sessions.sort(key=lambda x: x.created_at)

            # Calculate journey metrics
            journey_start = all_sessions[0].created_at
            journey_end = all_sessions[-1].last_active
            journey_duration = (journey_end - journey_start).days

            total_interactions = sum(s.total_interactions for s in all_sessions)
            unique_extensions = set()
            for session in all_sessions:
                unique_extensions.update(session.extensions_used)

            # Calculate session frequency
            session_frequency = len(all_sessions) / max(journey_duration, 1)

            return {
                "journey_start": journey_start.isoformat(),
                "journey_end": journey_end.isoformat(),
                "journey_duration_days": journey_duration,
                "total_sessions": len(all_sessions),
                "total_interactions": total_interactions,
                "unique_extensions": list(unique_extensions),
                "session_frequency": round(session_frequency, 2),
                "avg_interactions_per_session": round(
                    total_interactions / len(all_sessions), 2
                ),
            }

        except Exception as e:
            logger.error(f"Error generating journey summary: {str(e)}")
            return {}

    def _get_linking_methods_summary(
        self, scored_sessions: List[Tuple[UserSession, float, str]]
    ) -> Dict[str, Any]:
        """Get summary of linking methods used"""
        method_counts = {}
        total_confidence = 0.0

        for _, confidence, match_type in scored_sessions:
            method_counts[match_type] = method_counts.get(match_type, 0) + 1
            total_confidence += confidence

        return {
            "total_sessions_scored": len(scored_sessions),
            "method_breakdown": method_counts,
            "average_confidence": (
                round(total_confidence / len(scored_sessions), 3)
                if scored_sessions
                else 0.0
            ),
        }

    async def _store_customer_identity_links(
        self,
        customer_id: str,
        shop_id: str,
        sessions: List[UserSession],
    ) -> None:
        """
        Store customer identity links in UserIdentityLink table
        Uses the actual database schema with identifier and identifier_type fields
        Falls back to browser_session_id if client_id is not available
        """
        try:
            links_created = 0
            for session in sessions:
                # Link client_id (primary identifier)
                if session.client_id:
                    created = await self._create_identity_link(
                        shop_id,
                        session.client_id,
                        "client_id",  # identifier_type
                        customer_id,
                    )
                    if created:
                        links_created += 1
                else:
                    # Fallback: Use browser_session_id if client_id is not available
                    # Only log as debug to reduce noise
                    logger.debug(
                        f"Session {session.id} has no client_id, using browser_session_id as fallback"
                    )
                    created = await self._create_identity_link(
                        shop_id,
                        session.browser_session_id,
                        "browser_session_id",  # identifier_type
                        customer_id,
                    )
                    if created:
                        links_created += 1

        except Exception as e:
            logger.error(f"Failed to store identity links: {str(e)}")
            raise

    async def _create_identity_link(
        self,
        shop_id: str,
        identifier: str,
        identifier_type: str,
        customer_id: str,
    ) -> bool:
        """
        Create a single identity link if it doesn't exist
        Uses the actual database schema with identifier and identifier_type fields

        Returns:
            bool: True if link was created, False if it already existed
        """
        try:
            async with get_session_context() as session:
                # Check if link already exists using the actual database schema
                result = await session.execute(
                    select(SAUserIdentityLink).where(
                        SAUserIdentityLink.shop_id == shop_id,
                        SAUserIdentityLink.identifier == identifier,
                        SAUserIdentityLink.customer_id == customer_id,
                    )
                )
                existing_link = result.scalar_one_or_none()

                if not existing_link:
                    link = SAUserIdentityLink(
                        shop_id=shop_id,
                        identifier=identifier,
                        identifier_type=identifier_type,
                        customer_id=customer_id,
                        linked_at=utcnow(),
                    )
                    session.add(link)
                    await session.commit()
                    return True
                else:
                    return False

        except Exception as e:
            logger.error(f"Failed to create identity link: {str(e)}")
            raise

    async def fire_feature_computation_event(
        self,
        shop_id: str,
        trigger_source: str,
        interaction_id: Optional[str] = None,
        batch_size: int = 50,
        incremental: bool = True,
    ) -> Optional[str]:
        """
        Fire a feature computation event to trigger incremental ML pipeline

        Args:
            shop_id: The shop ID to compute features for
            trigger_source: Source that triggered the computation (e.g., "customer_linking")
            interaction_id: Optional interaction ID that triggered the computation
            batch_size: Batch size for feature processing
            incremental: Whether to run incremental processing

        Returns:
            Event ID if successful, None if failed
        """
        try:
            # Generate a unique job ID
            job_id = f"customer_linking_triggered_{shop_id}_{int(utcnow().timestamp())}"

            # Prepare event metadata
            metadata = {
                "batch_size": batch_size,
                "incremental": incremental,
                "trigger_source": trigger_source,
                "interaction_id": interaction_id,
                "timestamp": utcnow().isoformat(),
                "processed_count": 0,
            }

            # Create feature computation event for Kafka
            feature_event = {
                "job_id": job_id,
                "shop_id": shop_id,
                "features_ready": False,  # Need to be computed
                "metadata": metadata,
                "event_type": "feature_computation",
                "data_type": "interactions",
                "timestamp": utcnow().isoformat(),
                "source": "cross_session_linking",
            }

            # Publish the feature computation event to Kafka
            publisher = EventPublisher(kafka_settings.model_dump())
            await publisher.initialize()

            try:
                event_id = await publisher.publish_feature_computation_event(
                    feature_event
                )

                return event_id
            finally:
                await publisher.close()

        except Exception as e:
            logger.error(f"Failed to fire feature computation event: {str(e)}")
            return None

    async def handle_anonymous_to_customer_conversion(
        self, customer_id: str, shop_id: str, conversion_session_id: str
    ) -> Dict[str, Any]:
        """
        ✅ SCENARIO 33: Handle anonymous to customer conversion

        Story: Sarah browses anonymously, sees recommendations, then creates
        an account and logs in. We need to link her anonymous sessions to
        her new customer account for proper attribution.

        Args:
            customer_id: New customer ID after account creation
            shop_id: Shop identifier
            conversion_session_id: Session ID where conversion happened

        Returns:
            Conversion result with linked sessions
        """
        try:
            logger.info(
                f"🔄 Handling anonymous to customer conversion: {customer_id} "
                f"from session {conversion_session_id}"
            )

            # Step 1: Find anonymous sessions that could belong to this customer
            anonymous_sessions = await self._find_anonymous_sessions_for_conversion(
                customer_id, shop_id, conversion_session_id
            )

            if not anonymous_sessions:
                logger.info(f"No anonymous sessions found for conversion {customer_id}")
                return {
                    "success": True,
                    "conversion_type": "anonymous_to_customer",
                    "customer_id": customer_id,
                    "linked_sessions": [],
                    "message": "No anonymous sessions to link",
                }

            # Step 2: Score and link anonymous sessions
            linked_sessions = await self._link_anonymous_sessions_to_customer(
                customer_id, shop_id, anonymous_sessions
            )

            # Step 3: Update conversion session with customer attribution
            await self._update_conversion_session_attribution(
                conversion_session_id, customer_id, linked_sessions
            )

            logger.info(
                f"✅ Anonymous to customer conversion completed: {customer_id}, "
                f"linked {len(linked_sessions)} sessions"
            )

            return {
                "success": True,
                "conversion_type": "anonymous_to_customer",
                "customer_id": customer_id,
                "linked_sessions": [session.id for session in linked_sessions],
                "total_sessions": len(linked_sessions),
                "attribution_updated": True,
            }

        except Exception as e:
            logger.error(f"Error in anonymous to customer conversion: {e}")
            return {
                "success": False,
                "error": str(e),
                "conversion_type": "anonymous_to_customer",
                "customer_id": customer_id,
                "linked_sessions": [],
            }

    async def _find_anonymous_sessions_for_conversion(
        self, customer_id: str, shop_id: str, conversion_session_id: str
    ) -> List[UserSession]:
        """
        ✅ SCENARIO 33: Find anonymous sessions that could belong to this customer

        Story: When Sarah creates an account, we need to find her previous
        anonymous sessions based on browser fingerprinting, IP address,
        and interaction patterns.
        """
        try:
            # Get conversion session for fingerprinting
            conversion_session = await self.session_service.get_session(
                conversion_session_id
            )
            if not conversion_session:
                return []

            # Find anonymous sessions with similar characteristics
            anonymous_sessions = await self._find_sessions_by_fingerprint(
                shop_id, conversion_session, is_anonymous=True
            )

            # Filter sessions that are likely from the same user
            likely_sessions = []
            for session in anonymous_sessions:
                confidence = await self._calculate_conversion_confidence(
                    session, conversion_session
                )
                if confidence >= self.min_confidence_threshold:
                    likely_sessions.append(session)

            logger.info(
                f"🔍 Found {len(likely_sessions)} likely anonymous sessions "
                f"for conversion {customer_id}"
            )

            return likely_sessions

        except Exception as e:
            logger.error(f"Error finding anonymous sessions for conversion: {e}")
            return []

    async def _link_anonymous_sessions_to_customer(
        self, customer_id: str, shop_id: str, anonymous_sessions: List[UserSession]
    ) -> List[UserSession]:
        """
        ✅ SCENARIO 33: Link anonymous sessions to customer account

        Story: Once we've identified Sarah's anonymous sessions, we need
        to link them to her new customer account for proper attribution.
        """
        try:
            linked_sessions = []

            for session in anonymous_sessions:
                try:
                    # Link session to customer
                    await self.session_service.update_session(
                        session.id, SessionUpdate(customer_id=customer_id)
                    )

                    # Update interactions with customer attribution
                    await self._update_session_interactions(session.id, customer_id)

                    # Aggregate customer-level attribution
                    await self._aggregate_customer_attribution(customer_id, session.id)

                    linked_sessions.append(session)

                    logger.info(
                        f"🔗 Linked anonymous session {session.id} to customer {customer_id}"
                    )

                except Exception as e:
                    logger.error(f"Error linking session {session.id}: {e}")

            return linked_sessions

        except Exception as e:
            logger.error(f"Error linking anonymous sessions to customer: {e}")
            return []

    async def _update_conversion_session_attribution(
        self,
        conversion_session_id: str,
        customer_id: str,
        linked_sessions: List[UserSession],
    ) -> None:
        """
        ✅ SCENARIO 33: Update conversion session with aggregated attribution

        Story: After linking anonymous sessions, we need to update the
        conversion session with the complete attribution picture.
        """
        try:
            # Update conversion session interactions
            await self._update_session_interactions(conversion_session_id, customer_id)

            # Aggregate all customer attribution including conversion session
            await self._aggregate_customer_attribution(
                customer_id, conversion_session_id
            )

            logger.info(
                f"📊 Updated conversion session {conversion_session_id} "
                f"with customer attribution for {customer_id}"
            )

        except Exception as e:
            logger.error(f"Error updating conversion session attribution: {e}")

    async def _calculate_conversion_confidence(
        self, anonymous_session: UserSession, conversion_session: UserSession
    ) -> float:
        """
        ✅ SCENARIO 33: Calculate confidence that anonymous session belongs to customer

        Story: We need to determine how likely it is that an anonymous session
        belongs to the same person as the conversion session.
        """
        try:
            confidence_factors = []

            # IP address matching
            if (
                anonymous_session.ip_address
                and conversion_session.ip_address
                and anonymous_session.ip_address == conversion_session.ip_address
            ):
                confidence_factors.append(0.8)

            # User agent matching
            if (
                anonymous_session.user_agent
                and conversion_session.user_agent
                and anonymous_session.user_agent == conversion_session.user_agent
            ):
                confidence_factors.append(0.7)

            # Browser session ID matching
            if (
                anonymous_session.browser_session_id
                and conversion_session.browser_session_id
                and anonymous_session.browser_session_id
                == conversion_session.browser_session_id
            ):
                confidence_factors.append(0.9)

            # Time proximity (sessions close in time)
            time_diff = abs(
                (
                    anonymous_session.last_active - conversion_session.last_active
                ).total_seconds()
            )
            if time_diff < 3600:  # Within 1 hour
                confidence_factors.append(0.6)
            elif time_diff < 86400:  # Within 24 hours
                confidence_factors.append(0.4)

            # Interaction pattern similarity
            # This would require comparing interaction patterns
            # For now, we'll use a base score
            confidence_factors.append(0.3)

            # Calculate weighted average
            if confidence_factors:
                return sum(confidence_factors) / len(confidence_factors)

            return 0.0

        except Exception as e:
            logger.error(f"Error calculating conversion confidence: {e}")
            return 0.0

    async def handle_multiple_devices_same_customer(
        self, customer_id: str, shop_id: str, device_sessions: List[str]
    ) -> Dict[str, Any]:
        """
        ✅ SCENARIO 34: Handle multiple devices for same customer

        Story: Sarah uses her phone to browse and see recommendations, then
        switches to her laptop to complete the purchase. We need to link
        sessions across devices for proper attribution.

        Args:
            customer_id: Customer identifier
            shop_id: Shop identifier
            device_sessions: List of session IDs from different devices

        Returns:
            Multi-device linking result
        """
        try:
            logger.info(
                f"📱 Handling multiple devices for customer {customer_id} "
                f"with {len(device_sessions)} device sessions"
            )

            # Step 1: Get all device sessions
            device_session_objects = []
            for session_id in device_sessions:
                session = await self.session_service.get_session(session_id)
                if session:
                    device_session_objects.append(session)

            if not device_session_objects:
                logger.warning(
                    f"No valid device sessions found for customer {customer_id}"
                )
                return {
                    "success": False,
                    "error": "No valid device sessions found",
                    "customer_id": customer_id,
                    "linked_sessions": [],
                }

            # Step 2: Link sessions across devices
            linked_sessions = await self._link_device_sessions(
                customer_id, shop_id, device_session_objects
            )

            # Step 3: Aggregate cross-device attribution
            attribution_summary = await self._aggregate_cross_device_attribution(
                customer_id, shop_id, linked_sessions
            )

            logger.info(
                f"✅ Multiple devices linking completed for customer {customer_id}: "
                f"{len(linked_sessions)} sessions linked"
            )

            return {
                "success": True,
                "scenario": "multiple_devices_same_customer",
                "customer_id": customer_id,
                "linked_sessions": [session.id for session in linked_sessions],
                "total_devices": len(device_sessions),
                "attribution_summary": attribution_summary,
            }

        except Exception as e:
            logger.error(
                f"Error handling multiple devices for customer {customer_id}: {e}"
            )
            return {
                "success": False,
                "error": str(e),
                "scenario": "multiple_devices_same_customer",
                "customer_id": customer_id,
                "linked_sessions": [],
            }

    async def _link_device_sessions(
        self, customer_id: str, shop_id: str, device_sessions: List[UserSession]
    ) -> List[UserSession]:
        """
        ✅ SCENARIO 34: Link sessions across multiple devices

        Story: We need to link Sarah's phone session to her laptop session
        to maintain attribution continuity across devices.
        """
        try:
            linked_sessions = []

            for session in device_sessions:
                try:
                    # Update session with customer ID if not already set
                    if not session.customer_id:
                        await self.session_service.update_session(
                            session.id, SessionUpdate(customer_id=customer_id)
                        )
                        session.customer_id = customer_id

                    # Update interactions with customer attribution
                    await self._update_session_interactions(session.id, customer_id)

                    linked_sessions.append(session)

                    logger.info(
                        f"📱 Linked device session {session.id} to customer {customer_id}"
                    )

                except Exception as e:
                    logger.error(f"Error linking device session {session.id}: {e}")

            return linked_sessions

        except Exception as e:
            logger.error(f"Error linking device sessions: {e}")
            return []

    async def _aggregate_cross_device_attribution(
        self, customer_id: str, shop_id: str, linked_sessions: List[UserSession]
    ) -> Dict[str, Any]:
        """
        ✅ SCENARIO 34: Aggregate attribution across multiple devices

        Story: After linking sessions across devices, we need to aggregate
        all interactions to provide a complete attribution picture.
        """
        try:
            # Get all interactions across all device sessions
            all_interactions = []
            for session in linked_sessions:
                session_interactions = await self._get_session_interactions(session.id)
                all_interactions.extend(session_interactions)

            # Group interactions by device/session
            device_breakdown = {}
            for session in linked_sessions:
                device_info = self._extract_device_info(session)
                device_key = f"{device_info['type']}_{device_info['os']}"

                if device_key not in device_breakdown:
                    device_breakdown[device_key] = {
                        "device_type": device_info["type"],
                        "os": device_info["os"],
                        "sessions": [],
                        "interactions": 0,
                    }

                device_breakdown[device_key]["sessions"].append(session.id)
                device_breakdown[device_key]["interactions"] += len(
                    [i for i in all_interactions if i.get("session_id") == session.id]
                )

            # Calculate cross-device attribution metrics
            attribution_summary = {
                "customer_id": customer_id,
                "total_sessions": len(linked_sessions),
                "total_interactions": len(all_interactions),
                "device_breakdown": device_breakdown,
                "cross_device_attribution": True,
                "attribution_continuity": "maintained",
            }

            logger.info(
                f"📊 Cross-device attribution aggregated for customer {customer_id}: "
                f"{len(linked_sessions)} sessions, {len(all_interactions)} interactions"
            )

            return attribution_summary

        except Exception as e:
            logger.error(f"Error aggregating cross-device attribution: {e}")
            return {}

    def _extract_device_info(self, session: UserSession) -> Dict[str, str]:
        """
        ✅ SCENARIO 34: Extract device information from session

        Story: We need to identify what type of device Sarah is using
        (phone, laptop, tablet) to understand her multi-device journey.
        """
        try:
            user_agent = session.user_agent or ""
            user_agent_lower = user_agent.lower()

            # Detect device type
            if any(
                mobile in user_agent_lower for mobile in ["mobile", "android", "iphone"]
            ):
                device_type = "mobile"
            elif any(tablet in user_agent_lower for tablet in ["tablet", "ipad"]):
                device_type = "tablet"
            else:
                device_type = "desktop"

            # Detect OS
            if "windows" in user_agent_lower:
                os = "windows"
            elif "mac" in user_agent_lower or "macos" in user_agent_lower:
                os = "macos"
            elif "linux" in user_agent_lower:
                os = "linux"
            elif "android" in user_agent_lower:
                os = "android"
            elif "ios" in user_agent_lower:
                os = "ios"
            else:
                os = "unknown"

            return {"type": device_type, "os": os, "user_agent": user_agent}

        except Exception as e:
            logger.error(f"Error extracting device info: {e}")
            return {"type": "unknown", "os": "unknown", "user_agent": ""}

    async def _get_session_interactions(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all interactions for a specific session"""
        try:
            # This would query the database for interactions
            # For now, return empty list as placeholder
            return []
        except Exception as e:
            logger.error(f"Error getting session interactions: {e}")
            return []
