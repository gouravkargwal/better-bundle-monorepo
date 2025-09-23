"""
Session model for SQLAlchemy

Represents user sessions for the Shopify app.
Uses camelCase column names to match Prisma exactly.
"""

from sqlalchemy import Column, String, Boolean, DateTime, BigInteger, Index
from .base import Base


class Session(Base):
    """Session model representing user sessions"""

    __tablename__ = "Session"

    # Primary key (matches Prisma: String @id)
    id = Column(String, primary_key=True)

    # Session identification (camelCase to match Prisma)
    shop = Column(String, nullable=False)
    state = Column(String, nullable=False)
    isOnline = Column("isOnline", Boolean, default=False, nullable=False)

    # OAuth information (camelCase to match Prisma)
    scope = Column(String(500), nullable=True)
    expires = Column(DateTime, nullable=True)
    accessToken = Column("accessToken", String(1000), nullable=False)

    # User information (camelCase to match Prisma exactly)
    userId = Column("userId", BigInteger, nullable=True)
    firstName = Column("firstName", String(100), nullable=True)
    lastName = Column("lastName", String(100), nullable=True)
    email = Column(String(255), nullable=True)
    accountOwner = Column("accountOwner", Boolean, default=False, nullable=False)
    locale = Column(String(10), nullable=True)
    collaborator = Column(Boolean, nullable=True)
    emailVerified = Column("emailVerified", Boolean, nullable=True)

    # Indexes (matching Prisma indexes)
    # Note: These will be created automatically by SQLAlchemy
    # and won't conflict if they already exist
    __table_args__ = (
        Index("ix_Session_shop", "shop"),
        Index("ix_Session_expires", "expires"),
    )

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, shop={self.shop}, userId={self.userId})>"
