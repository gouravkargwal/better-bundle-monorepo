"""
LLM enrichment pass (plan section 4).

Runs once per product on install, then per-product on `products/update`. Output
is a structured description of what each product *is* and what categories go
with it — never specific product names.

Why categories and not SKUs
---------------------------
The model cannot see the full catalog. Asked for concrete pairings it invents
product names that do not exist in the store, and the output does not scale past
whatever fits in one prompt. Asked for *category descriptions* it does the thing
it is actually good at — retail reasoning — and `resolution.py` grounds those
categories against the merchant's real catalog by embedding similarity.

Nothing here talks to the database and nothing here embeds anything. It turns
products into validated `ProductEnrichment` objects, or raises.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence

from pydantic import BaseModel, Field, ValidationError, field_validator

from .llm_provider import LLMProvider

logger = logging.getLogger(__name__)

# Products per request. Small enough that one bad batch is cheap to retry and
# that the response stays inside a sane output budget; large enough that a
# 2,000-SKU catalog is 100 calls, not 2,000.
BATCH_SIZE = 20

# Description text sent per product. The first couple of sentences carry the
# useful signal; the rest is shipping tables and size charts.
DESCRIPTION_CHARS = 200

MAX_COMPLEMENT_CATEGORIES = 5

SYSTEM_PROMPT = """You are a retail merchandising analyst.

For each product you are given, output structured JSON describing what it is and
what categories of product are bought alongside it.

Rules:
- Do NOT invent product names. Describe complements as CATEGORY DESCRIPTIONS
  ("yoga blocks and props"), never as specific products ("Manduka Cork Block").
- A complement is something bought IN ADDITION to the product. A substitute is
  an ALTERNATIVE to it. Never put a substitute in complement_categories.
- role: "consumable" if it is used up and rebought, "durable" if bought once,
  "accessory" if it attaches to or supports another product, "apparel" for worn
  items.
- replenish_days: for consumables only, the typical number of days before a
  customer would need another. null for everything else.
- strength: 0..1, how reliably that category is bought alongside this product.
- Return ONLY a JSON array, one object per input product, in the same order.
  No markdown fences, no preamble, no trailing commentary."""


class ComplementCategory(BaseModel):
    category: str = Field(min_length=2, max_length=120)
    strength: float = Field(ge=0.0, le=1.0)
    reason: str = Field(default="", max_length=300)


class ProductEnrichment(BaseModel):
    """Validated enrichment for a single product."""

    product_id: str
    category_path: str = Field(default="", max_length=300)
    role: str = "durable"
    replenish_days: Optional[int] = Field(default=None, ge=1, le=3650)
    complement_categories: List[ComplementCategory] = Field(default_factory=list)
    substitute_category: Optional[str] = Field(default=None, max_length=120)
    use_case_tags: List[str] = Field(default_factory=list)
    price_tier: str = "mid"
    is_giftable: bool = False

    @field_validator("role")
    @classmethod
    def _known_role(cls, v: str) -> str:
        allowed = {"consumable", "durable", "accessory", "apparel"}
        v = (v or "").strip().lower()
        return v if v in allowed else "durable"

    @field_validator("price_tier")
    @classmethod
    def _known_tier(cls, v: str) -> str:
        allowed = {"budget", "mid", "premium"}
        v = (v or "").strip().lower()
        return v if v in allowed else "mid"

    @field_validator("complement_categories")
    @classmethod
    def _cap_and_sort(cls, v):
        return sorted(v, key=lambda c: c.strength, reverse=True)[
            :MAX_COMPLEMENT_CATEGORIES
        ]

    def model_post_init(self, _ctx) -> None:
        # A replenish window on a non-consumable is a model slip, and it would
        # otherwise cause `resolution.py` to write a bogus refill self-edge —
        # offering someone a second sofa a fortnight after they bought one.
        if self.role != "consumable" and self.replenish_days is not None:
            object.__setattr__(self, "replenish_days", None)


class EnrichmentService:
    """Turns catalog rows into validated enrichment objects."""

    def __init__(
        self,
        provider: LLMProvider,
        batch_size: int = BATCH_SIZE,
        concurrency: int = 4,
    ):
        self.provider = provider
        self.batch_size = batch_size
        # Bounded so a 2,000-SKU install does not open 100 simultaneous calls.
        self._semaphore = asyncio.Semaphore(concurrency)

    async def enrich_catalog(
        self, products: Sequence[Dict[str, Any]]
    ) -> List[ProductEnrichment]:
        """Enrich every product. Batches that fail are skipped, not fatal.

        A failed batch means those products fall back to embedding-only priors
        (`resolution.py` still has their vectors), so a partial LLM outage
        degrades recommendation quality instead of failing the install.
        """
        batches = list(_chunk(products, self.batch_size))
        results = await asyncio.gather(
            *(self._enrich_batch_guarded(b) for b in batches)
        )

        enriched: List[ProductEnrichment] = []
        failed = 0
        for batch, outcome in zip(batches, results):
            if outcome is None:
                failed += len(batch)
                continue
            enriched.extend(outcome)

        if failed:
            logger.warning(
                f"Enrichment: {failed}/{len(products)} products fell back to "
                f"embedding-only priors after batch failures"
            )
        logger.info(f"Enrichment: {len(enriched)}/{len(products)} products enriched")
        return enriched

    async def _enrich_batch_guarded(
        self, batch: Sequence[Dict[str, Any]]
    ) -> Optional[List[ProductEnrichment]]:
        async with self._semaphore:
            try:
                return await self.enrich_batch(batch)
            except Exception as e:
                logger.error(f"Enrichment batch failed ({len(batch)} products): {e}")
                return None

    async def enrich_batch(
        self, batch: Sequence[Dict[str, Any]]
    ) -> List[ProductEnrichment]:
        """One request. Retries once on unparseable output, then gives up.

        The retry exists because a truncated or fenced response is common and
        cheap to fix; a second failure means the batch is genuinely bad and
        retrying further just spends money.
        """
        prompt = self.build_prompt(batch)
        ids = [str(p.get("product_id")) for p in batch]

        for attempt in (1, 2):
            raw = await self.provider.complete(SYSTEM_PROMPT, prompt)
            try:
                return self.parse_response(raw, ids)
            except (ValueError, ValidationError, json.JSONDecodeError) as e:
                if attempt == 2:
                    raise ValueError(
                        f"enrichment unparseable after retry: {e}"
                    ) from e
                logger.warning(f"Enrichment parse failed, retrying once: {e}")

        raise AssertionError("unreachable")

    def build_prompt(self, batch: Sequence[Dict[str, Any]]) -> str:
        """Render the catalog rows the model should describe."""
        lines = []
        for p in batch:
            tags = p.get("tags") or []
            if isinstance(tags, str):
                tags = [tags]
            description = (p.get("description") or "")[:DESCRIPTION_CHARS]
            lines.append(
                json.dumps(
                    {
                        "product_id": str(p.get("product_id")),
                        "title": p.get("title") or "",
                        "product_type": p.get("product_type") or "",
                        "vendor": p.get("vendor") or "",
                        "tags": list(tags)[:12],
                        "price": p.get("price"),
                        "description": description,
                    },
                    ensure_ascii=False,
                )
            )
        return "Products:\n" + "\n".join(lines)

    def parse_response(
        self, raw: str, expected_ids: Sequence[str]
    ) -> List[ProductEnrichment]:
        """Validate strictly, and only accept products we actually asked about.

        The id filter matters: a model that hallucinates an extra product would
        otherwise have priors written for a SKU that does not exist in the shop.
        """
        payload = json.loads(_strip_fences(raw))
        if isinstance(payload, dict):
            # Tolerate {"products": [...]}, which the model sometimes prefers.
            payload = next(
                (v for v in payload.values() if isinstance(v, list)), None
            )
        if not isinstance(payload, list):
            raise ValueError("expected a JSON array of enrichment objects")

        wanted = set(expected_ids)
        out: List[ProductEnrichment] = []
        seen = set()
        for item in payload:
            if not isinstance(item, dict):
                continue
            pid = str(item.get("product_id") or item.get("sku") or "")
            if pid not in wanted or pid in seen:
                continue
            item = {**item, "product_id": pid}
            item.pop("sku", None)
            out.append(ProductEnrichment.model_validate(item))
            seen.add(pid)

        if not out:
            raise ValueError("no enrichment objects matched the requested products")
        return out


def _strip_fences(text: str) -> str:
    """Remove ```json fences if the model added them despite instructions."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1] if "\n" in t else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def _chunk(items: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]
