"""
Suspension Audit Log Model

Tracks all shop suspension and reactivation events for auditing purposes.
Each time a shop is suspended or reactivated, a row is inserted to maintain
a permanent history that is never overwritten.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from .base import Base


class SuspensionAuditLog(Base):
    """
    Suspension Audit Log

    Immutable audit trail of suspension and reactivation events.
    Once written, rows are never modified or deleted.
    """

    __tablename__ = "suspension_audit_log"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="Auto-incrementing primary key",
    )
    shop_id = Column(
        String,
        nullable=False,
        index=True,
        comment="Shop UUID from the shops table",
    )
    action = Column(
        String(50),
        nullable=False,
        comment="Event type: SUSPENDED or REACTIVATED",
    )
    reason = Column(
        Text,
        nullable=True,
        comment="Reason for the suspension or reactivation",
    )
    triggered_by = Column(
        String(50),
        nullable=False,
        default="system",
        server_default="system",
        comment="What triggered this event: system, webhook, or admin",
    )
    metadata_json = Column(
        Text,
        nullable=True,
        comment="Arbitrary JSON metadata for additional context",
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default="NOW()",
        default=lambda: datetime.now(timezone.utc),
        comment="When the event was recorded",
    )

    # Indexes
    __table_args__ = (
        Index(
            "idx_suspension_audit_log_shop_id",
            "shop_id",
        ),
        Index(
            "idx_suspension_audit_log_created_at",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return f"<SuspensionAuditLog(id={self.id}, shop_id={self.shop_id}, action={self.action}, created_at={self.created_at})>"
