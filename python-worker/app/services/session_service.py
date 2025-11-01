import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional

from app.shared.helpers import now_utc

from app.core.database.models.user_session import UserSession as UserSessionModel
from app.domains.analytics.models.session import (
    UserSession,
    SessionUpdate,
    SessionStatus,
)
from app.core.logging.logger import get_logger
from app.repository.UserSessionRepository import SessionRepository

logger = get_logger(__name__)


class SessionService:

    def __init__(self):
        self.anonymous_session_duration = timedelta(days=30)
        self.identified_session_duration = timedelta(days=7)
        self.cleanup_interval = timedelta(hours=1)
        self._last_cleanup = now_utc()
        self.repository = SessionRepository()

    async def get_or_create_session(
        self,
        shop_id: str,
        customer_id: Optional[str] = None,
        browser_session_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        referrer: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> UserSession:
        try:
            current_time = now_utc()
            await self._cleanup_expired_sessions()
            existing_session = await self._find_existing_session(
                None,
                shop_id,
                customer_id,
                client_id,
                browser_session_id,
                current_time,
            )

            if not existing_session:
                existing_session = await self._find_expired_session_for_linking(
                    None,
                    shop_id,
                    customer_id,
                    client_id,
                    current_time,
                )
                if existing_session:
                    logger.info(
                        f"🔄 Expired session found for linking: {existing_session.id}"
                    )

            if existing_session:
                asyncio.create_task(
                    self._update_session_activity_background(existing_session.id)
                )
                return self._convert_to_user_session(existing_session)

            return await self._create_new_session_with_retry(
                None,
                shop_id,
                customer_id,
                browser_session_id,
                user_agent,
                ip_address,
                referrer,
                current_time,
                client_id,
            )

        except Exception as e:
            logger.error(f"Error in get_or_create_session: {str(e)}")
            raise

    async def get_session(self, session_id: str) -> Optional[UserSession]:

        try:
            current_time = now_utc()
            session_data = await self.repository.get_active_by_id(
                session_id, current_time
            )

            if session_data:
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
        try:
            current_session = await self.repository.get_by_id(session_id)

            if not current_session:
                logger.warning(f"Session {session_id} not found for update")
                return None

            # Prepare update data
            update_dict = update_data.model_dump(exclude_unset=True)
            if "last_active" not in update_dict:
                update_dict["last_active"] = now_utc()

            # Check for constraint violations if updating customer_id
            if "customer_id" in update_dict and update_dict["customer_id"]:
                new_customer_id = update_dict["customer_id"]
                if new_customer_id != current_session.customer_id:
                    # Check for active session with same customer_id (to avoid duplicates)
                    existing_session = (
                        await self.repository.check_active_session_conflict(
                            shop_id=current_session.shop_id,
                            customer_id=new_customer_id,
                            exclude_session_id=session_id,
                            current_time=now_utc(),
                        )
                    )

                    if existing_session:
                        logger.warning(
                            f"Cannot update session {session_id} - active session {existing_session.id} already exists for customer {new_customer_id}"
                        )
                        return None

            # Map to repository update parameters
            update_kwargs = {}
            if "customer_id" in update_dict:
                update_kwargs["customer_id"] = update_dict["customer_id"]
            if "client_id" in update_dict:
                update_kwargs["client_id"] = update_dict["client_id"]
            if "status" in update_dict:
                update_kwargs["status"] = update_dict["status"]
            if "last_active" in update_dict:
                update_kwargs["last_active"] = update_dict["last_active"]
            if "extensions_used" in update_dict:
                update_kwargs["extensions_used"] = update_dict["extensions_used"]
            if "total_interactions" in update_dict:
                update_kwargs["total_interactions"] = update_dict["total_interactions"]

            # Execute update via repository
            success = await self.repository.update(
                session_id=session_id, **update_kwargs
            )

            if success:
                # Return updated session
                return await self.get_session(session_id)
            return None

        except Exception as e:
            logger.error(f"Error updating session {session_id}: {str(e)}")
            return None

    # ============================================================================
    # SESSION LIFECYCLE MANAGEMENT
    # ============================================================================

    async def add_extension_to_session(
        self, session_id: str, extension_type: str
    ) -> bool:
        """
        Add extension to session's extensions_used list.

        Args:
            session_id: The session ID
            extension_type: The extension type (string: "phoenix", "apollo", "venus", "atlas", "mercury", or "unknown")

        Returns:
            True if successful, False otherwise
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                return False

            # Normalize to lowercase for consistency
            extension_type_normalized = (
                extension_type.lower() if extension_type else "unknown"
            )

            if extension_type_normalized not in session.extensions_used:
                session.extensions_used.append(extension_type_normalized)

                await self.update_session(
                    session_id, SessionUpdate(extensions_used=session.extensions_used)
                )

            return True

        except Exception as e:
            logger.error(f"Error adding extension to session: {str(e)}")
            return False

    async def increment_session_interactions(self, session_id: str) -> bool:
        try:
            success = await self.repository.increment_interactions(session_id)
            if not success:
                logger.warning(
                    f"Session {session_id} not found for interaction increment"
                )
            return success

        except Exception as e:
            logger.error(f"Error incrementing session interactions: {str(e)}")
            return False

    async def _find_expired_session_for_linking(
        self,
        session,
        shop_id: str,
        customer_id: Optional[str],
        client_id: Optional[str],
        current_time: datetime,
    ) -> Optional[UserSessionModel]:
        try:
            expired_session = await self.repository.find_expired_for_linking(
                shop_id, customer_id, client_id, current_time
            )

            if expired_session:
                logger.info(
                    f"🔄 Found recently expired session: {expired_session.id} "
                    f"(expired at {expired_session.expires_at})"
                )

                await self.repository.update(
                    session_id=expired_session.id,
                    expires_at=current_time + self.anonymous_session_duration,
                    last_active=current_time,
                )

                logger.info(f"🔄 Extended expired session: {expired_session.id}")

                # Reload the session to get updated values
                expired_session = await self.repository.get_by_id(expired_session.id)

            return expired_session

        except Exception as e:
            logger.error(f"Error finding expired session for linking: {e}")
            return None

    async def _find_existing_session(
        self,
        session,
        shop_id: str,
        customer_id: Optional[str],
        client_id: Optional[str],
        browser_session_id: Optional[str],
        current_time: datetime,
    ) -> Optional[UserSessionModel]:
        try:
            # Priority 1: customer_id (works across all devices when logged in)
            if customer_id:
                session_data = await self.repository.find_active_by_customer(
                    shop_id, customer_id, current_time
                )

                if session_data:
                    # Update client_id if provided and not already set
                    if client_id and not session_data.client_id:
                        try:
                            await self.repository.update(
                                session_id=session_data.id, client_id=client_id
                            )
                            # Reload to get updated values
                            session_data = await self.repository.get_by_id(
                                session_data.id
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to update client_id for session {session_data.id}: {e}"
                            )
                    return session_data

            # Priority 2: client_id (cross-device linking when Atlas runs)
            if client_id:
                session_data = await self.repository.find_active_by_client_id(
                    shop_id, client_id, current_time
                )

                if session_data:
                    # Update customer_id if session was anonymous and now identified
                    if customer_id and not session_data.customer_id:
                        try:
                            await self.repository.update(
                                session_id=session_data.id,
                                customer_id=customer_id,
                                expires_at=current_time
                                + self.identified_session_duration,
                            )
                            # Reload to get updated values
                            session_data = await self.repository.get_by_id(
                                session_data.id
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to update customer_id for session {session_data.id}: {e}"
                            )

                    logger.info(f"🔗 Found session via client_id: {session_data.id}")
                    return session_data

            # Priority 3: browser_session_id (fallback for same-device only)
            if browser_session_id:
                session_data = await self.repository.find_active_by_browser_session(
                    shop_id, browser_session_id, current_time
                )

                if session_data:
                    # Update identifiers if available
                    update_kwargs = {}
                    if customer_id and not session_data.customer_id:
                        update_kwargs["customer_id"] = customer_id
                        update_kwargs["expires_at"] = (
                            current_time + self.identified_session_duration
                        )

                    if client_id and not session_data.client_id:
                        update_kwargs["client_id"] = client_id

                    if update_kwargs:
                        try:
                            await self.repository.update(
                                session_id=session_data.id, **update_kwargs
                            )
                            # Reload to get updated values
                            session_data = await self.repository.get_by_id(
                                session_data.id
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to update session {session_data.id}: {e}"
                            )

                    return session_data

            # Priority 4: Race condition detection
            recent_session = await self.repository.find_recent_by_shop(
                shop_id, current_time
            )

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
        client_id: Optional[str] = None,
    ) -> UserSession:

        # Validate shop exists
        shop_exists = await self.repository.validate_shop_exists_and_active(shop_id)
        if not shop_exists:
            raise ValueError(f"Shop not found or inactive: {shop_id}")

        # Generate browser_session_id if not provided (backend-generated for fallback)
        original_browser_session_id = browser_session_id
        if not browser_session_id:
            short_uuid = uuid.uuid4().hex[:12]
            browser_session_id = f"bb_{short_uuid}"
            logger.debug(f"Generated new browser_session_id: {browser_session_id}")

        # Generate session expiration
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
                session_id = str(uuid.uuid4())
                if attempt > 0:
                    # Regenerate browser_session_id on retry only if it wasn't originally provided
                    if not original_browser_session_id:
                        short_uuid = uuid.uuid4().hex[:12]
                        browser_session_id = f"bb_{short_uuid}"
                    await asyncio.sleep(retry_delay * (2**attempt))

                # Use repository to create session
                new_session_model = await self.repository.create(
                    session_id=session_id,
                    shop_id=shop_id,
                    customer_id=customer_id,
                    browser_session_id=browser_session_id,
                    client_id=client_id,
                    user_agent=user_agent,
                    ip_address=ip_address,
                    referrer=referrer,
                    created_at=current_time,
                    expires_at=expires_at,
                )

                return self._convert_to_user_session(new_session_model)

            except Exception as e:
                # Handle race conditions
                if self._is_unique_constraint_error(e):
                    logger.warning(
                        f"Session creation race condition detected: {session_id}"
                    )

                    # Try to find existing session created by concurrent request
                    existing_session = await self.repository.get_by_id(session_id)
                    if existing_session:
                        return self._convert_to_user_session(existing_session)

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
        shop_exists = await self.repository.validate_shop_exists_and_active(shop_id)
        if not shop_exists:
            raise ValueError(f"Shop not found or inactive: {shop_id}")

    async def _find_session_by_id(
        self, session, session_id: str
    ) -> Optional[UserSession]:
        try:
            session_data = await self.repository.get_by_id(session_id)
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
        try:
            current_time = now_utc()
            session_data = None

            # Prioritize persistent identifiers
            if customer_id:
                session_data = await self.repository.find_active_by_customer(
                    shop_id, customer_id, current_time
                )
            elif browser_session_id:
                session_data = await self.repository.find_active_by_browser_session(
                    shop_id, browser_session_id, current_time
                )

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
            client_id=getattr(session_data, "client_id", None),  # Include client_id
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

    async def _update_session_activity_background(self, session_id: str):
        """Update session activity in background without blocking the response."""
        try:
            # First check if session still exists and is active
            session_data = await self.repository.get_by_id(session_id)

            if not session_data:
                logger.debug(f"Session {session_id} not found for activity update")
                return

            # Only update if session is still active
            if session_data.status == SessionStatus.ACTIVE:
                await self.repository.update_last_active(session_id, now_utc())
            else:
                logger.debug(
                    f"Session {session_id} is not active, skipping activity update"
                )
        except Exception as e:
            logger.warning(f"Failed to update session activity in background: {e}")

    async def _update_session_activity(self, session_id: str) -> None:
        """Update session's last active time."""
        try:
            await self.repository.update_last_active(session_id, now_utc())

        except Exception as e:
            logger.error(f"Error updating session activity: {str(e)}")

    async def _cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions periodically."""
        try:
            # Only cleanup every hour to avoid excessive database operations
            if now_utc() - self._last_cleanup < self.cleanup_interval:
                return

            current_time = now_utc()

            # Mark expired sessions as expired
            await self.repository.mark_expired_sessions(current_time)

            # Delete very old sessions (older than 30 days)
            cutoff_date = current_time - timedelta(days=30)
            await self.repository.delete_old_sessions(cutoff_date)

            self._last_cleanup = now_utc()

        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {str(e)}")

    async def _find_recent_customer_session(
        self, customer_id: str, shop_id: str, minutes_back: int = 30
    ) -> Optional[UserSession]:
        try:
            current_time = now_utc()
            session_data = await self.repository.find_recent_customer_session(
                customer_id, shop_id, current_time, minutes_back
            )

            if session_data:
                logger.info(
                    f"🔍 Found recent session for customer {customer_id}: {session_data.id}"
                )
                return self._convert_to_user_session(session_data)
            return None

        except Exception as e:
            logger.error(f"Error finding recent customer session: {str(e)}")
            return None
