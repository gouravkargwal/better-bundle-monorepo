"""
Cross-Session Linking Service

Industry-standard service for linking customer sessions across time periods
using privacy-compliant methods and industry best practices.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from sqlalchemy import select
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
        """Link high-confidence sessions to customer"""
        linked_sessions = []

        for session, confidence, match_type in scored_sessions:
            try:
                # Link session to customer
                await self.session_service.update_session(
                    session.id,
                    SessionUpdate(customer_id=customer_id),
                )

                # Update interactions in this session
                await self._update_session_interactions(session.id, customer_id)

                linked_sessions.append(session)

            except Exception as e:
                logger.error(f"Error linking session {session.id}: {str(e)}")

        return linked_sessions

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
                    logger.warning(
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
