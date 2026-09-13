"""
Product Vector model for pgvector-based semantic similarity search

Stores 1408-dim multimodal embeddings for every active product.
Used for ANN similarity retrieval against Google Vertex multimodal embeddings.
"""

from sqlalchemy import Column, String, UniqueConstraint, Index
from pgvector.sqlalchemy import Vector
from .base import BaseModel, ShopMixin


class ProductVector(BaseModel, ShopMixin):
    """Dense vector embedding for semantic product similarity"""

    __tablename__ = "product_vectors"

    product_id = Column(String, nullable=False, index=True)
    vector = Column(Vector(1408), nullable=False)
    # We now hash the Image URL (or image bytes) AND the text, not just text
    text_hash = Column(String(32), nullable=False)
    model_version = Column(
        String, nullable=False, default="multimodalembedding"
    )

    __table_args__ = (
        UniqueConstraint(
            "shop_id", "product_id", name="uq_product_vector_shop_product"
        ),
        # Upgrade from ivfflat to HNSW for high-dimensional performance
        Index(
            "idx_product_vectors_vector",
            vector,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"vector": "vector_cosine_ops"},
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ProductVector(shop_id={self.shop_id}, "
            f"product_id={self.product_id}, "
            f"model={self.model_version})>"
        )
