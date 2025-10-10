"""
Client ID to User ID Resolver Service

This service resolves user_id from client_id using the customer linking system.
When users aren't logged in, we can still get their user_id from the client_id
that's passed in interaction data.
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database.models.identity import UserIdentityLink
from app.core.logging import get_logger

logger = get_logger(__name__)


class ClientIdResolver:
    """Service for resolving user_id from client_id"""

    async def resolve_user_id_from_client_id(
        self,
        session: AsyncSession,
        shop_id: str,
        client_id: str,
    ) -> Optional[str]:
        """
        Resolve user_id (customer_id) from client_id using the identity linking system.

        Args:
            session: Database session
            shop_id: Shop ID
            client_id: Client ID from interaction data

        Returns:
            User ID (customer_id) if found, None otherwise
        """
        try:
            # Query the UserIdentityLink table to find the customer_id linked to this client_id
            stmt = select(UserIdentityLink.customer_id).where(
                (UserIdentityLink.shop_id == shop_id)
                & (UserIdentityLink.identifier == client_id)
                & (UserIdentityLink.identifier_type == "client_id")
            )

            result = await session.execute(stmt)
            customer_id = result.scalar_one_or_none()

            if customer_id:
                logger.debug(
                    f"🔗 Resolved user_id {customer_id} from client_id {client_id} for shop {shop_id}"
                )
                return customer_id
            else:
                logger.debug(
                    f"❌ No user_id found for client_id {client_id} in shop {shop_id}"
                )
                return None

        except Exception as e:
            logger.error(
                f"💥 Error resolving user_id from client_id {client_id}: {str(e)}"
            )
            return None

    async def resolve_user_id_from_session_id(
        self,
        session: AsyncSession,
        shop_id: str,
        session_id: str,
    ) -> Optional[str]:
        """
        Resolve user_id (customer_id) from session_id as fallback.

        Args:
            session: Database session
            shop_id: Shop ID
            session_id: Session ID

        Returns:
            User ID (customer_id) if found, None otherwise
        """
        try:
            # Query the UserIdentityLink table to find the customer_id linked to this session_id
            stmt = select(UserIdentityLink.customer_id).where(
                (UserIdentityLink.shop_id == shop_id)
                & (UserIdentityLink.identifier == session_id)
                & (UserIdentityLink.identifier_type == "browser_session_id")
            )

            result = await session.execute(stmt)
            customer_id = result.scalar_one_or_none()

            if customer_id:
                logger.debug(
                    f"🔗 Resolved user_id {customer_id} from session_id {session_id} for shop {shop_id}"
                )
                return customer_id
            else:
                logger.debug(
                    f"❌ No user_id found for session_id {session_id} in shop {shop_id}"
                )
                return None

        except Exception as e:
            logger.error(
                f"💥 Error resolving user_id from session_id {session_id}: {str(e)}"
            )
            return None

    async def resolve_user_id_from_metadata(
        self,
        session: AsyncSession,
        shop_id: str,
        metadata: dict,
    ) -> Optional[str]:
        """
        Resolve user_id from various identifiers in metadata.

        Args:
            session: Database session
            shop_id: Shop ID
            metadata: Interaction metadata containing identifiers

        Returns:
            User ID (customer_id) if found, None otherwise
        """
        try:
            # Try client_id first (most reliable)
            client_id = metadata.get("client_id") or metadata.get("clientId")
            if client_id:
                user_id = await self.resolve_user_id_from_client_id(
                    session, shop_id, client_id
                )
                if user_id:
                    return user_id

            # Try session_id as fallback
            session_id = metadata.get("session_id") or metadata.get("sessionId")
            if session_id:
                user_id = await self.resolve_user_id_from_session_id(
                    session, shop_id, session_id
                )
                if user_id:
                    return user_id

            # Try other possible identifiers
            for identifier_key in ["browser_session_id", "device_id", "visitor_id"]:
                identifier = metadata.get(identifier_key)
                if identifier:
                    stmt = select(UserIdentityLink.customer_id).where(
                        (UserIdentityLink.shop_id == shop_id)
                        & (UserIdentityLink.identifier == identifier)
                        & (UserIdentityLink.identifier_type == identifier_key)
                    )

                    result = await session.execute(stmt)
                    customer_id = result.scalar_one_or_none()

                    if customer_id:
                        logger.debug(
                            f"🔗 Resolved user_id {customer_id} from {identifier_key} {identifier}"
                        )
                        return customer_id

            logger.debug(f"❌ No user_id found in metadata for shop {shop_id}")
            return None

        except Exception as e:
            logger.error(f"💥 Error resolving user_id from metadata: {str(e)}")
            return None

    async def resolve_user_id_from_session_data(
        self,
        session: AsyncSession,
        shop_id: str,
        session_id: str,
    ) -> Optional[str]:
        """
        Resolve user_id from session data by looking up the session's client_id.

        Args:
            session: Database session
            shop_id: Shop ID
            session_id: Session ID

        Returns:
            User ID (customer_id) if found, None otherwise
        """
        try:
            # Import the UserSession model
            from app.core.database.models.user_session import UserSession

            # Get the session data
            stmt = select(UserSession.client_id, UserSession.customer_id).where(
                (UserSession.shop_id == shop_id) & (UserSession.id == session_id)
            )

            result = await session.execute(stmt)
            session_data = result.first()

            if not session_data:
                logger.debug(
                    f"❌ No session found for session_id {session_id} in shop {shop_id}"
                )
                return None

            # If session already has customer_id, return it
            if session_data.customer_id:
                logger.debug(
                    f"🔗 Session {session_id} already has customer_id: {session_data.customer_id}"
                )
                return session_data.customer_id

            # If session has client_id, try to resolve user_id from it
            if session_data.client_id:
                user_id = await self.resolve_user_id_from_client_id(
                    session, shop_id, session_data.client_id
                )
                if user_id:
                    logger.debug(
                        f"🔗 Resolved user_id {user_id} from session {session_id} client_id {session_data.client_id}"
                    )
                    return user_id

            logger.debug(
                f"❌ No user_id found for session {session_id} in shop {shop_id}"
            )
            return None

        except Exception as e:
            logger.error(f"💥 Error resolving user_id from session data: {str(e)}")
            return None
