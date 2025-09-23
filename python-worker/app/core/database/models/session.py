"""
Session model for SQLAlchemy

Represents user sessions for the Shopify app.
"""

from sqlalchemy import Column, String, Boolean, DateTime, BigInteger
from .base import BaseModel


class Session(BaseModel):
    """Session model representing user sessions"""

    __tablename__ = "Session"

    # Session identification
    shop = Column(String, nullable=False, index=True)
    state = Column(String, nullable=False)
    is_online = Column(Boolean, default=False, nullable=False)

    # OAuth information
    scope = Column(String(500), nullable=True)
    expires = Column(DateTime, nullable=True, index=True)
    access_token = Column(String(1000), nullable=False)

    # User information
    user_id = Column(BigInteger, nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    account_owner = Column(Boolean, default=False, nullable=False)
    locale = Column(String(10), nullable=True)
    collaborator = Column(Boolean, nullable=True)
    email_verified = Column(Boolean, nullable=True)

    def __repr__(self) -> str:
        return f"<Session(shop={self.shop}, user_id={self.user_id})>"
