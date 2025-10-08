"""
Session model for SQLAlchemy

Represents user sessions for the Shopify app.
This model exactly matches the Prisma sessions table structure
for Remix compatibility.
"""

from sqlalchemy import Column, String, Boolean, BigInteger, Index, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from .base import Base


class Session(Base):
    """Session model representing Shopify app sessions - matches Prisma schema exactly"""

    __tablename__ = "sessions"

    # Primary key (matches Prisma: String @id)
    id = Column(String, primary_key=True)

    # Session identification (camelCase for Remix compatibility)
    shop = Column("shop", String, nullable=False)
    state = Column("state", String, nullable=False)
    is_online = Column("isOnline", Boolean, nullable=False)

    # OAuth information (camelCase for Remix compatibility)
    scope = Column("scope", String(500), nullable=True)
    expires = Column("expires", TIMESTAMP(timezone=True), nullable=True)
    access_token = Column("accessToken", String(1000), nullable=False)

    # User information (camelCase for Remix compatibility)
    user_id = Column("userId", BigInteger, nullable=True)
    first_name = Column("firstName", String(100), nullable=True)
    last_name = Column("lastName", String(100), nullable=True)
    email = Column("email", String(255), nullable=True)
    account_owner = Column("accountOwner", Boolean, nullable=False)
    locale = Column("locale", String(10), nullable=True)
    collaborator = Column("collaborator", Boolean, nullable=True)
    email_verified = Column("emailVerified", Boolean, nullable=True)

    # Timestamps (camelCase for Remix compatibility)
    created_at = Column(
        "createdAt",
        TIMESTAMP(timezone=True),
        nullable=False,
        default=func.timezone("UTC", func.current_timestamp()),
        server_default=func.timezone("UTC", func.current_timestamp()),
    )
    updated_at = Column(
        "updatedAt",
        TIMESTAMP(timezone=True),
        nullable=False,
        default=func.timezone("UTC", func.current_timestamp()),
        server_default=func.timezone("UTC", func.current_timestamp()),
        onupdate=func.timezone("UTC", func.current_timestamp()),
    )

    # Indexes (using camelCase column names)
    __table_args__ = (
        Index("ix_sessions_expires", "expires"),
        Index("ix_sessions_shop", "shop"),
    )

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, shop={self.shop}, user_id={self.user_id})>"
