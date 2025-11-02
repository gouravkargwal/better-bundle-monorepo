from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, desc, update
from sqlalchemy.orm import Session
from app.core.database.session import get_session_context
from app.core.database.models.user_session import UserSession as UserSessionModel
from app.core.database.models.shop import Shop
from app.domains.analytics.models.session import SessionStatus, SessionQuery
from app.core.logging.logger import get_logger

logger = get_logger(__name__)


class SessionRepository:
    """
    Repository for managing user session database operations.
    Handles all database queries and transactions for sessions.
    """

    def __init__(self, session_factory=None):
        """
        Initialize the repository with a session factory.
        Repository handles its own session management.
        """
        self.session_factory = session_factory or get_session_context

    # ============================================================================
    # BASIC CRUD OPERATIONS
    # ============================================================================

    async def create(
        self,
        session_id: str,
        shop_id: str,
        customer_id: Optional[str] = None,
        browser_session_id: Optional[str] = None,
        client_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        referrer: Optional[str] = None,
        created_at: datetime = None,
        expires_at: datetime = None,
    ) -> UserSessionModel:
        """Create a new session record."""
        async with self.session_factory() as session:
            new_session = UserSessionModel(
                id=session_id,
                shop_id=shop_id,
                customer_id=customer_id,
                browser_session_id=browser_session_id,
                client_id=client_id,
                user_agent=user_agent,
                ip_address=ip_address,
                referrer=referrer,
                status=SessionStatus.ACTIVE,
                created_at=created_at,
                last_active=created_at,
                expires_at=expires_at,
                extensions_used=[],
                total_interactions=0,
            )
            session.add(new_session)
            await session.commit()
            await session.refresh(new_session)
            return new_session

    async def get_by_id(self, session_id: str) -> Optional[UserSessionModel]:
        """Get session by ID."""
        async with self.session_factory() as session:
            stmt = select(UserSessionModel).where(UserSessionModel.id == session_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_active_by_id(
        self, session_id: str, current_time: datetime
    ) -> Optional[UserSessionModel]:
        """Get active session by ID that hasn't expired."""
        async with self.session_factory() as session:
            stmt = select(UserSessionModel).where(
                and_(
                    UserSessionModel.id == session_id,
                    UserSessionModel.status == SessionStatus.ACTIVE,
                    UserSessionModel.expires_at > current_time,
                )
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def update(
        self,
        session_id: str,
        customer_id: Optional[str] = None,
        client_id: Optional[str] = None,
        status: Optional[SessionStatus] = None,
        last_active: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        extensions_used: Optional[List[str]] = None,
        total_interactions: Optional[int] = None,
    ) -> bool:
        """Update session fields."""
        async with self.session_factory() as session:
            update_values = {}
            if customer_id is not None:
                update_values["customer_id"] = customer_id
            if client_id is not None:
                update_values["client_id"] = client_id
            if status is not None:
                update_values["status"] = status
            if last_active is not None:
                update_values["last_active"] = last_active
            if expires_at is not None:
                update_values["expires_at"] = expires_at
            if extensions_used is not None:
                update_values["extensions_used"] = extensions_used
            if total_interactions is not None:
                update_values["total_interactions"] = total_interactions

            if not update_values:
                return False

            stmt = (
                update(UserSessionModel)
                .where(UserSessionModel.id == session_id)
                .values(**update_values)
            )
            await session.execute(stmt)
            await session.commit()
            return True

    async def update_last_active(self, session_id: str, last_active: datetime) -> bool:
        """Update session's last active timestamp."""
        return await self.update(session_id=session_id, last_active=last_active)

    async def increment_interactions(self, session_id: str) -> bool:
        """Increment session's total interactions count."""
        async with self.session_factory() as session:
            # Get current count
            stmt = select(UserSessionModel.total_interactions).where(
                UserSessionModel.id == session_id
            )
            result = await session.execute(stmt)
            current_count = result.scalar_one_or_none()

            if current_count is not None:
                update_stmt = (
                    update(UserSessionModel)
                    .where(UserSessionModel.id == session_id)
                    .values(total_interactions=current_count + 1)
                )
                await session.execute(update_stmt)
                await session.commit()
                return True
            return False

    # ============================================================================
    # QUERY OPERATIONS
    # ============================================================================

    async def find_active_by_customer(
        self,
        shop_id: str,
        customer_id: str,
        current_time: datetime,
    ) -> Optional[UserSessionModel]:
        """Find active session by customer_id (priority 1)."""
        async with self.session_factory() as session:
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
            return result.scalar_one_or_none()

    async def find_active_by_client_id(
        self,
        shop_id: str,
        client_id: str,
        current_time: datetime,
    ) -> Optional[UserSessionModel]:
        """Find active session by client_id (priority 2)."""
        async with self.session_factory() as session:
            stmt = (
                select(UserSessionModel)
                .where(
                    and_(
                        UserSessionModel.shop_id == shop_id,
                        UserSessionModel.client_id == client_id,
                        UserSessionModel.status == SessionStatus.ACTIVE,
                        UserSessionModel.expires_at > current_time,
                    )
                )
                .order_by(desc(UserSessionModel.last_active))
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def find_active_by_browser_session(
        self,
        shop_id: str,
        browser_session_id: str,
        current_time: datetime,
    ) -> Optional[UserSessionModel]:
        """Find active session by browser_session_id (priority 3)."""
        async with self.session_factory() as session:
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
            return result.scalar_one_or_none()

    async def find_recent_by_shop(
        self,
        shop_id: str,
        current_time: datetime,
        seconds_ago: int = 5,
    ) -> Optional[UserSessionModel]:
        """Find very recent session (for race condition detection)."""
        async with self.session_factory() as session:
            cutoff_time = current_time - timedelta(seconds=seconds_ago)
            stmt = (
                select(UserSessionModel)
                .where(
                    and_(
                        UserSessionModel.shop_id == shop_id,
                        UserSessionModel.status == SessionStatus.ACTIVE,
                        UserSessionModel.created_at > cutoff_time,
                        UserSessionModel.expires_at > current_time,
                    )
                )
                .order_by(desc(UserSessionModel.created_at))
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def find_expired_for_linking(
        self,
        shop_id: str,
        customer_id: Optional[str],
        client_id: Optional[str],
        current_time: datetime,
        hours_back: int = 24,
    ) -> Optional[UserSessionModel]:
        """Find recently expired session for linking (within last N hours)."""
        async with self.session_factory() as session:
            recent_expiry = current_time - timedelta(hours=hours_back)

            conditions = [
                UserSessionModel.shop_id == shop_id,
                UserSessionModel.status == "active",  # Still marked as active
                UserSessionModel.expires_at < current_time,  # But actually expired
                UserSessionModel.expires_at > recent_expiry,  # Recently expired
            ]

            # Only match using persistent identifiers
            if customer_id:
                conditions.append(UserSessionModel.customer_id == customer_id)
            elif client_id:
                conditions.append(UserSessionModel.client_id == client_id)
            else:
                return None

            stmt = (
                select(UserSessionModel)
                .where(and_(*conditions))
                .order_by(desc(UserSessionModel.last_active))
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def find_recent_customer_session(
        self,
        customer_id: str,
        shop_id: str,
        current_time: datetime,
        minutes_back: int = 30,
    ) -> Optional[UserSessionModel]:
        """Find most recent active session for customer within last N minutes."""
        async with self.session_factory() as session:
            cutoff_time = current_time - timedelta(minutes=minutes_back)
            stmt = (
                select(UserSessionModel)
                .where(
                    and_(
                        UserSessionModel.customer_id == customer_id,
                        UserSessionModel.shop_id == shop_id,
                        UserSessionModel.status == SessionStatus.ACTIVE,
                        UserSessionModel.last_active > cutoff_time,
                    )
                )
                .order_by(desc(UserSessionModel.last_active))
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def query(self, query: SessionQuery) -> List[UserSessionModel]:
        """Query sessions based on criteria."""
        async with self.session_factory() as session:
            where_conditions = [UserSessionModel.shop_id == query.shop_id]

            if query.customer_id:
                where_conditions.append(
                    UserSessionModel.customer_id == query.customer_id
                )
            if query.client_id:
                where_conditions.append(UserSessionModel.client_id == query.client_id)
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

            stmt = (
                select(UserSessionModel)
                .where(and_(*where_conditions))
                .order_by(desc(UserSessionModel.created_at))
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def check_active_session_conflict(
        self,
        shop_id: str,
        customer_id: str,
        exclude_session_id: str,
        current_time: datetime,
    ) -> Optional[UserSessionModel]:
        """
        Check if ANOTHER active session already has this customer_id.

        Used before updating customer_id to ensure we don't create duplicates.
        This is now the APPLICATION layer's responsibility (was database layer before).
        """
        async with self.session_factory() as session:
            stmt = select(UserSessionModel).where(
                and_(
                    UserSessionModel.shop_id == shop_id,
                    UserSessionModel.customer_id == customer_id,
                    UserSessionModel.status == SessionStatus.ACTIVE,
                    UserSessionModel.expires_at > current_time,
                    UserSessionModel.id
                    != exclude_session_id,  # Exclude current session
                )
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    # ============================================================================
    # LIFECYCLE OPERATIONS
    # ============================================================================

    async def terminate(self, session_id: str, current_time: datetime) -> bool:
        """Terminate a session."""
        return await self.update(
            session_id=session_id,
            status=SessionStatus.TERMINATED,
            last_active=current_time,
        )

    async def mark_expired_sessions(self, current_time: datetime) -> int:
        """Mark expired sessions as expired. Returns count of updated sessions."""
        async with self.session_factory() as session:
            stmt = (
                update(UserSessionModel)
                .where(
                    and_(
                        UserSessionModel.status == SessionStatus.ACTIVE,
                        UserSessionModel.expires_at <= current_time,
                    )
                )
                .values(status=SessionStatus.EXPIRED)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    async def delete_old_sessions(self, cutoff_date: datetime) -> int:
        """Delete very old sessions. Returns count of deleted sessions."""
        async with self.session_factory() as session:
            stmt = select(UserSessionModel).where(
                UserSessionModel.created_at < cutoff_date
            )
            result = await session.execute(stmt)
            old_sessions = result.scalars().all()

            count = 0
            for old_session in old_sessions:
                await session.delete(old_session)
                count += 1

            await session.commit()
            return count

    # ============================================================================
    # VALIDATION OPERATIONS
    # ============================================================================

    async def validate_shop_exists_and_active(self, shop_id: str) -> bool:
        """Validate that shop exists and is active."""
        async with self.session_factory() as session:
            shop_result = await session.execute(
                select(Shop).where(and_(Shop.id == shop_id, Shop.is_active == True))
            )
            shop = shop_result.scalar_one_or_none()
            return shop is not None
