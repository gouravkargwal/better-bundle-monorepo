"""
Session model for SQLAlchemy

Represents user sessions for the Shopify app.
Uses snake_case column names for consistency.
"""

from sqlalchemy import Column, String, Boolean, DateTime, BigInteger, Index
from .base import Base, TimestampMixin


class Session(Base, TimestampMixin):
    """Session model representing user sessions"""

    __tablename__ = "sessions"

    # Primary key (matches Prisma: String @id)
    id = Column(String, primary_key=True)

    # Session identification (snake_case for consistency)
    shop = Column(String, nullable=False)
    state = Column(String, nullable=False)
    is_online = Column(Boolean, default=False, nullable=False)

    # OAuth information (snake_case for consistency)
    scope = Column(String(500), nullable=True)
    expires = Column(DateTime, nullable=True)
    access_token = Column(String(1000), nullable=False)

    # User information (snake_case for consistency)
    user_id = Column(BigInteger, nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    account_owner = Column(Boolean, default=False, nullable=False)
    locale = Column(String(10), nullable=True)
    collaborator = Column(Boolean, nullable=True)
    email_verified = Column(Boolean, nullable=True)

    # Indexes (matching Prisma indexes)
    # Note: These will be created automatically by SQLAlchemy
    # and won't conflict if they already exist
    __table_args__ = (
        Index("ix_sessions_shop", "shop"),
        Index("ix_sessions_expires", "expires"),
    )

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, shop={self.shop}, user_id={self.user_id})>"
