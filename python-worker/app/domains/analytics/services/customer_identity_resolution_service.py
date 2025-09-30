"""
Customer Identity Resolution Service

Industry-standard service for linking anonymous sessions to identified customers
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
from app.shared.helpers.datetime_utils import utcnow
from app.core.logging.logger import get_logger
from app.core.messaging.event_publisher import EventPublisher
from app.core.config.kafka_settings import kafka_settings

logger = get_logger(__name__)


@dataclass
class IdentityMatch:
    """Represents a potential identity match"""

    session_id: str
    confidence_score: float
    match_type: str  # 'deterministic', 'probabilistic'
    match_reason: str


class CustomerIdentityResolutionService:
    """
    Industry-standard customer identity resolution service

    Implements privacy-compliant methods for linking anonymous sessions
    to identified customers using industry best practices.
    """

    def __init__(self):
        self.session_service = UnifiedSessionService()
        self.deterministic_threshold = 0.95  # High confidence
        self.probabilistic_threshold = 0.70  # Medium confidence
        self.min_confidence_threshold = 0.60  # Minimum for linking

    async def resolve_customer_identity(
        self,
        customer_id: str,
        current_session_id: str,
        shop_id: str,
        customer_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Resolve customer identity and link related sessions

        This is the main method that implements industry-standard
        customer identity resolution.

        Args:
            customer_id: The identified customer ID
            current_session_id: Current session being linked
            shop_id: Shop identifier
            customer_data: Optional customer data for enhanced matching

        Returns:
            Dict with resolution results
        """
        try:
            logger.info(f"Starting identity resolution for customer {customer_id}")

            # Step 1: Link current session to customer
            current_session = await self._link_current_session(
                current_session_id, customer_id
            )

            if not current_session:
                return {"success": False, "error": "Current session not found"}

            # Step 2: Find related anonymous sessions
            related_sessions = await self._find_related_anonymous_sessions(
                current_session, customer_id, shop_id, customer_data
            )

            # Step 3: Link high-confidence matches
            linked_sessions = await self._link_related_sessions(
                related_sessions, customer_id
            )

            # Step 4: Update customer journey
            journey_stats = await self._update_customer_journey(
                customer_id, current_session_id, linked_sessions
            )

            # Step 5: Store customer identity links in UserIdentityLink table
            await self._store_customer_identity_links(
                customer_id, shop_id, current_session_id, linked_sessions
            )

            # Step 6: Fire Redis stream event for customer linking backfill
            await self._fire_customer_linking_event(
                customer_id, shop_id, current_session_id, linked_sessions
            )

            result = {
                "success": True,
                "customer_id": customer_id,
                "current_session": current_session_id,
                "linked_sessions": linked_sessions,
                "total_sessions": len(linked_sessions) + 1,
                "journey_stats": journey_stats,
                "resolution_methods": self._get_resolution_summary(related_sessions),
            }

            logger.info(
                f"Identity resolution completed: {len(linked_sessions)} sessions linked"
            )
            return result

        except Exception as e:
            logger.error(f"Error in identity resolution: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _link_current_session(
        self, session_id: str, customer_id: str
    ) -> Optional[UserSession]:
        """Link current session to customer (deterministic)"""
        try:
            # Update session with customer ID
            await self.session_service.update_session(
                session_id, SessionUpdate(customer_id=customer_id)
            )

            # Update all interactions in this session
            await self._update_session_interactions(session_id, customer_id)

            return await self.session_service.get_session(session_id)

        except Exception as e:
            logger.error(f"Error linking current session: {str(e)}")
            return None

    async def _find_related_anonymous_sessions(
        self,
        current_session: UserSession,
        customer_id: str,
        shop_id: str,
        customer_data: Optional[Dict[str, Any]] = None,
    ) -> List[IdentityMatch]:
        """Find related anonymous sessions using industry-standard methods"""
        try:
            matches = []

            # Method 1: IP + User Agent matching (probabilistic)
            ip_ua_matches = await self._find_sessions_by_ip_user_agent(
                current_session, shop_id
            )
            matches.extend(ip_ua_matches)

            # Method 2: Browser session ID matching (deterministic)
            browser_matches = await self._find_sessions_by_browser_session(
                current_session, shop_id
            )
            matches.extend(browser_matches)

            # Method 3: Customer data matching (if available)
            if customer_data:
                customer_matches = await self._find_sessions_by_customer_data(
                    customer_data, shop_id
                )
                matches.extend(customer_matches)

            # Remove duplicates and sort by confidence
            unique_matches = self._deduplicate_matches(matches)
            unique_matches.sort(key=lambda x: x.confidence_score, reverse=True)

            return unique_matches

        except Exception as e:
            logger.error(f"Error finding related sessions: {str(e)}")
            return []

    async def _find_sessions_by_ip_user_agent(
        self, current_session: UserSession, shop_id: str
    ) -> List[IdentityMatch]:
        """Find sessions by IP address + User Agent (probabilistic matching)"""
        try:
            if not current_session.ip_address or not current_session.user_agent:
                return []

            async with get_session_context() as session:
                stmt = select(SAUserSession).where(
                    SAUserSession.shop_id == shop_id,
                    SAUserSession.customer_id.is_(None),
                    SAUserSession.ip_address == current_session.ip_address,
                    SAUserSession.user_agent == current_session.user_agent,
                    SAUserSession.status == SessionStatus.ACTIVE,
                    SAUserSession.expires_at > utcnow(),
                )
                result = await session.execute(stmt)
                sessions = result.scalars().all()

            matches = []
            for session in sessions:
                if session.id != current_session.id:  # Exclude current session
                    # Calculate confidence based on recency and activity
                    confidence = self._calculate_ip_ua_confidence(
                        session, current_session
                    )

                    if confidence >= self.min_confidence_threshold:
                        matches.append(
                            IdentityMatch(
                                session_id=session.id,
                                confidence_score=confidence,
                                match_type="probabilistic",
                                match_reason="IP address + User Agent match",
                            )
                        )

            return matches

        except Exception as e:
            logger.error(f"Error in IP/UA matching: {str(e)}")
            return []

    async def _find_sessions_by_browser_session(
        self, current_session: UserSession, shop_id: str
    ) -> List[IdentityMatch]:
        """Find sessions by browser session ID (deterministic matching)"""
        try:
            if not current_session.browser_session_id:
                return []

            async with get_session_context() as session:
                stmt = select(SAUserSession).where(
                    SAUserSession.shop_id == shop_id,
                    SAUserSession.customer_id.is_(None),
                    SAUserSession.browser_session_id
                    == current_session.browser_session_id,
                    SAUserSession.status == SessionStatus.ACTIVE,
                    SAUserSession.expires_at > utcnow(),
                )
                result = await session.execute(stmt)
                sessions = result.scalars().all()

            matches = []
            for session in sessions:
                if session.id != current_session.id:  # Exclude current session
                    matches.append(
                        IdentityMatch(
                            session_id=session.id,
                            confidence_score=0.95,  # High confidence for browser session
                            match_type="deterministic",
                            match_reason="Browser session ID match",
                        )
                    )

            return matches

        except Exception as e:
            logger.error(f"Error in browser session matching: {str(e)}")
            return []

    async def _find_sessions_by_customer_data(
        self, customer_data: Dict[str, Any], shop_id: str
    ) -> List[IdentityMatch]:
        """Find sessions by customer data (email, phone, etc.)"""
        try:
            matches = []

            # Look for sessions that might have customer data in metadata
            if customer_data.get("email"):
                email_matches = await self._find_sessions_by_email(
                    customer_data["email"], shop_id
                )
                matches.extend(email_matches)

            if customer_data.get("phone"):
                phone_matches = await self._find_sessions_by_phone(
                    customer_data["phone"], shop_id
                )
                matches.extend(phone_matches)

            return matches

        except Exception as e:
            logger.error(f"Error in customer data matching: {str(e)}")
            return []

    async def _find_sessions_by_email(
        self, email: str, shop_id: str
    ) -> List[IdentityMatch]:
        """Find sessions by email address (deterministic)"""
        try:
            # Look for sessions with email in metadata (simplified - no metadata field exists)
            # For now, return empty list since we don't have metadata field
            sessions = []

            matches = []
            for session in sessions:
                matches.append(
                    IdentityMatch(
                        session_id=session.id,
                        confidence_score=0.90,  # High confidence for email
                        match_type="deterministic",
                        match_reason="Email address match",
                    )
                )

            return matches

        except Exception as e:
            logger.error(f"Error in email matching: {str(e)}")
            return []

    async def _find_sessions_by_phone(
        self, phone: str, shop_id: str
    ) -> List[IdentityMatch]:
        """Find sessions by phone number (deterministic)"""
        try:
            # Look for sessions with phone in metadata (simplified - no metadata field exists)
            # For now, return empty list since we don't have metadata field
            sessions = []

            matches = []
            for session in sessions:
                matches.append(
                    IdentityMatch(
                        session_id=session.id,
                        confidence_score=0.90,  # High confidence for phone
                        match_type="deterministic",
                        match_reason="Phone number match",
                    )
                )

            return matches

        except Exception as e:
            logger.error(f"Error in phone matching: {str(e)}")
            return []

    def _calculate_ip_ua_confidence(
        self, session: Any, current_session: UserSession
    ) -> float:
        """Calculate confidence score for IP + User Agent matching"""
        try:
            confidence = 0.70  # Base confidence for IP + UA match

            # Boost confidence based on recency
            time_diff = (
                current_session.last_active - session.lastActive
            ).total_seconds()
            if time_diff < 3600:  # Within 1 hour
                confidence += 0.15
            elif time_diff < 86400:  # Within 1 day
                confidence += 0.10
            elif time_diff < 604800:  # Within 1 week
                confidence += 0.05

            # Boost confidence based on activity level
            if session.totalInteractions > 5:
                confidence += 0.10
            elif session.totalInteractions > 2:
                confidence += 0.05

            # Boost confidence based on extensions used
            if len(session.extensionsUsed) > 1:
                confidence += 0.05

            return min(confidence, 0.95)  # Cap at 95%

        except Exception as e:
            logger.error(f"Error calculating confidence: {str(e)}")
            return 0.60  # Minimum threshold

    def _deduplicate_matches(self, matches: List[IdentityMatch]) -> List[IdentityMatch]:
        """Remove duplicate matches and keep highest confidence"""
        unique_matches = {}

        for match in matches:
            if match.session_id not in unique_matches:
                unique_matches[match.session_id] = match
            elif (
                match.confidence_score
                > unique_matches[match.session_id].confidence_score
            ):
                unique_matches[match.session_id] = match

        return list(unique_matches.values())

    async def _link_related_sessions(
        self, matches: List[IdentityMatch], customer_id: str
    ) -> List[str]:
        """Link related sessions to customer"""
        linked_sessions = []

        for match in matches:
            if match.confidence_score >= self.min_confidence_threshold:
                try:
                    # Link session to customer
                    await self.session_service.update_session(
                        match.session_id,
                        self.session_service.SessionUpdate(customer_id=customer_id),
                    )

                    # Update interactions in this session
                    await self._update_session_interactions(
                        match.session_id, customer_id
                    )

                    linked_sessions.append(match.session_id)

                    logger.info(
                        f"Linked session {match.session_id} to customer {customer_id} "
                        f"(confidence: {match.confidence_score:.2f}, "
                        f"method: {match.match_type})"
                    )

                except Exception as e:
                    logger.error(f"Error linking session {match.session_id}: {str(e)}")

        return linked_sessions

    async def _update_session_interactions(self, session_id: str, customer_id: str):
        """Update all interactions in a session with customer ID"""
        try:
            async with get_session_context() as session:
                result = await session.execute(
                    select(SAUserInteraction).where(
                        SAUserInteraction.session_id == session_id
                    )
                )
                interactions = result.scalars().all()
                for it in interactions:
                    it.customer_id = customer_id
                await session.commit()

        except Exception as e:
            logger.error(f"Error updating session interactions: {str(e)}")

    async def _update_customer_journey(
        self, customer_id: str, current_session_id: str, linked_sessions: List[str]
    ) -> Dict[str, Any]:
        """Update customer journey statistics"""
        try:
            all_session_ids = [current_session_id] + linked_sessions

            # Get total interactions across all sessions
            async with get_session_context() as session:
                result = await session.execute(
                    select(SAUserInteraction).where(
                        SAUserInteraction.session_id.in_(all_session_ids)
                    )
                )
                interactions = result.scalars().all()
                total_interactions = len(interactions)
                unique_extensions = list(set(i.extension_type for i in interactions))

            return {
                "total_sessions": len(all_session_ids),
                "total_interactions": total_interactions,
                "unique_extensions": unique_extensions,
                "journey_span_days": await self._calculate_journey_span(
                    all_session_ids
                ),
            }

        except Exception as e:
            logger.error(f"Error updating customer journey: {str(e)}")
            return {}

    async def _calculate_journey_span(self, session_ids: List[str]) -> int:
        """Calculate the span of the customer journey in days"""
        try:
            if not session_ids:
                return 0

            async with get_session_context() as session:
                result = await session.execute(
                    select(SAUserSession).where(SAUserSession.id.in_(session_ids))
                )
                sessions = result.scalars().all()

            if not sessions:
                return 0

            earliest = min(s.created_at for s in sessions)
            latest = max(s.created_at for s in sessions)

            span = (latest - earliest).days
            return max(span, 1)  # Minimum 1 day

        except Exception as e:
            logger.error(f"Error calculating journey span: {str(e)}")
            return 1

    async def _fire_customer_linking_event(
        self,
        customer_id: str,
        shop_id: str,
        current_session_id: str,
        linked_sessions: List[str],
    ) -> None:
        """Publish customer linking backfill event to Kafka"""
        try:
            publisher = EventPublisher(kafka_settings.model_dump())
            await publisher.initialize()
            try:
                linking_event = {
                    "job_id": f"customer_linking_{customer_id}_{int(utcnow().timestamp())}",
                    "shop_id": shop_id,
                    "customer_id": customer_id,
                    "event_type": "customer_linking",
                    "trigger_session_id": current_session_id,
                    "linked_sessions": linked_sessions,
                    "metadata": {
                        "source": "identity_resolution_service",
                        "backfill_needed": True,
                        "linked_session_ids": linked_sessions,
                        "total_sessions_linked": len(linked_sessions) + 1,
                        "timestamp": utcnow().isoformat(),
                    },
                }

                message_id = await publisher.publish_customer_linking_event(
                    linking_event
                )

                logger.info(
                    f"Customer linking event published to Kafka: {message_id} for customer {customer_id} "
                    f"with {len(linked_sessions)} linked sessions"
                )
            finally:
                await publisher.close()
        except Exception as e:
            logger.error(f"Error publishing customer linking event to Kafka: {str(e)}")
            # Don't fail the main operation if event firing fails

    def _get_resolution_summary(self, matches: List[IdentityMatch]) -> Dict[str, Any]:
        """Get summary of resolution methods used"""
        deterministic_count = len(
            [m for m in matches if m.match_type == "deterministic"]
        )
        probabilistic_count = len(
            [m for m in matches if m.match_type == "probabilistic"]
        )

        return {
            "total_matches_found": len(matches),
            "deterministic_matches": deterministic_count,
            "probabilistic_matches": probabilistic_count,
            "average_confidence": (
                sum(m.confidence_score for m in matches) / len(matches)
                if matches
                else 0
            ),
        }

    async def _store_customer_identity_links(
        self,
        customer_id: str,
        shop_id: str,
        current_session_id: str,
        linked_sessions: List[str],
    ) -> None:
        """
        Store customer identity links in UserIdentityLink table

        Args:
            customer_id: The customer ID to link to
            shop_id: The shop ID
            current_session_id: The current session ID
            linked_sessions: List of linked session IDs
        """
        try:
            # Get all session IDs that need to be linked
            all_session_ids = [current_session_id] + linked_sessions
            async with get_session_context() as session:
                result = await session.execute(
                    select(SAUserSession).where(
                        SAUserSession.id.in_(all_session_ids),
                        SAUserSession.shop_id == shop_id,
                    )
                )
                sessions_data = result.scalars().all()

            # Create identity links for each session
            for session_data in sessions_data:
                browser_session_id = session_data.browser_session_id

                # Check if link already exists
                async with get_session_context() as session:
                    result = await session.execute(
                        select(SAUserIdentityLink).where(
                            SAUserIdentityLink.shop_id == shop_id,
                            SAUserIdentityLink.client_id == browser_session_id,
                            SAUserIdentityLink.customer_id == customer_id,
                        )
                    )
                    existing_link = result.scalar_one_or_none()

                    if not existing_link:
                        link = SAUserIdentityLink(
                            shop_id=shop_id,
                            client_id=browser_session_id,
                            customer_id=customer_id,
                        )
                        session.add(link)
                        await session.commit()
                        logger.info(
                            f"Created identity link: {browser_session_id} -> {customer_id}"
                        )
                    else:
                        logger.debug(
                            f"Identity link already exists: {browser_session_id} -> {customer_id}"
                        )

            logger.info(
                f"Stored {len(sessions_data)} customer identity links for customer {customer_id}"
            )

        except Exception as e:
            logger.error(f"Failed to store customer identity links: {str(e)}")
            raise
