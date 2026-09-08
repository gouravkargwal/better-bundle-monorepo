"""
Durable state for the LLM enrichment pass.

Before this existed, enrichment output was computed, handed straight to
`resolution.py` and discarded. Two consequences:

1. Every install pass re-paid for every product — there was no idempotency,
   unlike `product_vectors` which skips on (model_version, text_hash).
2. A failed batch vanished into a log line. Nothing recorded which products
   still needed enriching, so nothing could retry them. A shop whose catalog
   went quiet after a failed install kept zero priors forever.

One row per (shop_id, product_id). The row is written PENDING before the call
and updated to SUCCEEDED or FAILED after, so work in flight is always
recoverable — a container that dies mid-pass leaves PENDING rows the re-driver
picks up rather than silent gaps.
"""

from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    UniqueConstraint,
    Index,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from .base import BaseModel, ShopMixin
from .enums import EnrichmentStatus

# How many times a product is retried before it is left alone. Past this the
# row is a dead letter: still queryable, no longer re-driven, so one poison
# product cannot stall a catalog or burn quota indefinitely.
MAX_ENRICHMENT_ATTEMPTS = 4


class ProductEnrichment(BaseModel, ShopMixin):
    """Persisted LLM enrichment for one product, with its retry state."""

    __tablename__ = "product_enrichments"

    product_id = Column(String, nullable=False, index=True)

    status = Column(
        SQLEnum(EnrichmentStatus, name="enrichment_status_enum"),
        nullable=False,
        default=EnrichmentStatus.PENDING,
        # `.name`, not `.value`: SQLAlchemy stores enum *member names* in the
        # Postgres type by default, which is the convention the billing enums
        # already follow. Using .value here produced a server default of
        # "pending" against a type containing only "PENDING".
        server_default=EnrichmentStatus.PENDING.name,
        index=True,
    )

    # Idempotency, mirroring product_vectors: a product whose text and model
    # are unchanged is skipped rather than re-sent to the API.
    text_hash = Column(String(32), nullable=False)
    model_version = Column(String(100), nullable=False)

    # The validated ProductEnrichment payload from enrichment.py. Kept so
    # resolution can re-run — re-resolving after a threshold change must not
    # require paying for the LLM again.
    payload = Column(JSONB, nullable=True)

    attempts = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Failed attempts so far; at MAX_ENRICHMENT_ATTEMPTS it is a dead letter",
    )
    last_error = Column(Text, nullable=True)
    last_attempt_at = Column(TIMESTAMP(timezone=True), nullable=True)
    succeeded_at = Column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "shop_id", "product_id", name="uq_product_enrichment_shop_product"
        ),
        # The re-driver's query: what still needs work, oldest first.
        Index(
            "idx_product_enrichments_retryable",
            "shop_id",
            "status",
            "attempts",
        ),
    )

    @property
    def is_dead_letter(self) -> bool:
        return (
            self.status == EnrichmentStatus.FAILED
            and self.attempts >= MAX_ENRICHMENT_ATTEMPTS
        )

    def __repr__(self) -> str:
        return (
            f"<ProductEnrichment(shop_id={self.shop_id}, "
            f"product_id={self.product_id}, status={self.status}, "
            f"attempts={self.attempts})>"
        )
