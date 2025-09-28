"""
Base model class for SQLAlchemy models

Provides common functionality and base configuration for all models.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import Column, String, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import declared_attr
from sqlalchemy.dialects.postgresql import UUID
import uuid

# Create the declarative base
Base = declarative_base()


class TimestampMixin:
    """Mixin for models that need created_at and updated_at timestamps"""

    created_at = Column(
        "created_at",
        TIMESTAMP(timezone=True),
        default=func.current_timestamp(),
        nullable=False,
    )
    updated_at = Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )


class IDMixin:
    """Mixin for models that need a primary key ID"""

    @declared_attr
    def id(cls):
        return Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))


class BaseModel(Base, IDMixin, TimestampMixin):
    """
    Base model class with common functionality.

    All models should inherit from this class to get:
    - Automatic ID generation
    - Created/updated timestamps
    - Common utility methods
    """

    __abstract__ = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary"""
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }

    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update model instance from dictionary"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def __repr__(self) -> str:
        """String representation of the model"""
        return f"<{self.__class__.__name__}(id={self.id})>"

    @classmethod
    def get_table_name(cls) -> str:
        """Get the table name for this model"""
        return cls.__tablename__


class ShopMixin:
    """Mixin for models that belong to a shop"""

    shop_id = Column(
        "shop_id", String, ForeignKey("shops.id"), nullable=False, index=True
    )

    @declared_attr
    def shop(cls):
        """Relationship to Shop model"""
        from .shop import Shop

        return None  # Will be set in the actual model


class CustomerMixin:
    """Mixin for models that belong to a customer"""

    customer_id = Column(String, nullable=True, index=True)


class ProductMixin:
    """Mixin for models that belong to a product"""

    product_id = Column(String, nullable=True, index=True)


class OrderMixin:
    """Mixin for models that belong to an order"""

    order_id = Column(String, nullable=True, index=True)


class SessionMixin:
    """Mixin for models that belong to a session"""

    session_id = Column(String, nullable=True, index=True)
