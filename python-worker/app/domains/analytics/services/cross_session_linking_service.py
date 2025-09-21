"""
Cross-Session Linking Service

Industry-standard service for linking customer sessions across time periods
using privacy-compliant methods and industry best practices.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from app.core.database import get_database
from app.domains.analytics.models.session import UserSession, SessionStatus
from app.domains.analytics.services.unified_session_service import UnifiedSessionService
from app.domains.analytics.services.customer_identity_resolution_service import (
    CustomerIdentityResolutionService,
)
from app.shared.helpers.datetime_utils import utcnow
from app.core.logging.logger import get_logger

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
        self.identity_resolution_service = CustomerIdentityResolutionService()

        # Industry-standard linking parameters
        self.max_journey_days = 30  # Maximum journey span to consider
        self.min_confidence_threshold = 0.60  # Minimum confidence for linking
        self.ip_ua_confidence_base = 0.70  # Base confidence for IP + UA matching

    async def link_customer_sessions(
        self, customer_id: str, shop_id: str, trigger_session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Link all sessions for a customer using industry-standard methods

        This is the main method that implements cross-session linking
        for complete customer journey reconstruction.

        Args:
            customer_id: Customer identifier
            shop_id: Shop identifier
            trigger_session_id: Optional session that triggered the linking

        Returns:
            Dict with linking results
        """
        try:
            logger.info(f"Starting cross-session linking for customer {customer_id}")

            # Step 1: Get all existing sessions for this customer
            existing_sessions = await self._get_customer_sessions(customer_id, shop_id)

            if not existing_sessions:
                return {"success": False, "error": "No sessions found for customer"}

            # Step 2: Find unlinked anonymous sessions that might belong to this customer
            potential_sessions = await self._find_potential_sessions(
                existing_sessions, shop_id
            )

            # Step 3: Calculate confidence scores for potential matches
            scored_sessions = await self._score_potential_sessions(
                existing_sessions, potential_sessions
            )

            # Step 4: Link high-confidence matches
            linked_sessions = await self._link_high_confidence_sessions(
                scored_sessions, customer_id
            )

            # Step 5: Create session links for tracking
            session_links = await self._create_session_links(
                existing_sessions, linked_sessions, customer_id
            )

            # Step 6: Generate customer journey summary
            journey_summary = await self._generate_journey_summary(
                customer_id, existing_sessions + linked_sessions
            )

            result = {
                "success": True,
                "customer_id": customer_id,
                "existing_sessions": len(existing_sessions),
                "linked_sessions": len(linked_sessions),
                "total_sessions": len(existing_sessions) + len(linked_sessions),
                "session_links": len(session_links),
                "journey_summary": journey_summary,
                "linking_methods": self._get_linking_methods_summary(scored_sessions),
            }

            logger.info(
                f"Cross-session linking completed: {len(linked_sessions)} sessions linked"
            )
            return result

        except Exception as e:
            logger.error(f"Error in cross-session linking: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _get_customer_sessions(
        self, customer_id: str, shop_id: str
    ) -> List[UserSession]:
        """Get all existing sessions for a customer"""
        try:
            db = await get_database()

            sessions_data = await db.usersession.find_many(
                where={
                    "customerId": customer_id,
                    "shopId": shop_id,
                    "status": "active",  # Use string value instead of enum
                },
                order={"createdAt": "asc"},
            )

            sessions = []
            for session_data in sessions_data:
                session = UserSession(
                    id=session_data.id,
                    shop_id=session_data.shopId,
                    customer_id=session_data.customerId,
                    browser_session_id=session_data.browserSessionId,
                    status=SessionStatus(session_data.status),
                    created_at=session_data.createdAt,
                    last_active=session_data.lastActive,
                    expires_at=session_data.expiresAt,
                    user_agent=session_data.userAgent,
                    ip_address=session_data.ipAddress,
                    referrer=session_data.referrer,
                    extensions_used=session_data.extensionsUsed,
                    total_interactions=session_data.totalInteractions,
                )
                sessions.append(session)

            return sessions

        except Exception as e:
            logger.error(f"Error getting customer sessions: {str(e)}")
            return []

    async def _find_potential_sessions(
        self, existing_sessions: List[UserSession], shop_id: str
    ) -> List[UserSession]:
        """Find anonymous sessions that might belong to this customer"""
        try:
            db = await get_database()

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

            # Find anonymous sessions with matching identifiers
            where_conditions = {
                "shopId": shop_id,
                "customerId": None,  # Only anonymous sessions
                "status": "active",  # Use string value instead of enum
                "expiresAt": {"gt": utcnow()},
            }

            # Build OR conditions for matching
            or_conditions = []

            if ip_addresses:
                or_conditions.append({"ipAddress": {"in": ip_addresses}})

            if user_agents:
                or_conditions.append({"userAgent": {"in": user_agents}})

            if browser_session_ids:
                or_conditions.append({"browserSessionId": {"in": browser_session_ids}})

            if not or_conditions:
                return []

            # Find sessions matching any of the conditions
            sessions_data = await db.usersession.find_many(
                where={**where_conditions, "OR": or_conditions},
                order={"createdAt": "asc"},
            )

            # Convert to UserSession objects
            potential_sessions = []
            existing_session_ids = {s.id for s in existing_sessions}

            for session_data in sessions_data:
                if (
                    session_data.id not in existing_session_ids
                ):  # Exclude existing sessions
                    session = UserSession(
                        id=session_data.id,
                        shop_id=session_data.shopId,
                        customer_id=session_data.customerId,
                        browser_session_id=session_data.browserSessionId,
                        status=SessionStatus(session_data.status),
                        created_at=session_data.createdAt,
                        last_active=session_data.lastActive,
                        expires_at=session_data.expiresAt,
                        user_agent=session_data.userAgent,
                        ip_address=session_data.ipAddress,
                        referrer=session_data.referrer,
                        extensions_used=session_data.extensionsUsed,
                        total_interactions=session_data.totalInteractions,
                    )
                    potential_sessions.append(session)

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
                    self.session_service.SessionUpdate(customer_id=customer_id),
                )

                # Update interactions in this session
                await self._update_session_interactions(session.id, customer_id)

                linked_sessions.append(session)

                logger.info(
                    f"Linked session {session.id} to customer {customer_id} "
                    f"(confidence: {confidence:.2f}, method: {match_type})"
                )

            except Exception as e:
                logger.error(f"Error linking session {session.id}: {str(e)}")

        return linked_sessions

    async def _update_session_interactions(self, session_id: str, customer_id: str):
        """Update all interactions in a session with customer ID"""
        try:
            db = await get_database()

            await db.userinteraction.update_many(
                where={"sessionId": session_id}, data={"customerId": customer_id}
            )

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
