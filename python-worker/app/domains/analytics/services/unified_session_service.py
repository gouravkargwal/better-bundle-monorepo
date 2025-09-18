"""
Unified Session Service for BetterBundle Analytics

Manages user sessions across all extensions with proper lifecycle management,
expiration handling, and cross-extension session sharing using Prisma.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from prisma import Json

from app.core.database import get_database
from app.domains.analytics.models.session import (
    UserSession,
    SessionCreate,
    SessionUpdate,
    SessionQuery,
    SessionStatus,
)
from app.shared.helpers.datetime_utils import utcnow
from app.core.logging.logger import get_logger

logger = get_logger(__name__)


class UnifiedSessionService:
    """Service for managing unified user sessions across all extensions"""

    def __init__(self):
        # Industry-standard session durations
        self.anonymous_session_duration = timedelta(days=30)  # E-commerce standard
        self.identified_session_duration = timedelta(days=7)  # Identified users
        self.cleanup_interval = timedelta(hours=1)
        self._last_cleanup = datetime.utcnow()

    async def get_or_create_session(
        self,
        shop_id: str,
        customer_id: Optional[str] = None,
        browser_session_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        referrer: Optional[str] = None,
    ) -> UserSession:
        """
        Get existing session or create new one for unified tracking - OPTIMIZED VERSION

        Args:
            shop_id: Shop identifier
            customer_id: Customer identifier (optional for anonymous users)
            browser_session_id: Browser session identifier
            user_agent: User agent string
            ip_address: IP address
            referrer: Referrer URL

        Returns:
            UserSession: Active session for the user
        """
        try:
            # Validate required parameters
            if not shop_id:
                raise ValueError("shop_id is required for session creation")

            db = await get_database()
            current_time = utcnow()

            # OPTIMIZATION: Single query to find or create session using upsert
            if browser_session_id:
                # Use browser_session_id as primary lookup (fastest)
                session_data = await db.usersession.find_first(
                    where={
                        "browserSessionId": browser_session_id,
                        "shopId": shop_id,
                        "status": SessionStatus.ACTIVE,
                        "expiresAt": {"gt": current_time},
                    },
                    order={"lastActive": "desc"},
                )
            elif customer_id:
                # Fallback to customer_id lookup
                session_data = await db.usersession.find_first(
                    where={
                        "customerId": customer_id,
                        "shopId": shop_id,
                        "status": SessionStatus.ACTIVE,
                        "expiresAt": {"gt": current_time},
                    },
                    order={"lastActive": "desc"},
                )
            else:
                session_data = None

            if session_data:
                # OPTIMIZATION: Update last active time in background (non-blocking)
                asyncio.create_task(
                    self._update_session_activity_background(session_data.id)
                )

                logger.info(f"Resumed existing session: {session_data.id}")
                return UserSession(
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
                )

            # OPTIMIZATION: Create new session with single database call
            # Use browser_session_id if provided, otherwise generate unified session ID
            session_id = (
                browser_session_id
                or f"unified_{shop_id}_{customer_id or 'anon'}_{int(current_time.timestamp())}"
            )
            expires_at = current_time + (
                self.identified_session_duration
                if customer_id
                else self.anonymous_session_duration
            )

            new_session_data = await db.usersession.create(
                data={
                    "id": session_id,
                    "shopId": shop_id,
                    "customerId": customer_id,
                    "browserSessionId": browser_session_id,
                    "status": SessionStatus.ACTIVE,
                    "userAgent": user_agent,
                    "ipAddress": ip_address,
                    "referrer": referrer,
                    "createdAt": current_time,
                    "lastActive": current_time,
                    "expiresAt": expires_at,
                }
            )

            logger.info(f"Created new session: {new_session_data.id}")
            return UserSession(
                id=new_session_data.id,
                shop_id=new_session_data.shopId,
                customer_id=new_session_data.customerId,
                browser_session_id=new_session_data.browserSessionId,
                status=SessionStatus(new_session_data.status),
                created_at=new_session_data.createdAt,
                last_active=new_session_data.lastActive,
                expires_at=new_session_data.expiresAt,
                user_agent=new_session_data.userAgent,
                ip_address=new_session_data.ipAddress,
                referrer=new_session_data.referrer,
            )

        except Exception as e:
            logger.error(f"Error in get_or_create_session: {str(e)}")
            raise

    async def _update_session_activity_background(self, session_id: str):
        """Update session activity in background without blocking the response"""
        try:
            db = await get_database()
            await db.usersession.update(
                where={"id": session_id}, data={"lastActive": utcnow()}
            )
        except Exception as e:
            logger.warning(f"Failed to update session activity in background: {e}")

    async def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get session by ID"""
        try:
            db = await get_database()

            # Query session from database using Prisma
            session_data = await db.usersession.find_unique(where={"id": session_id})

            if (
                session_data
                and session_data.status == SessionStatus.ACTIVE
                and session_data.expiresAt > utcnow()
            ):
                # Convert Prisma model to Pydantic model
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
                # Update last active time
                await self._update_session_activity(session_id)
                return session

            return None

        except Exception as e:
            logger.error(f"Error getting session {session_id}: {str(e)}")
            return None

    async def update_session(
        self, session_id: str, update_data: SessionUpdate
    ) -> Optional[UserSession]:
        """Update session with new data"""
        try:
            db = await get_database()

            # Prepare update data for Prisma
            update_dict = update_data.dict(exclude_unset=True)
            if "last_active" not in update_dict:
                update_dict["lastActive"] = utcnow()
            else:
                update_dict["lastActive"] = update_dict.pop("last_active")

            # Map field names to Prisma field names
            prisma_update = {}
            if "status" in update_dict:
                prisma_update["status"] = update_dict["status"]
            if "lastActive" in update_dict:
                prisma_update["lastActive"] = update_dict["lastActive"]
            if "extensions_used" in update_dict:
                prisma_update["extensionsUsed"] = Json(update_dict["extensions_used"])
            if "total_interactions" in update_dict:
                prisma_update["totalInteractions"] = update_dict["total_interactions"]

            # Update session using Prisma
            await db.usersession.update(where={"id": session_id}, data=prisma_update)

            # Return updated session
            return await self.get_session(session_id)

        except Exception as e:
            logger.error(f"Error updating session {session_id}: {str(e)}")
            return None

    async def terminate_session(self, session_id: str) -> bool:
        """Terminate a session"""
        try:
            db = await get_database()

            await db.usersession.update(
                where={"id": session_id},
                data={"status": SessionStatus.TERMINATED, "lastActive": utcnow()},
            )

            logger.info(f"Terminated session: {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error terminating session {session_id}: {str(e)}")
            return False

    async def add_extension_to_session(
        self, session_id: str, extension_type: str
    ) -> bool:
        """Add extension to session's extensions_used list"""
        try:
            session = await self.get_session(session_id)
            if not session:
                return False

            if extension_type not in session.extensions_used:
                session.extensions_used.append(extension_type)

                await self.update_session(
                    session_id, SessionUpdate(extensions_used=session.extensions_used)
                )

                logger.info(f"Added extension {extension_type} to session {session_id}")

            return True

        except Exception as e:
            logger.error(f"Error adding extension to session: {str(e)}")
            return False

    async def increment_session_interactions(self, session_id: str) -> bool:
        """Increment session's total interactions count"""
        try:
            db = await get_database()
            await db.usersession.update(
                where={"id": session_id},
                data={
                    "totalInteractions": {"increment": 1},
                },
            )
            return True

        except Exception as e:
            logger.error(f"Error incrementing session interactions: {str(e)}")
            return False

    async def query_sessions(self, query: SessionQuery) -> List[UserSession]:
        """Query sessions based on criteria"""
        try:
            db = await get_database()

            # Build where conditions for Prisma
            where_conditions = {"shopId": query.shop_id}

            if query.customer_id:
                where_conditions["customerId"] = query.customer_id

            if query.browser_session_id:
                where_conditions["browserSessionId"] = query.browser_session_id

            if query.status:
                where_conditions["status"] = query.status

            if query.created_after:
                where_conditions["createdAt"] = {"gte": query.created_after}

            if query.created_before:
                if "createdAt" in where_conditions:
                    where_conditions["createdAt"]["lte"] = query.created_before
                else:
                    where_conditions["createdAt"] = {"lte": query.created_before}

            # Execute query using Prisma
            sessions_data = await db.usersession.find_many(
                where=where_conditions, order={"createdAt": "desc"}
            )

            # Convert to Pydantic models
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
            logger.error(f"Error querying sessions: {str(e)}")
            return []

    async def _find_active_session(
        self,
        shop_id: str,
        customer_id: Optional[str] = None,
        browser_session_id: Optional[str] = None,
    ) -> Optional[UserSession]:
        """Find existing active session"""
        try:
            db = await get_database()

            # Build conditions for finding active session
            where_conditions = {
                "shopId": shop_id,
                "status": SessionStatus.ACTIVE,
                "expiresAt": {"gt": utcnow()},
            }

            # For logged-in customers, prioritize customer_id
            if customer_id:
                where_conditions["customerId"] = customer_id
            elif browser_session_id:
                where_conditions["browserSessionId"] = browser_session_id

            session_data = await db.usersession.find_first(
                where=where_conditions, order={"lastActive": "desc"}
            )

            if session_data:
                return UserSession(
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

            return None

        except Exception as e:
            logger.error(f"Error finding active session: {str(e)}")
            return None

    async def _create_new_session(
        self,
        shop_id: str,
        customer_id: Optional[str] = None,
        browser_session_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        referrer: Optional[str] = None,
    ) -> UserSession:
        """Create new session"""
        try:
            db = await get_database()

            # Validate shop exists before creating session
            shop = await db.shop.find_unique(where={"id": shop_id})
            if not shop:
                logger.error(f"Shop not found for ID: {shop_id}")
                raise ValueError(f"Shop not found for ID: {shop_id}")

            if not shop.isActive:
                logger.error(f"Shop is inactive for ID: {shop_id}")
                raise ValueError(f"Shop is inactive for ID: {shop_id}")

            # Generate unique session ID using browser_session_id if available
            import uuid

            session_id = (
                browser_session_id
                or f"unified_{shop_id}_{customer_id or 'anon'}_{int(utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"
            )

            # Calculate expiration time based on user identification status
            duration = (
                self.anonymous_session_duration
                if not customer_id
                else self.identified_session_duration
            )
            expires_at = utcnow() + duration

            # Create session using Prisma with retry logic for unique constraint failures
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    session_data = await db.usersession.create(
                        data={
                            "id": session_id,
                            "shopId": shop_id,
                            "customerId": customer_id,
                            "browserSessionId": browser_session_id
                            or f"browser_{uuid.uuid4().hex[:8]}",
                            "status": SessionStatus.ACTIVE,
                            "createdAt": utcnow(),
                            "lastActive": utcnow(),
                            "expiresAt": expires_at,
                            "userAgent": user_agent,
                            "ipAddress": ip_address,
                            "referrer": referrer,
                            "extensionsUsed": [],
                            "totalInteractions": 0,
                        }
                    )
                    break  # Success, exit retry loop
                except Exception as e:
                    if (
                        "Unique constraint failed" in str(e)
                        and attempt < max_retries - 1
                    ):
                        # Generate new session ID and retry
                        session_id = f"unified_{shop_id}_{customer_id or 'anon'}_{int(utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"
                        logger.warning(
                            f"Session ID collision, retrying with new ID: {session_id}"
                        )
                        continue
                    else:
                        raise e

            # Convert to Pydantic model
            return UserSession(
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

        except Exception as e:
            logger.error(f"Error creating new session: {str(e)}")
            raise

    async def _update_session_activity(self, session_id: str) -> None:
        """Update session's last active time"""
        try:
            db = await get_database()

            await db.usersession.update(
                where={"id": session_id}, data={"lastActive": utcnow()}
            )

        except Exception as e:
            logger.error(f"Error updating session activity: {str(e)}")

    async def _cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions periodically"""
        try:
            # Only cleanup every hour to avoid excessive database operations
            if utcnow() - self._last_cleanup < self.cleanup_interval:
                return

            db = await get_database()

            # Mark expired sessions as expired
            await db.usersession.update_many(
                where={"status": SessionStatus.ACTIVE, "expiresAt": {"lte": utcnow()}},
                data={"status": SessionStatus.EXPIRED},
            )

            # Delete very old sessions (older than 30 days)
            cutoff_date = utcnow() - timedelta(days=30)
            await db.usersession.delete_many(where={"createdAt": {"lt": cutoff_date}})

            self._last_cleanup = utcnow()

            logger.info("Cleaned up expired sessions")

        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {str(e)}")
