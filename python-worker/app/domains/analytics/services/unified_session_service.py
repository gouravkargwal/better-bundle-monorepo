"""
Unified Session Service for BetterBundle Analytics

Manages user sessions across all extensions with proper lifecycle management,
expiration handling, and cross-extension session sharing using Prisma.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from app.core.database.session import get_transaction_context
from app.core.database.models.user_session import UserSession as UserSessionModel
from app.core.database.models.shop import Shop
from sqlalchemy import select, and_, or_, desc, func, update
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

            current_time = utcnow()

            async with get_transaction_context() as session:
                # OPTIMIZATION: Single query to find or create session using upsert
                if browser_session_id:
                    # Use browser_session_id as primary lookup (fastest)
                    stmt = (
                        select(UserSessionModel)
                        .where(
                            and_(
                                UserSessionModel.browser_session_id
                                == browser_session_id,
                                UserSessionModel.shop_id == shop_id,
                                UserSessionModel.status == SessionStatus.ACTIVE,
                                UserSessionModel.expires_at > current_time,
                            )
                        )
                        .order_by(desc(UserSessionModel.last_active))
                    )

                    result = await session.execute(stmt)
                    session_data = result.scalar_one_or_none()
                elif customer_id:
                    # Fallback to customer_id lookup
                    stmt = (
                        select(UserSessionModel)
                        .where(
                            and_(
                                UserSessionModel.customer_id == customer_id,
                                UserSessionModel.shop_id == shop_id,
                                UserSessionModel.status == SessionStatus.ACTIVE,
                                UserSessionModel.expires_at > current_time,
                            )
                        )
                        .order_by(desc(UserSessionModel.last_active))
                    )

                    result = await session.execute(stmt)
                    session_data = result.scalar_one_or_none()
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
                        shop_id=session_data.shop_id,
                        customer_id=session_data.customer_id,
                        browser_session_id=session_data.browser_session_id,
                        status=SessionStatus(session_data.status),
                        created_at=session_data.created_at,
                        last_active=session_data.last_active,
                        expires_at=session_data.expires_at,
                        user_agent=session_data.user_agent,
                        ip_address=session_data.ip_address,
                        referrer=session_data.referrer,
                    )

                # OPTIMIZATION: Create new session with single database call
                # Use browser_session_id if provided, otherwise generate unique UUID
                session_id = browser_session_id or str(uuid.uuid4())
                expires_at = current_time + (
                    self.identified_session_duration
                    if customer_id
                    else self.anonymous_session_duration
                )

                # Validate shop exists before creating session
                shop_result = await session.execute(
                    select(Shop).where(Shop.id == shop_id)
                )
                shop = shop_result.scalar_one_or_none()

                if not shop:
                    logger.error(f"Shop not found for ID: {shop_id}")
                    raise ValueError(f"Shop not found for ID: {shop_id}")

                if not shop.is_active:
                    logger.error(f"Shop is inactive for ID: {shop_id}")
                    raise ValueError(f"Shop is inactive for ID: {shop_id}")

                # Use retry mechanism with exponential backoff for race conditions
                max_retries = 3
                retry_delay = 0.1  # Start with 100ms delay

                for attempt in range(max_retries):
                    try:
                        # Generate a new UUID for each retry attempt to avoid collisions
                        if attempt > 0:
                            session_id = str(uuid.uuid4())
                            # Add exponential backoff delay
                            await asyncio.sleep(retry_delay * (2**attempt))

                        new_session_model = UserSessionModel(
                            id=session_id,
                            shop_id=shop_id,
                            customer_id=customer_id,
                            browser_session_id=browser_session_id,
                            status=SessionStatus.ACTIVE,
                            user_agent=user_agent,
                            ip_address=ip_address,
                            referrer=referrer,
                            created_at=current_time,
                            last_active=current_time,
                            expires_at=expires_at,
                            extensions_used=[],
                            total_interactions=0,
                        )

                        session.add(new_session_model)
                        await session.commit()
                        await session.refresh(new_session_model)
                        break  # Success, exit retry loop

                    except Exception as e:
                        # CRITICAL: Rollback the failed transaction first
                        await session.rollback()

                        # Handle race condition - if session creation fails due to unique constraint,
                        # try to find the existing session that was created by another request
                        if (
                            "Unique constraint failed" in str(e)
                            or "UniqueViolationError" in str(e)
                            or "duplicate key value violates unique constraint"
                            in str(e)
                        ):
                            logger.warning(
                                f"Session creation race condition detected, attempting to find existing session: {session_id}"
                            )

                            # Start a new transaction to find the existing session
                            try:
                                existing_stmt = select(UserSessionModel).where(
                                    UserSessionModel.id == session_id
                                )
                                existing_result = await session.execute(existing_stmt)
                                existing_session = existing_result.scalar_one_or_none()

                                if existing_session:
                                    logger.info(
                                        f"Found existing session created by concurrent request: {existing_session.id}"
                                    )
                                    return UserSession(
                                        id=existing_session.id,
                                        shop_id=existing_session.shop_id,
                                        customer_id=existing_session.customer_id,
                                        browser_session_id=existing_session.browser_session_id,
                                        status=SessionStatus(existing_session.status),
                                        created_at=existing_session.created_at,
                                        last_active=existing_session.last_active,
                                        expires_at=existing_session.expires_at,
                                        user_agent=existing_session.user_agent,
                                        ip_address=existing_session.ip_address,
                                        referrer=existing_session.referrer,
                                    )
                                else:
                                    # If we can't find the session, try to find any active session for this user
                                    fallback_session = await self._find_active_session(
                                        shop_id, customer_id, browser_session_id
                                    )
                                    if fallback_session:
                                        logger.info(
                                            f"Found fallback active session: {fallback_session.id}"
                                        )
                                        return fallback_session
                                    else:
                                        # If no session exists, re-raise the original error
                                        raise e
                            except Exception as fallback_error:
                                logger.error(
                                    f"Error in race condition handling: {fallback_error}"
                                )
                                raise e
                        else:
                            # Re-raise non-unique constraint errors
                            raise e

                logger.info(f"Created new session: {new_session_model.id}")
                return UserSession(
                    id=new_session_model.id,
                    shop_id=new_session_model.shop_id,
                    customer_id=new_session_model.customer_id,
                    browser_session_id=new_session_model.browser_session_id,
                    status=SessionStatus(new_session_model.status),
                    created_at=new_session_model.created_at,
                    last_active=new_session_model.last_active,
                    expires_at=new_session_model.expires_at,
                    user_agent=new_session_model.user_agent,
                    ip_address=new_session_model.ip_address,
                    referrer=new_session_model.referrer,
                )

        except Exception as e:
            logger.error(f"Error in get_or_create_session: {str(e)}")
            raise

    async def _update_session_activity_background(self, session_id: str):
        """Update session activity in background without blocking the response"""
        try:
            async with get_transaction_context() as session:
                stmt = (
                    update(UserSessionModel)
                    .where(UserSessionModel.id == session_id)
                    .values(last_active=utcnow())
                )
                await session.execute(stmt)
                await session.commit()
        except Exception as e:
            logger.warning(f"Failed to update session activity in background: {e}")

    async def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get session by ID"""
        try:
            async with get_transaction_context() as session:
                # Query session from database using SQLAlchemy
                stmt = select(UserSessionModel).where(UserSessionModel.id == session_id)
                result = await session.execute(stmt)
                session_data = result.scalar_one_or_none()

                if (
                    session_data
                    and session_data.status == SessionStatus.ACTIVE
                    and session_data.expires_at > utcnow()
                ):
                    # Convert SQLAlchemy model to Pydantic model
                    user_session = UserSession(
                        id=session_data.id,
                        shop_id=session_data.shop_id,
                        customer_id=session_data.customer_id,
                        browser_session_id=session_data.browser_session_id,
                        status=SessionStatus(session_data.status),
                        created_at=session_data.created_at,
                        last_active=session_data.last_active,
                        expires_at=session_data.expires_at,
                        user_agent=session_data.user_agent,
                        ip_address=session_data.ip_address,
                        referrer=session_data.referrer,
                        extensions_used=session_data.extensions_used,
                        total_interactions=session_data.total_interactions,
                    )
                    # Update last active time
                    await self._update_session_activity(session_id)
                    return user_session

                return None

        except Exception as e:
            logger.error(f"Error getting session {session_id}: {str(e)}")
            return None

    async def update_session(
        self, session_id: str, update_data: SessionUpdate
    ) -> Optional[UserSession]:
        """Update session with new data"""
        try:
            async with get_transaction_context() as session:
                # Prepare update data for SQLAlchemy
                update_dict = update_data.dict(exclude_unset=True)
                if "last_active" not in update_dict:
                    update_dict["last_active"] = utcnow()

                # Map field names to SQLAlchemy field names
                sqlalchemy_update = {}
                if "customer_id" in update_dict:
                    sqlalchemy_update["customer_id"] = update_dict["customer_id"]
                if "status" in update_dict:
                    sqlalchemy_update["status"] = update_dict["status"]
                if "last_active" in update_dict:
                    sqlalchemy_update["last_active"] = update_dict["last_active"]
                if "extensions_used" in update_dict:
                    sqlalchemy_update["extensions_used"] = update_dict[
                        "extensions_used"
                    ]
                if "total_interactions" in update_dict:
                    sqlalchemy_update["total_interactions"] = update_dict[
                        "total_interactions"
                    ]

                # Update session using SQLAlchemy
                stmt = (
                    update(UserSessionModel)
                    .where(UserSessionModel.id == session_id)
                    .values(**sqlalchemy_update)
                )
                await session.execute(stmt)
                await session.commit()

                # Return updated session
                return await self.get_session(session_id)

        except Exception as e:
            logger.error(f"Error updating session {session_id}: {str(e)}")
            return None

    async def terminate_session(self, session_id: str) -> bool:
        """Terminate a session"""
        try:
            async with get_transaction_context() as session:
                stmt = (
                    update(UserSessionModel)
                    .where(UserSessionModel.id == session_id)
                    .values(status=SessionStatus.TERMINATED, last_active=utcnow())
                )
                await session.execute(stmt)
                await session.commit()

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
            async with get_transaction_context() as session:
                # Get current total_interactions value
                stmt = select(UserSessionModel.total_interactions).where(
                    UserSessionModel.id == session_id
                )
                result = await session.execute(stmt)
                current_count = result.scalar_one_or_none()

                if current_count is not None:
                    # Increment the count
                    update_stmt = (
                        update(UserSessionModel)
                        .where(UserSessionModel.id == session_id)
                        .values(total_interactions=current_count + 1)
                    )
                    await session.execute(update_stmt)
                    await session.commit()
                    return True
                else:
                    logger.warning(
                        f"Session {session_id} not found for interaction increment"
                    )
                    return False

        except Exception as e:
            logger.error(f"Error incrementing session interactions: {str(e)}")
            return False

    async def query_sessions(self, query: SessionQuery) -> List[UserSession]:
        """Query sessions based on criteria"""
        try:
            async with get_transaction_context() as session:
                # Build where conditions for SQLAlchemy
                where_conditions = [UserSessionModel.shop_id == query.shop_id]

                if query.customer_id:
                    where_conditions.append(
                        UserSessionModel.customer_id == query.customer_id
                    )

                if query.browser_session_id:
                    where_conditions.append(
                        UserSessionModel.browser_session_id == query.browser_session_id
                    )

                if query.status:
                    where_conditions.append(UserSessionModel.status == query.status)

                if query.created_after:
                    where_conditions.append(
                        UserSessionModel.created_at >= query.created_after
                    )

                if query.created_before:
                    where_conditions.append(
                        UserSessionModel.created_at <= query.created_before
                    )

                # Execute query using SQLAlchemy
                stmt = (
                    select(UserSessionModel)
                    .where(and_(*where_conditions))
                    .order_by(desc(UserSessionModel.created_at))
                )

                result = await session.execute(stmt)
                sessions_data = result.scalars().all()

                # Convert to Pydantic models
                sessions = []
                for session_data in sessions_data:
                    session = UserSession(
                        id=session_data.id,
                        shop_id=session_data.shop_id,
                        customer_id=session_data.customer_id,
                        browser_session_id=session_data.browser_session_id,
                        status=SessionStatus(session_data.status),
                        created_at=session_data.created_at,
                        last_active=session_data.last_active,
                        expires_at=session_data.expires_at,
                        user_agent=session_data.user_agent,
                        ip_address=session_data.ip_address,
                        referrer=session_data.referrer,
                        extensions_used=session_data.extensions_used,
                        total_interactions=session_data.total_interactions,
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
            async with get_transaction_context() as session:
                # Build conditions for finding active session
                where_conditions = [
                    UserSessionModel.shop_id == shop_id,
                    UserSessionModel.status == SessionStatus.ACTIVE,
                    UserSessionModel.expires_at > utcnow(),
                ]

                # For logged-in customers, prioritize customer_id
                if customer_id:
                    where_conditions.append(UserSessionModel.customer_id == customer_id)
                elif browser_session_id:
                    where_conditions.append(
                        UserSessionModel.browser_session_id == browser_session_id
                    )

                stmt = (
                    select(UserSessionModel)
                    .where(and_(*where_conditions))
                    .order_by(desc(UserSessionModel.last_active))
                )

                result = await session.execute(stmt)
                session_data = result.scalar_one_or_none()

                if session_data:
                    return UserSession(
                        id=session_data.id,
                        shop_id=session_data.shop_id,
                        customer_id=session_data.customer_id,
                        browser_session_id=session_data.browser_session_id,
                        status=SessionStatus(session_data.status),
                        created_at=session_data.created_at,
                        last_active=session_data.last_active,
                        expires_at=session_data.expires_at,
                        user_agent=session_data.user_agent,
                        ip_address=session_data.ip_address,
                        referrer=session_data.referrer,
                        extensions_used=session_data.extensions_used,
                        total_interactions=session_data.total_interactions,
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
            async with get_transaction_context() as session:
                # Validate shop exists before creating session
                shop_result = await session.execute(
                    select(Shop).where(Shop.id == shop_id)
                )
                shop = shop_result.scalar_one_or_none()

                if not shop:
                    logger.error(f"Shop not found for ID: {shop_id}")
                    raise ValueError(f"Shop not found for ID: {shop_id}")

                if not shop.is_active:
                    logger.error(f"Shop is inactive for ID: {shop_id}")
                    raise ValueError(f"Shop is inactive for ID: {shop_id}")

                # Generate unique session ID using browser_session_id if available
                session_id = browser_session_id or str(uuid.uuid4())

                # Calculate expiration time based on user identification status
                duration = (
                    self.anonymous_session_duration
                    if not customer_id
                    else self.identified_session_duration
                )
                expires_at = utcnow() + duration

                # Create session using SQLAlchemy with retry logic for unique constraint failures
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        session_model = UserSessionModel(
                            id=session_id,
                            shop_id=shop_id,
                            customer_id=customer_id,
                            browser_session_id=browser_session_id
                            or f"browser_{uuid.uuid4().hex[:8]}",
                            status=SessionStatus.ACTIVE,
                            created_at=utcnow(),
                            last_active=utcnow(),
                            expires_at=expires_at,
                            user_agent=user_agent,
                            ip_address=ip_address,
                            referrer=referrer,
                            extensions_used=[],
                            total_interactions=0,
                        )

                        session.add(session_model)
                        await session.commit()
                        await session.refresh(session_model)
                        break  # Success, exit retry loop
                    except Exception as e:
                        if (
                            "Unique constraint failed" in str(e)
                            and attempt < max_retries - 1
                        ):
                            # Generate new UUID and retry
                            session_id = str(uuid.uuid4())
                            logger.warning(
                                f"Session ID collision, retrying with new UUID: {session_id}"
                            )
                            continue
                        else:
                            raise e

                # Convert to Pydantic model
                return UserSession(
                    id=session_model.id,
                    shop_id=session_model.shop_id,
                    customer_id=session_model.customer_id,
                    browser_session_id=session_model.browser_session_id,
                    status=SessionStatus(session_model.status),
                    created_at=session_model.created_at,
                    last_active=session_model.last_active,
                    expires_at=session_model.expires_at,
                    user_agent=session_model.user_agent,
                    ip_address=session_model.ip_address,
                    referrer=session_model.referrer,
                    extensions_used=session_model.extensions_used,
                    total_interactions=session_model.total_interactions,
                )

        except Exception as e:
            logger.error(f"Error creating new session: {str(e)}")
            raise

    async def _update_session_activity(self, session_id: str) -> None:
        """Update session's last active time"""
        try:
            async with get_transaction_context() as session:
                stmt = (
                    update(UserSessionModel)
                    .where(UserSessionModel.id == session_id)
                    .values(last_active=utcnow())
                )
                await session.execute(stmt)
                await session.commit()

        except Exception as e:
            logger.error(f"Error updating session activity: {str(e)}")

    async def _cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions periodically"""
        try:
            # Only cleanup every hour to avoid excessive database operations
            if utcnow() - self._last_cleanup < self.cleanup_interval:
                return

            async with get_transaction_context() as session:
                # Mark expired sessions as expired
                stmt = (
                    update(UserSessionModel)
                    .where(
                        and_(
                            UserSessionModel.status == SessionStatus.ACTIVE,
                            UserSessionModel.expires_at <= utcnow(),
                        )
                    )
                    .values(status=SessionStatus.EXPIRED)
                )
                await session.execute(stmt)

                # Delete very old sessions (older than 30 days)
                cutoff_date = utcnow() - timedelta(days=30)
                delete_stmt = select(UserSessionModel).where(
                    UserSessionModel.created_at < cutoff_date
                )
                result = await session.execute(delete_stmt)
                old_sessions = result.scalars().all()

                for old_session in old_sessions:
                    await session.delete(old_session)

                await session.commit()

            self._last_cleanup = utcnow()

            logger.info("Cleaned up expired sessions")

        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {str(e)}")
