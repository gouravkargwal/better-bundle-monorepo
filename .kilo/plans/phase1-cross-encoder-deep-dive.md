# Phase 1 Deep Dive — Cross-Encoder Semantic Similarity

## The Problem in One Sentence

The `item_neighbors` level (which [`SmartSelectionService`](python-worker/app/recommandations/smart_selection_service.py:32) tries FIRST for product_page and cart) has been a stub since day one:
```python
# Line 64 of recommendation_executor.py
if level == "item_neighbors":
    # Cross-encoder to be added later; return empty for now
    return {"success": False, "items": [], "source": "item_neighbors_pending"}
```

Every recommendation request for product_page or cart pays the cost of an async call that always returns empty, then falls through to FP-Growth or `popular`. For Mercury (checkout), the code doesn't even try `item_neighbors` — it goes straight to FBT using only the FIRST cart item. For Apollo (post-purchase), it goes straight to `popular_category`.

**Phase 1 replaces this stub with a real semantic similarity engine** that understands what products "go together" based on their descriptions, titles, and categories — not just purchase co-occurrence.

## What Phase 1 Actually Builds

```
Two models from the same OSS library (sentence-transformers):

                   ┌─────────────────────────────────────┐
                   │         Phase 1 Builds               │
                   │                                     │
                   │  ┌─────────────────────────────────┐ │
                   │  │ CrossEncoderService             │ │
                   │  │ (python-worker/app/recommandations/ │
                   │  │  cross_encoder_service.py)       │ │
                   │  └─────────────────────────────────┘ │
                   │            │                          │
                   │     ┌──────┴──────┐                   │
                   │     ▼             ▼                    │
                   │ ┌─────────┐ ┌──────────┐              │
                   │ │Stage 1a │ │ Stage 1b │              │
                   │ │Bi-encdr │ │Cross-enc │              │
                   │ │Always on│ │ Optional │              │
                   │ │Retrieval│ │ Re-rank  │              │
                   │ └─────────┘ └──────────┘              │
                   └─────────────────────────────────────┘
```

### Stage 1a — Bi-encoder Retrieval (The Big Leap)

**What it does:** Converts every product into a 384-dimensional vector (a "semantic fingerprint") that captures the meaning of its title, description, and category. When a request comes in with cart items (or purchased items), it embeds those too, then finds the nearest neighbors by cosine similarity.

**OSS library:** [`sentence-transformers`](https://www.sbert.net/) — specifically the `all-MiniLM-L6-v2` model.

**Why this model:**
- 34MB download, runs on CPU in ~5ms per product
- 384 dimensions (small enough for pgvector to index efficiently)
- Beats word-vector approaches (Word2Vec/GloVe) on semantic similarity benchmarks by 15-20 points
- No GPU needed, no API calls, no external service

**How vectors are computed:**
```
Product text = f"{title} {description} {category} {tags}"
             → SentenceTransformer model
             → [0.23, -0.56, 0.89, ...]  (384 floats)
```

**How retrieval works:**
```
Request with cart items [A, B, C]:
  1. vec(A) = embed("Organic Cotton T-Shirt ...")
  2. vec(B) = embed("Slim Fit Jeans ...")
  3. avg_vec = average(vec(A), vec(B), vec(C))
  4. SQL: SELECT product_id FROM product_vectors
           WHERE shop_id = 'shop_123'
           ORDER BY vector <=> avg_vec  # cosine distance
           LIMIT 30
  5. Return 30 candidate product IDs with similarity scores
```

**Storage:** New [`product_vectors`](python-worker/app/core/database/models/product_vector.py) table with pgvector's `IVFFlat` index — approximate nearest neighbor search in milliseconds.

### Stage 1b — Cross-encoder Re-rank (Quality Boost)

**What it does:** Takes the 30 candidates from Stage 1a and scores each pair `(query_item, candidate)` through a transformer that processes both texts simultaneously — more accurate than cosine similarity but slower.

**OSS library:** Same `sentence-transformers` package, `cross-encoder/ms-marco-MiniLM-L-6-v2` model.

**Why not use this for everything:** A cross-encoder scores ONE pair at a time. For 30 candidates × 3 query items = 90 forward passes at ~10ms each = ~900ms. Too slow for checkout. But for post-purchase (async-loaded thank-you page), that's fine.

**Where it fires:**
- Mercury (checkout): **Never** — Stage 1a only, need <100ms
- Apollo (post-purchase): **Optional** — Stage 1a + 1b if configured, since latency isn't critical

## How Phase 1 Changes Each Surface

### Mercury (checkout_page) — Before vs After

**Before (current):**
```python
# recommendations.py:369-440
cart_items = request.product_ids  # ← FIRST cart item only
primary_product = cart_items[0]   # ← ignores items 2, 3, 4
result = await fbt_service.get_frequently_bought_together(
    shop_id=shop.id,
    product_id=primary_product,  # ← single item
    limit=request.limit,
)
# If FBT fails: fallback to popular_category → popular
```

**After Phase 1:**
```python
# New pipeline for checkout_page
result = await cross_encoder_service.get_similar_products(
    shop_id=shop.id,
    query_items=request.product_ids,  # ← ALL cart items
    limit=request.limit,
    rerank=False,  # ← Stage 1a only (fast)
)
# If cross-encoder returns items: return them
# If cross-encoder fails: fallback to FBT → popular (existing chain)
```

**Improvement:**
- Uses ALL cart items instead of just the first
- Finds products semantically similar to what's in cart (complements, not just co-purchases)
- ~50ms added latency vs current ~200ms FBT query

### Apollo (post-purchase) — Before vs After

**Before (current):**
```python
# recommendation_executor.py:339-343
"post_purchase": [
    "popular_category",         # ← starts with generic popular
    "frequently_bought_together",
    "popular",
]
```

**After Phase 1:**
```python
# New pipeline for post_purchase
result = await cross_encoder_service.get_similar_products(
    shop_id=shop.id,
    query_items=request.product_ids,  # ← purchased products
    limit=request.limit,
    rerank=True,  # ← Stage 1b (quality) — post-purchase can wait ~400ms
)
# If cross-encoder fails: fallback to FBT → popular (existing chain)
```

**Improvement:**
- Uses purchased products as query (not generic "popular")
- Cross-encoder re-ranks for higher quality
- Results are semantically relevant to what was just bought

## What Actually Ships (Code + Config)

### New file: [`cross_encoder_service.py`](python-worker/app/recommandations/cross_encoder_service.py)
~250 lines. Core logic:

```python
class CrossEncoderService:
    """Two-stage item similarity using SentenceTransformers + pgvector"""

    # Model loading (lazy, first-call)
    _bi_encoder = None  # all-MiniLM-L6-v2
    _cross_encoder = None  # ms-marco-MiniLM-L-6-v2

    async def get_similar_products(
        self, shop_id, query_items, limit=6, rerank=False
    ) -> Dict:
        """Main entry point. Stage 1a ± Stage 1b."""

    async def compute_and_store_embeddings(
        self, shop_id, product_ids=None
    ) -> Dict:
        """Batch-embed all (or specific) products. Called on data sync."""

    def _embed_text(self, text: str) -> List[float]:
        """Bi-encoder inference. 5ms per product."""

    async def _pgvector_search(
        self, shop_id, query_vector, limit
    ) -> List[tuple]:
        """ANN search via pgvector IVFFlat index. <10ms."""
```

### New file: [`product_vector.py`](python-worker/app/core/database/models/product_vector.py)
~40 lines. SQLAlchemy model:

```python
class ProductVector(BaseModel, ShopMixin):
    __tablename__ = "product_vectors"

    product_id = Column(String, nullable=False, index=True)
    vector = Column(Vector(384), nullable=False)  # pgvector type
    text_hash = Column(String(16), nullable=False)  # md5 of input text
    model_version = Column(String, default="all-MiniLM-L6-v2")
```

### Modified file: [`recommendation_executor.py`](python-worker/app/recommandations/recommendation_executor.py)
Change 3 lines:

```python
# Line 64 — was:
if level == "item_neighbors":
    return {"success": False, "items": [], "source": "item_neighbors_pending"}

# Line 64 — becomes:
if level == "item_neighbors":
    result = await self.cross_encoder.get_similar_products(
        shop_id=shop_id,
        query_items=product_ids or cart_items,
        limit=limit,
        rerank=(metadata or {}).get("rerank", False),
    )
    return result
```

### Modified file: [`hybrid.py`](python-worker/app/recommandations/hybrid.py)
Same 3-line change at line 256.

### Modified file: [`recommendations.py`](python-worker/app/api/v1/recommendations.py)
Replace the Mercury checkout_page handler (lines 369-440) with a pipeline that:
1. Tries cross-encoder first (with ALL cart items)
2. Falls back to existing FBT → popular chain

### Modified file: [`normalization_consumer.py`](python-worker/app/consumers/kafka/normalization_consumer.py)
Add one call after existing FP-Growth retraining:

```python
# After line 202 — alongside existing FP-Growth training:
asyncio.create_task(
    self._update_product_embeddings(fbt_service, shop_id)
)
```

### New dependency in [`requirements.txt`](python-worker/requirements.txt)
One line:
```
sentence-transformers==3.4.1
```
(Already have `pgvector`, `numpy`, `sqlalchemy` — no other new deps.)

## What DOESN'T Change

| Component | Status | Why |
|-----------|--------|-----|
| [`FPGrowthEngine`](python-worker/app/recommandations/fp_growth_engine.py) | Unchanged | Still the FBT source — cross-encoder is additive, not a replacement |
| [`BusinessRulesFilter`](python-worker/app/recommandations/business_rules_filter.py) | Unchanged | Still filters price, inventory, category |
| [`ProductEmbeddingsService`](python-worker/app/recommandations/product_embeddings.py) | Unchanged | This is the OLD Word2Vec-based system. Phase 1's cross-encoder REPLACES it for similarity queries, but we leave the code in case FP-Growth still references it. |
| [`HoldoutService`](python-worker/app/services/holdout_service.py) | Unchanged | Incrementality measurement stays intact |
| `offer_impressions` table + outcome API | Unchanged | Still tracks what's shown and accepted |
| All other recommendation files | Unchanged | enrichment.py, cache.py, exclusion_service.py, etc. |

## Why Phase 1 Alone is Worth It

| Metric | Before Phase 1 | After Phase 1 | Impact |
|--------|---------------|---------------|--------|
| item_neighbors result | Always empty | Returns top-6 similar products | Unlock primary recommendation slot |
| Mercury uses | First cart item only | ALL cart items | More relevant suggestions |
| Apollo starts with | "Popular in category" | "Similar to what you bought" | Higher relevance |
| Semantic understanding | Purchase co-occurrence only | Title + description + category | Understands NEW products |
| Latency added | 0 (stub) | ~50ms (Mercury) / ~400ms (Apollo) | Acceptable for both surfaces |
| New dependencies | — | sentence-transformers (~34MB model) | One pip install |
| Code to write | — | ~300 lines total | ~2 days dev time |

## The 300 Lines That Ship

```
python-worker/
  app/
    recommandations/
      cross_encoder_service.py      ← NEW  (~200 lines)
    core/
      database/
        models/
          product_vector.py          ← NEW  (~40 lines)
          __init__.py                ← Edit (+1 import)
    api/
      v1/
        recommendations.py           ← Edit (~30 lines, Mercury path)
    consumers/
      kafka/
        normalization_consumer.py    ← Edit (~5 lines)
  requirements.txt                   ← Edit (+1 line)

app/
  recommandations/
    recommendation_executor.py       ← Edit (~10 lines)
    hybrid.py                        ← Edit (~3 lines)
```

## One-Question Qualification

Is `sentence-transformers` (Apache 2.0 license) acceptable as a dependency? If yes, Phase 1 is ~2 days of implementation. If you'd rather avoid any new dependency and use what's already in the stack, I can show you how to do the same thing using the existing `product_embeddings.py` (Word2Vec) which is already installed — you'd just need to change the text representation from purchase-sequences to product-title+description, and switch from in-memory similarity to pgvector. That's even fewer lines, but the quality won't be as high as a transformer model.
