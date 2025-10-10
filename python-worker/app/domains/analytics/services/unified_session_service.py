"""
Unified Session Service for BetterBundle Analytics

This service manages user sessions across all extensions with proper lifecycle management,
expiration handling, and cross-extension session sharing using SQLAlchemy.

Key Features:
- UUID-based session IDs to prevent collisions
- Race condition handling with retry logic
- Automatic session cleanup
- Cross-extension session sharing
- Proper transaction management
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from app.shared.helpers import now_utc

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
from app.core.logging.logger import get_logger

logger = get_logger(__name__)


class UnifiedSessionService:
    """
    Service for managing unified user sessions across all extensions.

    This service handles:
    - Session creation and retrieval
    - Race condition handling
    - Session lifecycle management
    - Cross-extension session sharing
    """

    # ============================================================================
    # CONFIGURATION & INITIALIZATION
    # ============================================================================

    def __init__(self):
        """Initialize the session service with industry-standard durations."""
        # Session durations based on e-commerce best practices
        self.anonymous_session_duration = timedelta(days=30)  # Anonymous users
        self.identified_session_duration = timedelta(days=7)  # Logged-in users

        # Cleanup settings
        self.cleanup_interval = timedelta(hours=1)
        self._last_cleanup = now_utc()

    # ============================================================================
    # MAIN SESSION OPERATIONS
    # ============================================================================

    async def get_or_create_session(
        self,
        shop_id: str,
        customer_id: Optional[str] = None,
        browser_session_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        referrer: Optional[str] = None,
        client_id: Optional[str] = None,  # ✅ NEW parameter
    ) -> UserSession:
        """
        Get existing session or create new one for unified tracking.

        ✅ SCENARIO 18: Cross-Device Attribution
        ✅ SCENARIO 20: Session Expiration During Journey

        Story: Sarah sees a recommendation, but her session expires while browsing.
        She starts a new session and completes the purchase. We need to link
        the expired session to the new one for proper attribution.

        Story: Sarah browses on her phone, sees a recommendation, then switches
        to her laptop to complete the purchase. We need to link these sessions
        to give proper attribution to the mobile recommendation.

        This is the main entry point for session management. It handles:
        - Finding existing active sessions
        - Cross-device session linking via client_id
        - Creating new sessions with UUID-based IDs
        - Race condition handling with retry logic
        - Proper transaction management

        Args:
            shop_id: Shop identifier (required)
            customer_id: Customer identifier (optional for anonymous users)
            browser_session_id: Browser session identifier
            client_id: Shopify client ID for device tracking (optional)  # ✅ NEW
            user_agent: User agent string
            ip_address: IP address
            referrer: Referrer URL

        Returns:
            UserSession: Active session for the user

        Raises:
            ValueError: If shop_id is not provided or shop is not found/inactive
        """
        try:
            # Validate required parameters
            if not shop_id:
                raise ValueError("shop_id is required for session creation")

            current_time = now_utc()

            async with get_transaction_context() as session:
                # ✅ SCENARIO 18: Cross-Device Session Linking
                # Step 1: Try to find existing active session
                existing_session = await self._find_existing_session(
                    session, shop_id, customer_id, browser_session_id, current_time
                )

                # ✅ SCENARIO 18: Cross-device linking via client_id
                if not existing_session and client_id:
                    existing_session = await self._find_cross_device_session(
                        session, shop_id, client_id, current_time
                    )
                    if existing_session:
                        logger.info(
                            f"🔗 Cross-device session found: {existing_session.id} via client_id {client_id}"
                        )

                # ✅ SCENARIO 20: Check for expired sessions that can be linked
                if not existing_session:
                    existing_session = await self._find_expired_session_for_linking(
                        session, shop_id, customer_id, browser_session_id, current_time
                    )
                    if existing_session:
                        logger.info(
                            f"🔄 Expired session found for linking: {existing_session.id}"
                        )

                if existing_session:
                    # Update activity in background and return existing session
                    # ✅ NEW: Update client_id if provided and not already set
                    if client_id and not existing_session.client_id:
                        try:
                            existing_session.client_id = client_id
                            await session.commit()
                            await session.refresh(existing_session)
                        except Exception as e:
                            logger.warning(
                                f"Failed to update client_id for session {existing_session.id}: {e}"
                            )
                            # Continue with existing session even if client_id update fails

                    asyncio.create_task(
                        self._update_session_activity_background(existing_session.id)
                    )
                    return self._convert_to_user_session(existing_session)

                # Step 2: Create new session with race condition handling
                return await self._create_new_session_with_retry(
                    session,
                    shop_id,
                    customer_id,
                    browser_session_id,
                    user_agent,
                    ip_address,
                    referrer,
                    current_time,
                    client_id,  # ✅ NEW: Pass client_id
                )

        except Exception as e:
            logger.error(f"Error in get_or_create_session: {str(e)}")
            raise

    async def get_session(self, session_id: str) -> Optional[UserSession]:
        """
        Get session by ID.

        Args:
            session_id: The session ID to look up

        Returns:
            UserSession if found and active, None otherwise
        """
        try:
            async with get_transaction_context() as session:
                stmt = select(UserSessionModel).where(UserSessionModel.id == session_id)
                result = await session.execute(stmt)
                session_data = result.scalar_one_or_none()

                if (
                    session_data
                    and session_data.status == SessionStatus.ACTIVE
                    and session_data.expires_at > now_utc()
                ):
                    # Convert to Pydantic model and update activity
                    user_session = self._convert_to_user_session(session_data)
                    await self._update_session_activity(session_id)
                    return user_session

                return None

        except Exception as e:
            logger.error(f"Error getting session {session_id}: {str(e)}")
            return None

    async def update_session(
        self, session_id: str, update_data: SessionUpdate
    ) -> Optional[UserSession]:
        """
        Update session with new data.

        Args:
            session_id: The session ID to update
            update_data: The data to update

        Returns:
            Updated UserSession if successful, None if session not found
        """
        try:
            async with get_transaction_context() as session:
                # Get current session data first
                current_session_query = select(UserSessionModel).where(
                    UserSessionModel.id == session_id
                )
                current_session_result = await session.execute(current_session_query)
                current_session = current_session_result.scalar_one_or_none()

                if not current_session:
                    logger.warning(f"Session {session_id} not found for update")
                    return None

                # Prepare update data
                update_dict = update_data.dict(exclude_unset=True)
                if "last_active" not in update_dict:
                    update_dict["last_active"] = now_utc()

                # Check for constraint violations if updating customer_id
                if "customer_id" in update_dict and update_dict["customer_id"]:
                    new_customer_id = update_dict["customer_id"]
                    if new_customer_id != current_session.customer_id:
                        # Check if this would cause a constraint violation
                        existing_query = select(UserSessionModel).where(
                            and_(
                                UserSessionModel.shop_id == current_session.shop_id,
                                UserSessionModel.customer_id == new_customer_id,
                                UserSessionModel.browser_session_id
                                == current_session.browser_session_id,
                                UserSessionModel.id
                                != session_id,  # Exclude current session
                            )
                        )
                        existing_result = await session.execute(existing_query)
                        existing_session = existing_result.scalar_one_or_none()

                        if existing_session:
                            logger.warning(
                                f"Cannot update session {session_id} - would cause constraint violation with session {existing_session.id}"
                            )
                            return None

                # Map to SQLAlchemy fields
                sqlalchemy_update = {}
                field_mapping = {
                    "customer_id": "customer_id",
                    "client_id": "client_id",  # ✅ NEW: Add client_id mapping
                    "status": "status",
                    "last_active": "last_active",
                    "extensions_used": "extensions_used",
                    "total_interactions": "total_interactions",
                }

                for pydantic_field, sqlalchemy_field in field_mapping.items():
                    if pydantic_field in update_dict:
                        sqlalchemy_update[sqlalchemy_field] = update_dict[
                            pydantic_field
                        ]

                # Execute update
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

    # ============================================================================
    # SESSION LIFECYCLE MANAGEMENT
    # ============================================================================

    async def terminate_session(self, session_id: str) -> bool:
        """
        Terminate a session.

        Args:
            session_id: The session ID to terminate

        Returns:
            True if successful, False otherwise
        """
        try:
            async with get_transaction_context() as session:
                stmt = (
                    update(UserSessionModel)
                    .where(UserSessionModel.id == session_id)
                    .values(status=SessionStatus.TERMINATED, last_active=now_utc())
                )
                await session.execute(stmt)
                await session.commit()

                return True

        except Exception as e:
            logger.error(f"Error terminating session {session_id}: {str(e)}")
            return False

    async def add_extension_to_session(
        self, session_id: str, extension_type: str
    ) -> bool:
        """
        Add extension to session's extensions_used list.

        Args:
            session_id: The session ID
            extension_type: The extension type to add

        Returns:
            True if successful, False otherwise
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                return False

            if extension_type not in session.extensions_used:
                session.extensions_used.append(extension_type)

                await self.update_session(
                    session_id, SessionUpdate(extensions_used=session.extensions_used)
                )

            return True

        except Exception as e:
            logger.error(f"Error adding extension to session: {str(e)}")
            return False

    async def increment_session_interactions(self, session_id: str) -> bool:
        """
        Increment session's total interactions count.

        Args:
            session_id: The session ID to update

        Returns:
            True if successful, False otherwise
        """
        try:
            async with get_transaction_context() as session:
                # Get current count
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

    # ============================================================================
    # QUERY OPERATIONS
    # ============================================================================

    async def query_sessions(self, query: SessionQuery) -> List[UserSession]:
        """
        Query sessions based on criteria.

        Args:
            query: The query criteria

        Returns:
            List of matching UserSession objects
        """
        try:
            async with get_transaction_context() as session:
                # Build where conditions
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

                # Execute query
                stmt = (
                    select(UserSessionModel)
                    .where(and_(*where_conditions))
                    .order_by(desc(UserSessionModel.created_at))
                )

                result = await session.execute(stmt)
                sessions_data = result.scalars().all()

                # Convert to Pydantic models
                return [
                    self._convert_to_user_session(session_data)
                    for session_data in sessions_data
                ]

        except Exception as e:
            logger.error(f"Error querying sessions: {str(e)}")
            return []

    # ============================================================================
    # PRIVATE HELPER METHODS
    # ============================================================================

    async def _find_cross_device_session(
        self, session, shop_id: str, client_id: str, current_time: datetime
    ) -> Optional[UserSessionModel]:
        """
        ✅ SCENARIO 18: Find cross-device session via client_id

        Story: Sarah browses on her phone (client_id: abc123), sees a recommendation,
        then switches to her laptop (same client_id: abc123) to complete the purchase.
        We need to link these sessions to give proper attribution.

        Args:
            session: Database session
            shop_id: Shop identifier
            client_id: Shopify client ID
            current_time: Current timestamp

        Returns:
            UserSessionModel if found, None otherwise
        """
        try:
            # Find active session with same client_id
            stmt = (
                select(UserSessionModel)
                .where(
                    and_(
                        UserSessionModel.shop_id == shop_id,
                        UserSessionModel.client_id == client_id,
                        UserSessionModel.status == "active",
                        UserSessionModel.expires_at > current_time,
                    )
                )
                .order_by(UserSessionModel.last_active.desc())
                .limit(1)
            )

            result = await session.execute(stmt)
            cross_device_session = result.scalar_one_or_none()

            if cross_device_session:
                logger.info(
                    f"🔗 Cross-device session found: {cross_device_session.id} "
                    f"for client_id {client_id}"
                )

            return cross_device_session

        except Exception as e:
            logger.error(f"Error finding cross-device session: {e}")
            return None

    async def _find_expired_session_for_linking(
        self,
        session,
        shop_id: str,
        customer_id: Optional[str],
        browser_session_id: Optional[str],
        current_time: datetime,
    ) -> Optional[UserSessionModel]:
        """
        ✅ SCENARIO 20: Find expired session that can be linked for attribution

        Story: Sarah's session expires while browsing, but she starts a new session
        and completes the purchase. We need to link the expired session to the
        new one to maintain attribution continuity.

        Args:
            session: Database session
            shop_id: Shop identifier
            customer_id: Customer identifier
            browser_session_id: Browser session identifier
            current_time: Current timestamp

        Returns:
            UserSessionModel if found, None otherwise
        """
        try:
            # Look for recently expired sessions (within last 24 hours)
            recent_expiry = current_time - timedelta(hours=24)

            # Build query for expired sessions
            conditions = [
                UserSessionModel.shop_id == shop_id,
                UserSessionModel.status == "active",  # Still marked as active
                UserSessionModel.expires_at < current_time,  # But actually expired
                UserSessionModel.expires_at > recent_expiry,  # Recently expired
            ]

            # Add customer or browser session matching
            if customer_id:
                conditions.append(UserSessionModel.customer_id == customer_id)
            elif browser_session_id:
                conditions.append(
                    UserSessionModel.browser_session_id == browser_session_id
                )
            else:
                # No identifiers to match - return None
                return None

            stmt = (
                select(UserSessionModel)
                .where(and_(*conditions))
                .order_by(UserSessionModel.last_active.desc())
                .limit(1)
            )

            result = await session.execute(stmt)
            expired_session = result.scalar_one_or_none()

            if expired_session:
                logger.info(
                    f"🔄 Found recently expired session: {expired_session.id} "
                    f"(expired at {expired_session.expires_at})"
                )

                # Extend the expired session instead of creating new one
                expired_session.expires_at = (
                    current_time + self.anonymous_session_duration
                )
                expired_session.last_active = current_time
                await session.commit()
                await session.refresh(expired_session)

                logger.info(f"🔄 Extended expired session: {expired_session.id}")

            return expired_session

        except Exception as e:
            logger.error(f"Error finding expired session for linking: {e}")
            return None

    async def _find_existing_session(
        self,
        session,
        shop_id: str,
        customer_id: Optional[str],
        browser_session_id: Optional[str],
        current_time: datetime,
    ) -> Optional[UserSessionModel]:
        """
        Find existing active session with improved deduplication logic

        Priority order:
        1. Match by customer_id (if provided)
        2. Match by browser_session_id (if provided)
        3. Match by recent session from same shop (within last 5 seconds - race condition)
        """

        try:
            # ✅ Priority 1: Try browser_session_id first (most specific)
            if browser_session_id:
                stmt = (
                    select(UserSessionModel)
                    .where(
                        and_(
                            UserSessionModel.browser_session_id == browser_session_id,
                            UserSessionModel.shop_id == shop_id,
                            UserSessionModel.status == SessionStatus.ACTIVE,
                            UserSessionModel.expires_at > current_time,
                        )
                    )
                    .order_by(desc(UserSessionModel.last_active))
                )
                result = await session.execute(stmt)
                session_data = result.scalar_one_or_none()

                if session_data:
                    # ✅ Update customer_id if session was anonymous and now identified
                    # But only if it won't create a constraint violation
                    if customer_id and not session_data.customer_id:
                        try:
                            # Check if there's already a session with this customer_id and browser_session_id
                            existing_customer_session = await session.execute(
                                select(UserSessionModel).where(
                                    and_(
                                        UserSessionModel.customer_id == customer_id,
                                        UserSessionModel.browser_session_id
                                        == browser_session_id,
                                        UserSessionModel.shop_id == shop_id,
                                        UserSessionModel.status == SessionStatus.ACTIVE,
                                        UserSessionModel.expires_at > current_time,
                                    )
                                )
                            )
                            customer_session = (
                                existing_customer_session.scalar_one_or_none()
                            )

                            if not customer_session:
                                # Safe to update - no constraint violation
                                session_data.customer_id = customer_id
                                session_data.expires_at = (
                                    current_time + self.identified_session_duration
                                )
                                await session.commit()
                                await session.refresh(session_data)
                            else:
                                # There's already a session with this customer_id and browser_session_id
                                # Return the existing customer session instead
                                logger.debug(
                                    f"Found existing customer session, using that instead"
                                )
                                return customer_session
                        except Exception as e:
                            logger.warning(
                                f"Failed to update customer_id for session {session_data.id}: {e}"
                            )
                            # Continue with existing session even if customer_id update fails

                    return session_data

            # ✅ Priority 2: Fallback to customer_id lookup
            if customer_id:
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

                if session_data:
                    return session_data

            # ✅ NEW: Priority 3 - Race condition detection
            # If multiple requests hit at the same time, find very recent session from same shop
            five_seconds_ago = current_time - timedelta(seconds=5)
            stmt = (
                select(UserSessionModel)
                .where(
                    and_(
                        UserSessionModel.shop_id == shop_id,
                        UserSessionModel.status == SessionStatus.ACTIVE,
                        UserSessionModel.created_at > five_seconds_ago,
                        UserSessionModel.expires_at > current_time,
                    )
                )
                .order_by(desc(UserSessionModel.created_at))
            )
            result = await session.execute(stmt)
            recent_session = result.scalar_one_or_none()

            if recent_session:
                logger.warning(
                    f"⚠️ Possible race condition detected - reusing recent session: {recent_session.id}"
                )
                return recent_session

            return None

        except Exception as e:
            logger.error(f"Error finding existing session: {str(e)}")
            return None

    async def _create_new_session_with_retry(
        self,
        session,
        shop_id: str,
        customer_id: Optional[str],
        browser_session_id: Optional[str],
        user_agent: Optional[str],
        ip_address: Optional[str],
        referrer: Optional[str],
        current_time: datetime,
        client_id: Optional[str] = None,  # ✅ NEW parameter
    ) -> UserSession:
        """Create new session with retry logic for race conditions."""

        # Validate shop exists
        await self._validate_shop(session, shop_id)

        # Generate session ID and expiration
        session_id = str(uuid.uuid4())
        expires_at = current_time + (
            self.identified_session_duration
            if customer_id
            else self.anonymous_session_duration
        )

        # Retry mechanism with exponential backoff
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                # Generate new UUID for retry attempts
                if attempt > 0:
                    session_id = str(uuid.uuid4())
                    await asyncio.sleep(retry_delay * (2**attempt))

                # Create session model
                new_session_model = UserSessionModel(
                    id=session_id,
                    shop_id=shop_id,
                    customer_id=customer_id,
                    browser_session_id=browser_session_id,
                    status=SessionStatus.ACTIVE,
                    client_id=client_id,  # ✅ NEW: Pass client_id
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

                return self._convert_to_user_session(new_session_model)

            except Exception as e:
                # Rollback failed transaction
                await session.rollback()

                # Handle race conditions
                if self._is_unique_constraint_error(e):
                    logger.warning(
                        f"Session creation race condition detected: {session_id}"
                    )

                    # Try to find existing session created by concurrent request
                    existing_session = await self._find_session_by_id(
                        session, session_id
                    )
                    if existing_session:

                        return existing_session

                    # Try fallback to any active session for this user
                    fallback_session = await self._find_active_session(
                        shop_id, customer_id, browser_session_id
                    )
                    if fallback_session:

                        return fallback_session

                    # If this is the last attempt, re-raise the error
                    if attempt == max_retries - 1:
                        raise e
                else:
                    # Re-raise non-unique constraint errors
                    raise e

        # This should never be reached, but just in case
        raise Exception("Failed to create session after all retry attempts")

    async def _validate_shop(self, session, shop_id: str) -> None:
        """Validate that the shop exists and is active."""
        shop_result = await session.execute(select(Shop).where(Shop.id == shop_id))
        shop = shop_result.scalar_one_or_none()

        if not shop:
            logger.error(f"Shop not found for ID: {shop_id}")
            raise ValueError(f"Shop not found for ID: {shop_id}")

        if not shop.is_active:
            logger.error(f"Shop is inactive for ID: {shop_id}")
            raise ValueError(f"Shop is inactive for ID: {shop_id}")

    async def _find_session_by_id(
        self, session, session_id: str
    ) -> Optional[UserSession]:
        """Find session by ID within the current transaction."""
        try:
            stmt = select(UserSessionModel).where(UserSessionModel.id == session_id)
            result = await session.execute(stmt)
            session_data = result.scalar_one_or_none()

            if session_data:
                return self._convert_to_user_session(session_data)
            return None

        except Exception as e:
            logger.error(f"Error finding session by ID: {str(e)}")
            return None

    async def _find_active_session(
        self,
        shop_id: str,
        customer_id: Optional[str] = None,
        browser_session_id: Optional[str] = None,
    ) -> Optional[UserSession]:
        """Find existing active session using a new transaction."""
        try:
            async with get_transaction_context() as session:
                # Build conditions for finding active session
                where_conditions = [
                    UserSessionModel.shop_id == shop_id,
                    UserSessionModel.status == SessionStatus.ACTIVE,
                    UserSessionModel.expires_at > now_utc(),
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
                    return self._convert_to_user_session(session_data)

                return None

        except Exception as e:
            logger.error(f"Error finding active session: {str(e)}")
            return None

    def _convert_to_user_session(self, session_data) -> UserSession:
        """Convert SQLAlchemy model to Pydantic UserSession."""
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

    def _is_unique_constraint_error(self, error: Exception) -> bool:
        """Check if the error is a unique constraint violation."""
        error_str = str(error)
        return any(
            phrase in error_str
            for phrase in [
                "Unique constraint failed",
                "UniqueViolationError",
                "duplicate key value violates unique constraint",
            ]
        )

    # ============================================================================
    # BACKGROUND TASKS
    # ============================================================================

    async def _update_session_activity_background(self, session_id: str):
        """Update session activity in background without blocking the response."""
        try:
            async with get_transaction_context() as session:
                # First check if session still exists and is active
                stmt = select(UserSessionModel).where(UserSessionModel.id == session_id)
                result = await session.execute(stmt)
                session_data = result.scalar_one_or_none()

                if not session_data:
                    logger.debug(f"Session {session_id} not found for activity update")
                    return

                # Only update if session is still active
                if session_data.status == SessionStatus.ACTIVE:
                    update_stmt = (
                        update(UserSessionModel)
                        .where(UserSessionModel.id == session_id)
                        .values(last_active=now_utc())
                    )
                    await session.execute(update_stmt)
                    await session.commit()
                else:
                    logger.debug(
                        f"Session {session_id} is not active, skipping activity update"
                    )
        except Exception as e:
            logger.warning(f"Failed to update session activity in background: {e}")

    async def _update_session_activity(self, session_id: str) -> None:
        """Update session's last active time."""
        try:
            async with get_transaction_context() as session:
                stmt = (
                    update(UserSessionModel)
                    .where(UserSessionModel.id == session_id)
                    .values(last_active=now_utc())
                )
                await session.execute(stmt)
                await session.commit()

        except Exception as e:
            logger.error(f"Error updating session activity: {str(e)}")

    async def _cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions periodically."""
        try:
            # Only cleanup every hour to avoid excessive database operations
            if now_utc() - self._last_cleanup < self.cleanup_interval:
                return

            async with get_transaction_context() as session:
                # Mark expired sessions as expired
                stmt = (
                    update(UserSessionModel)
                    .where(
                        and_(
                            UserSessionModel.status == SessionStatus.ACTIVE,
                            UserSessionModel.expires_at <= now_utc(),
                        )
                    )
                    .values(status=SessionStatus.EXPIRED)
                )
                await session.execute(stmt)

                # Delete very old sessions (older than 30 days)
                cutoff_date = now_utc() - timedelta(days=30)
                delete_stmt = select(UserSessionModel).where(
                    UserSessionModel.created_at < cutoff_date
                )
                result = await session.execute(delete_stmt)
                old_sessions = result.scalars().all()

                for old_session in old_sessions:
                    await session.delete(old_session)

                await session.commit()

            self._last_cleanup = now_utc()

        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {str(e)}")
