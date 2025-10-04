"""
Simple Trial Configuration Model

Stores USD-based trial thresholds for different currencies.
Frontend will handle currency conversion.
"""

from datetime import UTC, datetime
from sqlalchemy import Column, String, Boolean, Index
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.types import DECIMAL
from .base import BaseModel
from .base import TimestampMixin


class TrialConfig(BaseModel, TimestampMixin):
    """Simple trial configuration with USD thresholds"""

    __tablename__ = "trial_configs"

    # Currency identification
    currency_code = Column(String(3), nullable=False, unique=True, index=True)
    currency_symbol = Column(String(10), nullable=False)  # $, €, ₹, etc.

    # Trial threshold in USD
    trial_threshold_usd = Column(DECIMAL(10, 2), nullable=False)

    # Market classification
    market_tier = Column(String(20), nullable=False)  # major, emerging, developing
    market_description = Column(String(100), nullable=True)

    # Configuration
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Indexes
    __table_args__ = (
        Index("ix_trial_config_currency", "currency_code"),
        Index("ix_trial_config_tier", "market_tier"),
        Index("ix_trial_config_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<TrialConfig(currency={self.currency_code}, threshold_usd={self.trial_threshold_usd}, tier={self.market_tier})>"
