"""
Product Vector model for pgvector-based semantic similarity search

Stores 384-dim bi-encoder embeddings for every active product.
Used by CrossEncoderService for ANN similarity retrieval (Phase 1).
"""

from sqlalchemy import Column, String, UniqueConstraint, Index
from pgvector.sqlalchemy import Vector
from .base import BaseModel, ShopMixin


class ProductVector(BaseModel, ShopMixin):
    """Dense vector embedding for semantic product similarity"""

    __tablename__ = "product_vectors"

    product_id = Column(String, nullable=False, index=True)
    vector = Column(Vector(384), nullable=False)
    text_hash = Column(String(32), nullable=False)  # md5 of input text
    model_version = Column(String, nullable=False, default="all-MiniLM-L6-v2")

    __table_args__ = (
        UniqueConstraint(
            "shop_id", "product_id", name="uq_product_vector_shop_product"
        ),
        Index(
            "idx_product_vectors_vector",
            vector,
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ProductVector(shop_id={self.shop_id}, "
            f"product_id={self.product_id}, "
            f"model={self.model_version})>"
        )
