"""
Tests for the LLM enrichment pass.

Uses StaticProvider so nothing here calls a model. What matters is that bad
model output cannot corrupt the catalog: hallucinated products are dropped,
malformed JSON is retried once then abandoned, and a failed batch degrades
to embedding-only priors instead of failing the install.
"""

import json

import pytest

from app.recommandations.edges.enrichment import (
    BATCH_SIZE,
    MAX_COMPLEMENT_CATEGORIES,
    SYSTEM_PROMPT,
    EnrichmentService,
    ProductEnrichment,
)
from app.recommandations.edges.llm_provider import StaticProvider

PRODUCTS = [
    {"product_id": "p1", "title": "Yoga Mat", "product_type": "Mats", "price": 60},
    {"product_id": "p2", "title": "Shaker Bottle", "product_type": "Bottles", "price": 12},
]


def _response(*objs):
    return json.dumps(list(objs))


def _obj(pid, **kw):
    return {
        "product_id": pid,
        "category_path": "fitness > yoga",
        "role": "durable",
        "complement_categories": [
            {"category": "yoga blocks and props", "strength": 0.9, "reason": "used together"}
        ],
        **kw,
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enriches_a_batch_into_validated_objects():
    provider = StaticProvider([_response(_obj("p1"), _obj("p2"))])
    out = await EnrichmentService(provider).enrich_batch(PRODUCTS)
    assert [e.product_id for e in out] == ["p1", "p2"]
    assert out[0].complement_categories[0].category == "yoga blocks and props"


@pytest.mark.asyncio
async def test_the_system_prompt_forbids_inventing_product_names():
    """The whole design rests on getting categories, not SKUs."""
    assert "Do NOT invent product names" in SYSTEM_PROMPT
    assert "CATEGORY DESCRIPTIONS" in SYSTEM_PROMPT
    # And it must separate complements from substitutes, or substitutes get
    # recommended instead of excluded.
    assert "Never put a substitute in complement_categories" in SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_prompt_carries_only_the_fields_the_model_needs():
    provider = StaticProvider([_response(_obj("p1"), _obj("p2"))])
    svc = EnrichmentService(provider)
    await svc.enrich_batch(PRODUCTS)
    sent = provider.calls[0]["user"]
    assert "Yoga Mat" in sent and "p1" in sent
    assert provider.calls[0]["system"] == SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_long_descriptions_are_truncated():
    """Shipping tables and size charts are not merchandising signal."""
    provider = StaticProvider([_response(_obj("p1"))])
    svc = EnrichmentService(provider)
    await svc.enrich_batch([{"product_id": "p1", "description": "x" * 5000}])
    assert len(provider.calls[0]["user"]) < 1500


# ---------------------------------------------------------------------------
# Bad model output must not corrupt the catalog
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hallucinated_products_are_dropped():
    """A product id we never asked about would get priors for a SKU that does
    not exist in the shop."""
    provider = StaticProvider([_response(_obj("p1"), _obj("does-not-exist"))])
    out = await EnrichmentService(provider).enrich_batch(PRODUCTS)
    assert [e.product_id for e in out] == ["p1"]


@pytest.mark.asyncio
async def test_duplicate_products_in_one_response_are_deduplicated():
    provider = StaticProvider([_response(_obj("p1"), _obj("p1"))])
    out = await EnrichmentService(provider).enrich_batch(PRODUCTS)
    assert [e.product_id for e in out] == ["p1"]


@pytest.mark.asyncio
async def test_markdown_fences_are_stripped():
    fenced = "```json\n" + _response(_obj("p1")) + "\n```"
    out = await EnrichmentService(StaticProvider([fenced])).enrich_batch(PRODUCTS)
    assert out[0].product_id == "p1"


@pytest.mark.asyncio
async def test_a_wrapped_array_is_accepted():
    wrapped = json.dumps({"products": [_obj("p1")]})
    out = await EnrichmentService(StaticProvider([wrapped])).enrich_batch(PRODUCTS)
    assert out[0].product_id == "p1"


@pytest.mark.asyncio
async def test_unparseable_output_is_retried_exactly_once_then_raises():
    provider = StaticProvider(["not json", "still not json"])
    with pytest.raises(ValueError, match="unparseable after retry"):
        await EnrichmentService(provider).enrich_batch(PRODUCTS)
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_a_retry_that_succeeds_is_used():
    provider = StaticProvider(["truncated {", _response(_obj("p1"))])
    out = await EnrichmentService(provider).enrich_batch(PRODUCTS)
    assert out[0].product_id == "p1"
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_an_empty_matching_response_is_treated_as_a_failure():
    """Silently accepting zero enrichments would leave the shop cold with
    nothing in the logs to explain why."""
    provider = StaticProvider([_response(_obj("other")), _response(_obj("other"))])
    with pytest.raises(ValueError):
        await EnrichmentService(provider).enrich_batch(PRODUCTS)


# ---------------------------------------------------------------------------
# Catalog-level behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_failed_batch_does_not_fail_the_whole_install():
    """Those products fall back to embedding-only priors; the rest still ship."""
    good = _response(_obj("p1"))
    provider = StaticProvider([good, "bad", "bad again"])
    svc = EnrichmentService(provider, batch_size=1)
    out = await svc.enrich_catalog(PRODUCTS)
    assert [e.product_id for e in out] == ["p1"]


@pytest.mark.asyncio
async def test_catalog_is_split_into_batches_of_the_configured_size():
    products = [{"product_id": f"p{i}", "title": f"t{i}"} for i in range(5)]
    provider = StaticProvider([_response(_obj(f"p{i}")) for i in range(5)])
    svc = EnrichmentService(provider, batch_size=1)
    out = await svc.enrich_catalog(products)
    assert len(provider.calls) == 5
    assert len(out) == 5


def test_default_batch_size_keeps_a_2000_sku_catalog_to_100_calls():
    assert BATCH_SIZE == 20
    assert (2000 + BATCH_SIZE - 1) // BATCH_SIZE == 100


# ---------------------------------------------------------------------------
# Schema normalisation
# ---------------------------------------------------------------------------


def test_unknown_role_and_tier_fall_back_to_safe_defaults():
    e = ProductEnrichment.model_validate(
        {"product_id": "p", "role": "WIDGET", "price_tier": "nonsense"}
    )
    assert e.role == "durable"
    assert e.price_tier == "mid"


def test_replenish_days_is_stripped_from_non_consumables():
    """Otherwise resolution writes a refill self-edge for a durable good."""
    e = ProductEnrichment.model_validate(
        {"product_id": "p", "role": "durable", "replenish_days": 14}
    )
    assert e.replenish_days is None


def test_complement_categories_are_capped_and_sorted_by_strength():
    cats = [
        {"category": f"category {i}", "strength": i / 10}
        for i in range(1, MAX_COMPLEMENT_CATEGORIES + 4)
    ]
    e = ProductEnrichment.model_validate(
        {"product_id": "p", "complement_categories": cats}
    )
    assert len(e.complement_categories) == MAX_COMPLEMENT_CATEGORIES
    strengths = [c.strength for c in e.complement_categories]
    assert strengths == sorted(strengths, reverse=True)


def test_out_of_range_strength_is_rejected():
    with pytest.raises(Exception):
        ProductEnrichment.model_validate(
            {
                "product_id": "p",
                "complement_categories": [{"category": "ab", "strength": 5}],
            }
        )
