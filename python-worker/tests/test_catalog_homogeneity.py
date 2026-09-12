"""
Picking a prior strategy from the shape of the catalog, and the style pairing
that a uniform catalog gets instead of category complements.

Worth real tests because every branch is expensive in a different direction:
pairing on style in a varied shop throws away the complement signal, pairing on
category in an art shop produces arbitrary edges, and skipping priors on a shop
with no history leaves an empty widget.
"""

import numpy as np
import pytest

from app.recommandations.edges.enrichment import ProductEnrichment
from app.recommandations.edges.install import (
    HOMOGENEITY_MIN_PRODUCTS,
    HOMOGENEITY_THRESHOLD,
    prior_mode,
)
from app.recommandations.edges.resolution import (
    STYLE_MATCHES,
    STYLE_PRIOR_WEIGHT,
    CategoryResolver,
)

BIG = HOMOGENEITY_MIN_PRODUCTS + 10
UNIFORM = HOMOGENEITY_THRESHOLD + 0.1
VARIED = HOMOGENEITY_THRESHOLD - 0.3


# ---------- which prior strategy ----------


def test_varied_catalog_uses_categories():
    assert prior_mode(VARIED, BIG, observed_pairs=500) == "categories"


def test_uniform_catalog_without_history_pairs_on_style():
    """The wall-art shop on install day: style is the only real signal."""
    assert prior_mode(UNIFORM, BIG, observed_pairs=0) == "style"


def test_uniform_catalog_with_history_needs_no_priors():
    assert prior_mode(UNIFORM, BIG, observed_pairs=500) == "none"


def test_small_catalog_uses_categories():
    """Ten near-identical products are not a ranking problem."""
    assert prior_mode(UNIFORM, HOMOGENEITY_MIN_PRODUCTS - 1, 500) == "categories"


def test_unknown_similarity_uses_categories():
    """No vectors to measure means unknown, which is not the same as uniform."""
    assert prior_mode(None, BIG, observed_pairs=500) == "categories"


# ---------- style pairing ----------


class _FakeResolver(CategoryResolver):
    """Resolver with canned embeddings and no database.

    The behaviour under test is which products get paired and how they are
    scored, not sentence-transformers and not Postgres.
    """

    def __init__(self, vectors):
        super().__init__()
        self._vectors = vectors
        self.persisted = None

    def embed(self, texts):
        return [self._vectors[t] for t in texts]

    async def persist(self, edges):
        self.persisted = edges
        return len(edges)


def _enrichment(pid: str, descriptor: str) -> ProductEnrichment:
    return ProductEnrichment(product_id=pid, style_descriptor=descriptor)


@pytest.mark.asyncio
async def test_style_pairing_matches_like_with_like():
    """Two gold prints pair with each other, not with the black-and-white one."""
    vectors = {
        "warm gold abstract": [1.0, 0.0, 0.0],
        "warm gold minimal": [0.99, 0.1, 0.0],
        "black and white portrait": [0.0, 0.0, 1.0],
    }
    resolver = _FakeResolver(vectors)
    await resolver.resolve_style_affinity(
        "shop-1",
        [
            _enrichment("gold-a", "warm gold abstract"),
            _enrichment("gold-b", "warm gold minimal"),
            _enrichment("mono", "black and white portrait"),
        ],
    )

    pairs = {
        (e["source_product_id"], e["target_product_id"])
        for e in resolver.persisted
    }
    assert ("gold-a", "gold-b") in pairs
    assert ("gold-b", "gold-a") in pairs
    # The mono print is orthogonal to both golds, so it falls under the floor.
    assert not any("mono" in p for p in pairs)


@pytest.mark.asyncio
async def test_style_pairing_never_recommends_the_product_itself():
    """Self-similarity is 1.0 and would otherwise win every slot."""
    vectors = {f"d{i}": list(np.eye(4, dtype=float)[i % 4]) for i in range(4)}
    resolver = _FakeResolver(vectors)
    await resolver.resolve_style_affinity(
        "shop-1", [_enrichment(f"p{i}", f"d{i}") for i in range(4)]
    )
    assert all(
        e["source_product_id"] != e["target_product_id"]
        for e in resolver.persisted
    )


@pytest.mark.asyncio
async def test_style_prior_is_damped_below_a_real_complement():
    """A style match must never outscore a confident category complement."""
    vectors = {"a": [1.0, 0.0], "b": [1.0, 0.0]}
    resolver = _FakeResolver(vectors)
    await resolver.resolve_style_affinity(
        "shop-1", [_enrichment("p1", "a"), _enrichment("p2", "b")]
    )
    # Identical descriptors: similarity 1.0, the strongest a style edge can be.
    assert max(e["prior_score"] for e in resolver.persisted) == pytest.approx(
        STYLE_PRIOR_WEIGHT
    )


@pytest.mark.asyncio
async def test_style_pairing_caps_neighbours():
    vectors = {f"d{i}": [1.0, i * 0.001] for i in range(STYLE_MATCHES + 5)}
    resolver = _FakeResolver(vectors)
    await resolver.resolve_style_affinity(
        "shop-1",
        [_enrichment(f"p{i}", f"d{i}") for i in range(STYLE_MATCHES + 5)],
    )
    per_source = {}
    for e in resolver.persisted:
        per_source[e["source_product_id"]] = (
            per_source.get(e["source_product_id"], 0) + 1
        )
    assert max(per_source.values()) == STYLE_MATCHES


@pytest.mark.asyncio
async def test_style_pairing_needs_two_descriptors():
    """A catalog the model gave no descriptors for writes nothing, not junk."""
    resolver = _FakeResolver({})
    assert await resolver.resolve_style_affinity(
        "shop-1", [_enrichment("p1", ""), _enrichment("p2", "  ")]
    ) == 0
    assert resolver.persisted is None
