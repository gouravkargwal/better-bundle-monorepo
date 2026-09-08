"""
Persistence and retry bookkeeping for the LLM enrichment pass.

`enrichment.py` deliberately knows nothing about the database — it turns
catalog rows into validated objects or raises. This module is the other half:
it decides which products still need an LLM call, records the outcome of each
one, and hands back the stored payloads so resolution can run without paying
for the model again.

The contract in one line: never call the LLM for work already done, and never
lose work that failed.
"""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import select, and_, or_, func, update, case, text

from app.core.database.models import (
    EnrichmentStatus,
    ProductEnrichment as ProductEnrichmentRow,
    MAX_ENRICHMENT_ATTEMPTS,
)
from app.core.database.session import get_transaction_context
from app.shared.helpers import now_utc

from .enrichment import DESCRIPTION_CHARS, ProductEnrichment
from .llm_budget import classify

logger = logging.getLogger(__name__)


def enrichment_input_hash(product: Dict[str, Any]) -> str:
    """Fingerprint of exactly the fields that reach the prompt.

    Must cover the same inputs as `EnrichmentService.build_prompt`, or a
    product whose title changed would be considered up to date and never
    re-enriched. Tags are sorted so a reordering from Shopify is not mistaken
    for a real edit.
    """
    tags = product.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    body = json.dumps(
        {
            "title": product.get("title") or "",
            "product_type": product.get("product_type") or "",
            "vendor": product.get("vendor") or "",
            "tags": sorted(str(t) for t in list(tags)[:12]),
            "price": str(product.get("price")),
            "description": (product.get("description") or "")[:DESCRIPTION_CHARS],
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.md5(body.encode()).hexdigest()


class EnrichmentStore:
    """Reads and writes `product_enrichments`."""

    def __init__(self, model_version: str):
        self.model_version = model_version

    async def partition(
        self, shop_id: str, products: Sequence[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[ProductEnrichment], int]:
        """Split the catalog into work to do, work already done, and dead letters.

        Returns (to_enrich, already_enriched, dead_lettered).

        A product is skipped when a SUCCEEDED row exists for the same input
        hash and model version. It is dead-lettered when it has failed
        MAX_ENRICHMENT_ATTEMPTS times — still visible in the table, but no
        longer re-driven, so a product the model consistently chokes on cannot
        stall the catalog or burn quota forever.
        """
        by_id = {str(p.get("product_id")): p for p in products}

        async with get_transaction_context() as session:
            rows = (
                (
                    await session.execute(
                        select(ProductEnrichmentRow).where(
                            and_(
                                ProductEnrichmentRow.shop_id == shop_id,
                                ProductEnrichmentRow.product_id.in_(list(by_id.keys())),
                            )
                        )
                    )
                )
                .scalars()
                .all()
            )

        existing = {r.product_id: r for r in rows}

        to_enrich: List[Dict[str, Any]] = []
        done: List[ProductEnrichment] = []
        dead = 0

        for pid, product in by_id.items():
            digest = enrichment_input_hash(product)
            row = existing.get(pid)

            if (
                row is not None
                and row.status == EnrichmentStatus.SUCCEEDED
                and row.text_hash == digest
                and row.model_version == self.model_version
                and row.payload
            ):
                parsed = _load_payload(row)
                if parsed is not None:
                    done.append(parsed)
                    continue
                # A payload we can no longer validate is treated as missing
                # rather than trusted — the schema may have tightened since.
                logger.warning(
                    f"Shop {shop_id}: unreadable enrichment payload for {pid}, "
                    "re-enriching"
                )

            # Only count as dead when the stored failure is for *this* input.
            # An edited product deserves a fresh set of attempts.
            if (
                row is not None
                and row.text_hash == digest
                and row.model_version == self.model_version
                and row.attempts >= MAX_ENRICHMENT_ATTEMPTS
            ):
                dead += 1
                continue

            to_enrich.append(product)

        return to_enrich, done, dead

    async def claim(self, shop_id: str, products: Sequence[Dict[str, Any]]) -> None:
        """Write PENDING rows before any call is made.

        This is the step that makes the work recoverable: if the process dies
        mid-pass, these rows are what tells the re-driver there is unfinished
        business. Without it a crash is indistinguishable from success.
        """
        if not products:
            return

        async with get_transaction_context() as session:
            for product in products:
                pid = str(product.get("product_id"))
                digest = enrichment_input_hash(product)
                row = (
                    await session.execute(
                        select(ProductEnrichmentRow).where(
                            and_(
                                ProductEnrichmentRow.shop_id == shop_id,
                                ProductEnrichmentRow.product_id == pid,
                            )
                        )
                    )
                ).scalar_one_or_none()

                if row is None:
                    session.add(
                        ProductEnrichmentRow(
                            shop_id=shop_id,
                            product_id=pid,
                            status=EnrichmentStatus.PENDING,
                            text_hash=digest,
                            model_version=self.model_version,
                            attempts=0,
                            last_attempt_at=now_utc(),
                        )
                    )
                    continue

                # The input changed, so previous failures are not this input's
                # failures — reset the attempt count with the new hash.
                if row.text_hash != digest or row.model_version != self.model_version:
                    row.text_hash = digest
                    row.model_version = self.model_version
                    row.attempts = 0
                    row.last_error = None
                row.status = EnrichmentStatus.PENDING
                row.last_attempt_at = now_utc()

    async def record_success(
        self, shop_id: str, enrichments: Sequence[ProductEnrichment]
    ) -> int:
        """Store validated payloads and mark those products done."""
        if not enrichments:
            return 0

        written = 0
        async with get_transaction_context() as session:
            for e in enrichments:
                row = (
                    await session.execute(
                        select(ProductEnrichmentRow).where(
                            and_(
                                ProductEnrichmentRow.shop_id == shop_id,
                                ProductEnrichmentRow.product_id == e.product_id,
                            )
                        )
                    )
                ).scalar_one_or_none()
                if row is None:
                    # Claimed rows should always exist; tolerate a missing one
                    # rather than throwing away a paid-for result.
                    logger.warning(f"Shop {shop_id}: no claimed row for {e.product_id}")
                    continue
                row.status = EnrichmentStatus.SUCCEEDED
                row.payload = e.model_dump(mode="json")
                row.last_error = None
                row.succeeded_at = now_utc()
                written += 1

        return written

    async def record_failure(
        self, shop_id: str, product_ids: Sequence[str], error: str
    ) -> int:
        """Increment the attempt count and store why it failed.

        The row stays FAILED and retryable until the attempt cap, at which
        point `partition` starts skipping it. Nothing is deleted, so the
        failure is still answerable with a query.

        A permanently-failing error jumps straight to the cap. Spending four
        attempts over four hours on a request that is structurally invalid —
        a revoked key, a malformed prompt — is money for nothing.
        """
        if not product_ids:
            return 0

        permanent = not classify(RuntimeError(error or "")).retryable
        attempts_value = (
            MAX_ENRICHMENT_ATTEMPTS
            if permanent
            else ProductEnrichmentRow.attempts + 1
        )
        if permanent:
            logger.error(
                f"Shop {shop_id}: dead-lettering {len(product_ids)} products "
                f"immediately — permanent enrichment error: {error[:200]}"
            )

        async with get_transaction_context() as session:
            result = await session.execute(
                update(ProductEnrichmentRow)
                .where(
                    and_(
                        ProductEnrichmentRow.shop_id == shop_id,
                        ProductEnrichmentRow.product_id.in_(list(product_ids)),
                    )
                )
                .values(
                    status=EnrichmentStatus.FAILED,
                    attempts=attempts_value,
                    last_error=(error or "")[:2000],
                    last_attempt_at=now_utc(),
                )
            )
            return result.rowcount or 0

    async def stats(self, shop_id: str) -> Dict[str, int]:
        """Counts by status, plus how many are dead-lettered.

        This is the visibility half: "did enrichment work for this shop?"
        becomes a query instead of a log grep. The resolution bug that reported
        `servable: True` with zero priors survived precisely because there was
        nothing to ask.
        """
        async with get_transaction_context() as session:
            rows = (
                await session.execute(
                    select(
                        ProductEnrichmentRow.status,
                        func.count().label("n"),
                    )
                    .where(ProductEnrichmentRow.shop_id == shop_id)
                    .group_by(ProductEnrichmentRow.status)
                )
            ).all()

            dead = (
                await session.execute(
                    select(func.count()).where(
                        and_(
                            ProductEnrichmentRow.shop_id == shop_id,
                            ProductEnrichmentRow.status == EnrichmentStatus.FAILED,
                            ProductEnrichmentRow.attempts >= MAX_ENRICHMENT_ATTEMPTS,
                        )
                    )
                )
            ).scalar_one()

        out = {s.value: 0 for s in EnrichmentStatus}
        for status, n in rows:
            key = status.value if hasattr(status, "value") else str(status)
            out[key] = n
        out["dead_lettered"] = dead
        return out

    async def load_succeeded(self, shop_id: str) -> List[ProductEnrichment]:
        """Every stored payload for a shop, for re-resolving without the LLM."""
        async with get_transaction_context() as session:
            rows = (
                (
                    await session.execute(
                        select(ProductEnrichmentRow).where(
                            and_(
                                ProductEnrichmentRow.shop_id == shop_id,
                                ProductEnrichmentRow.status
                                == EnrichmentStatus.SUCCEEDED,
                            )
                        )
                    )
                )
                .scalars()
                .all()
            )

        out = []
        for r in rows:
            parsed = _load_payload(r)
            if parsed is not None:
                out.append(parsed)
        return out


# Backoff between attempts, indexed by attempts-so-far. Tuned for the two
# failures that actually happen: a transient timeout (worth retrying soon) and
# an exhausted daily quota (worth waiting hours, not minutes — retrying a
# quota error every minute just burns rate limit and logs).
RETRY_BACKOFF_MINUTES = (5, 30, 240)


def _retry_due_clause():
    """SQL for "enough time has passed since the last attempt".

    A PENDING row with no recorded attempt is due immediately: it means a pass
    died before it could even record a failure, and that work is simply lost
    until something picks it up.
    """
    schedule = case(
        *[
            (ProductEnrichmentRow.attempts <= i, text(f"interval '{m} minutes'"))
            for i, m in enumerate(RETRY_BACKOFF_MINUTES)
        ],
        else_=text(f"interval '{RETRY_BACKOFF_MINUTES[-1]} minutes'"),
    )
    return or_(
        ProductEnrichmentRow.last_attempt_at.is_(None),
        ProductEnrichmentRow.last_attempt_at + schedule <= now_utc(),
    )


async def shops_needing_enrichment(limit: int = 50) -> List[str]:
    """Shops with retryable enrichment work that is due now.

    The re-driver's entry point. PENDING rows mean a pass died mid-flight;
    FAILED rows under the attempt cap mean a transient error (quota, timeout)
    that deserves another go. Rows at the cap are excluded — they are dead
    letters, not work. Oldest-waiting shop first, so no shop starves.
    """
    async with get_transaction_context() as session:
        rows = (
            await session.execute(
                select(ProductEnrichmentRow.shop_id)
                .where(
                    ProductEnrichmentRow.status.in_(
                        [EnrichmentStatus.PENDING, EnrichmentStatus.FAILED]
                    ),
                    ProductEnrichmentRow.attempts < MAX_ENRICHMENT_ATTEMPTS,
                    _retry_due_clause(),
                )
                .group_by(ProductEnrichmentRow.shop_id)
                .order_by(func.min(ProductEnrichmentRow.last_attempt_at).asc())
                .limit(limit)
            )
        ).all()
    return [r.shop_id for r in rows]


async def retryable_product_ids(shop_id: str) -> List[str]:
    """The products in one shop that are due for another attempt."""
    async with get_transaction_context() as session:
        rows = (
            await session.execute(
                select(ProductEnrichmentRow.product_id).where(
                    ProductEnrichmentRow.shop_id == shop_id,
                    ProductEnrichmentRow.status.in_(
                        [EnrichmentStatus.PENDING, EnrichmentStatus.FAILED]
                    ),
                    ProductEnrichmentRow.attempts < MAX_ENRICHMENT_ATTEMPTS,
                    _retry_due_clause(),
                )
            )
        ).all()
    return [r.product_id for r in rows]


def _load_payload(row: ProductEnrichmentRow) -> Optional[ProductEnrichment]:
    try:
        return ProductEnrichment.model_validate(row.payload)
    except Exception:
        return None
