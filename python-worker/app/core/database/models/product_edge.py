"""
ProductEdge model — the serving table for recommendations.

One row per (source product, target product, edge type). Everything the request
path needs is precomputed here, so serving is an indexed lookup and never runs a
model or an LLM call.

Three scores are kept side by side rather than collapsed into one:

- `prior_score`    from LLM category enrichment resolved against this shop's
                   catalog by embedding similarity. Available on install day.
- `observed_llr`   log-likelihood ratio over real co-purchases, squashed to 0..1.
- `blended_score`  what the serve path ranks on.

Keeping the components separate is deliberate: it is the only way to answer
"did the prior actually convert?" against live data later, instead of guessing
at the blend thresholds forever.
"""

from sqlalchemy import Column, String, Integer, Float, Index, PrimaryKeyConstraint
from .base import Base, TimestampMixin

# Edge semantics.
#   complement — bought together, different need     (cross-sell)
#   accessory  — depends on the source product       (cross-sell, tighter)
#   refill     — same or equivalent item, bought again later
#   substitute — alternative to the source. NEVER recommended; used to EXCLUDE
#                lookalikes at checkout, where showing one causes swaps.
EDGE_TYPES = ("complement", "accessory", "refill", "substitute")

# Edge types that may be shown. `substitute` is deliberately absent.
RECOMMENDABLE_EDGE_TYPES = ("complement", "accessory", "refill")


class ProductEdge(Base, TimestampMixin):
    """A directed, typed relationship between two products in one shop."""

    __tablename__ = "product_edges"

    shop_id = Column(String, nullable=False)
    source_product_id = Column(String, nullable=False)
    target_product_id = Column(String, nullable=False)
    edge_type = Column(String(20), nullable=False)

    prior_score = Column(Float, nullable=False, default=0.0)
    observed_count = Column(Integer, nullable=False, default=0)
    observed_llr = Column(Float, nullable=False, default=0.0)
    blended_score = Column(Float, nullable=False, default=0.0)

    # Why the prior fired, for debugging bad recommendations against a real
    # catalog. Small: the matched category string and its cosine similarity.
    prior_reason = Column(String(500), nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint(
            "shop_id",
            "source_product_id",
            "target_product_id",
            "edge_type",
            name="pk_product_edges",
        ),
        # The serve query: given the cart's products, the best edges of a type.
        Index(
            "ix_product_edges_serve",
            "shop_id",
            "source_product_id",
            "edge_type",
            "blended_score",
        ),
        # Substitute lookups run the other way: "is anything in the cart a
        # substitute for this candidate?"
        Index(
            "ix_product_edges_target",
            "shop_id",
            "target_product_id",
            "edge_type",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ProductEdge({self.source_product_id} -{self.edge_type}-> "
            f"{self.target_product_id}, blended={self.blended_score:.3f})>"
        )
