# Cross-Encoder Item Similarity Engine — Implementation Plan

## 1. Goal

Replace the `item_neighbors` stub (which always returns empty) with a two-stage retrieve-and-rerank similarity engine that powers pre-purchase recommendations (`product_page`, `cart`, `checkout_page`). Post-purchase stays on FP-Growth + popular fallback.

## 2. Architecture

```
                    ┌──────────────┐
                    │  Shopify     │
                    │  Storefront  │
                    └──────┬───────┘
                           │ POST /api/v1/recommendations
                           ▼
               ┌───────────────────────┐
               │  Python Worker        │
               │  fetch_recommendations │
               └────────┬──────────────┘
                        │ context = product_page | cart | checkout_page
                        ▼
               ┌───────────────────────┐
               │  SmartSelectionService │
               │  tries item_neighbors  │  ← was stub, now real
               └────────┬──────────────┘
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
   ┌──────────────┐          ┌──────────────────┐
   │ Stage 1:     │          │ Stage 2 (opt):    │
   │ Bi-encoder   │          │ Cross-encoder     │
   │ vector       │          │ rerank top-30     │
   │ retrieval    │          │ for post-purchase │
   │ top-30       │          │ or high-value     │
   └──────┬───────┘          │ carts             │
          │                  └────────┬─────────┘
          ▼                           │
   ┌──────────────────────────────────┘
   │
   ▼
   Return enriched results
```

### Stage 1 — Bi-encoder (fast, always-on)

- Pre-compute 384-dim dense vectors for every active product using SentenceTransformers (`all-MiniLM-L6-v2` — 34MB model, runs on CPU, 5ms per product).
- Store in new `product_vectors` table (pgvector) with an IVFFlat index.
- At query time: embed the cart/product text, cosine-similarity search against shop's product vectors, return top-30.
- Latency target: < 50ms.

### Stage 2 — Cross-encoder (optional, quality)

- Load `cross-encoder/ms-marco-MiniLM-L-6-v2` (~80MB) in the same process.
- For high-value carts ($100+) or explicit `metadata.rerank=true`, score the 30 candidates pairwise against the query item, re-rank by cross-encoder score.
- Latency target: < 500ms for 30 pairs (batched).

## 3. New Table: `product_vectors`

```python
class ProductVector(BaseModel, ShopMixin):
    """Dense vector embedding for product similarity search"""
    __tablename__ = "product_vectors"

    product_id = Column(String, nullable=False, index=True)
    vector = Column(Vector(384), nullable=False)  # pgvector column
    text_hash = Column(String, nullable=False)    # md5 of (title+desc+tags) for cache invalidation
    model_version = Column(String, nullable=False, default="all-MiniLM-L6-v2")
    updated_at = Column(TIMESTAMP(timezone=True), ...)

    __table_args__ = (
        # Composite unique: one vector per shop+product
        UniqueConstraint("shop_id", "product_id", name="uq_product_vector_shop_product"),
        # IVFFlat index for approximate nearest neighbor search
        Index("idx_product_vectors_vector", vector, postgresql_using="ivfflat",
              postgresql_with={"lists": 100}),
    )
```

**Why separate table, not ProductData column:** Zero migration risk. ProductData is large (30+ columns, JSON blobs). A separate table keeps vector lifecycle independent — rebuild vectors without touching product data.

**Why 384 dims:** MiniLM-L6 is the smallest SentenceTransformer that still beats word-vector baselines. 768-dim would require a larger model (all-mpnet-base-v2, ~420MB) for marginal gain.

## 4. New Dependencies

Add to `requirements.txt`:
```
sentence-transformers==3.4.1   # bi-encoder + cross-encoder
pgvector==0.3.6                # already installed
```

**Why not torch:** SentenceTransformers bundles its own torch. No separate install needed.

## 5. New Files

### 5.1 [`python-worker/app/recommandations/cross_encoder_service.py`](python-worker/app/recommandations/cross_encoder_service.py) — Core service

```python
class CrossEncoderService:
    """
    Two-stage item similarity engine.

    Stage 1: Bi-encoder (fast) — pre-computed dense vectors, pgvector ANN search.
    Stage 2: Cross-encoder (quality) — on-the-fly pairwise scoring for re-ranking.
    """

    # Initialization
    def __init__(self):
        self._bi_encoder: Optional[SentenceTransformer] = None   # lazy load
        self._cross_encoder: Optional[CrossEncoder] = None       # lazy load for stage 2
        self.redis_client = None
        self.config = CrossEncoderConfig()

    # Public API — called by RecommendationExecutor / SmartSelectionService
    async def get_similar_products(
        self,
        shop_id: str,
        query_product_ids: List[str],
        limit: int = 6,
        rerank: bool = False,        # True = run stage 2 cross-encoder
    ) -> Dict[str, Any]:
        """
        1. Build query text from product title+description+tags
        2. Embed query text using bi-encoder
        3. pgvector cosine-similarity search (shop-scoped)
        4. If rerank=True: cross-encoder score top-30 candidates
        5. Return top-N with scores
        """
        ...

    # Embedding management — called by normalization consumer / admin
    async def compute_and_store_embeddings(
        self, shop_id: str, product_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        1. Load product text (title+description+tags+category) from ProductData
        2. Compute md5 hash of concatenated text
        3. Skip products where hash matches cached
        4. Batch-embed new/changed products (bi-encoder, batch_size=64)
        5. UPSERT into product_vectors
        6. Return stats
        """
        ...

    # Model loading helpers
    def _get_bi_encoder(self) -> SentenceTransformer:   ...
    def _get_cross_encoder(self) -> CrossEncoder:        ...
```

### 5.2 [`python-worker/app/core/database/models/product_vector.py`](python-worker/app/core/database/models/product_vector.py)

The SQLAlchemy model for `product_vectors` table (described in §3). Register in `models/__init__.py`.

### 5.3 Configuration

Add to [`python-worker/app/core/config/settings.py`](python-worker/app/core/config/settings.py) — extend `MLSettings`:

```python
# Cross-encoder settings
CROSS_ENCODER_MODEL: str = Field(
    default="cross-encoder/ms-marco-MiniLM-L-6-v2", env="CROSS_ENCODER_MODEL"
)
BI_ENCODER_MODEL: str = Field(
    default="all-MiniLM-L6-v2", env="BI_ENCODER_MODEL"
)
CROSS_ENCODER_ENABLED: bool = Field(
    default=True, env="CROSS_ENCODER_ENABLED"
)
CROSS_ENCODER_RERANK_THRESHOLD: float = Field(
    default=100.0, env="CROSS_ENCODER_RERANK_THRESHOLD"  # cart $ threshold for auto-rerank
)
```

## 6. What Changes in Existing Code

| File | Change |
|------|--------|
| [`recommendation_executor.py`](python-worker/app/recommandations/recommendation_executor.py:64) | Replace `item_neighbors` stub: instantiate `CrossEncoderService`, call `get_similar_products()`. |
| [`hybrid.py`](python-worker/app/recommandations/hybrid.py:256) | Replace `item_neighbors` stub with same call. |
| [`models/__init__.py`](python-worker/app/core/database/models/__init__.py) | Add `ProductVector` to `__all__`. |
| [`normalization_consumer.py`](python-worker/app/consumers/kafka/normalization_consumer.py:147) | After normalization, trigger `compute_and_store_embeddings()` for the affected shop+products (alongside existing FP-Growth retraining). |
| [`requirements.txt`](python-worker/requirements.txt) | Add `sentence-transformers==3.4.1`. |

**No changes needed to:**
- `smart_selection_service.py` — it already calls `item_neighbors` via the executor, the stub replacement is transparent.
- `frequently_bought_together.py`, `fp_growth_engine.py`, `business_rules_filter.py`, `product_embeddings.py` — cross-encoder is parallel to FP-Growth, not a replacement.
- `recommendation_service.py`, `recommendations.py` — no routing changes; the `item_neighbors` level simply starts returning real results.

## 7. Pre-Purchase vs Post-Purchase Data Flow

### Pre-purchase (product_page, cart, checkout_page)

```
Request → fetch_recommendations_logic()
  → SmartSelectionService.get_smart_product_page_recommendation()
    → recommendation_executor.execute_recommendation_level("item_neighbors")
      → CrossEncoderService.get_similar_products(rerank=False)  # stage 1 only
        → embed query text
        → pgvector ANN search (shop-scoped)
        → return top-6
    → if empty: fallback to frequently_bought_together (FP-Growth)
    → if still empty: fallback to popular
```

For checkout_page (Mercury), the current direct-FBT path is unaffected — it bypasses SmartSelection. The cross-encoder only fires for `product_page` and `cart` contexts through the SmartSelection priority list.

### Post-purchase (post_purchase)

```
Request → fetch_recommendations_logic()
  → RecommendationExecutor.execute_fallback_chain("post_purchase")
    → Level 1: popular_category
    → Level 2: frequently_bought_together (FP-Growth)
    → Level 3: popular
```

Post-purchase does **not** use `item_neighbors`. No change.

## 8. Model Lifecycle

### Initial embedding (one-time per shop)
1. Shop installs → data sync → normalization completes
2. After normalization, `_trigger_fbt_retraining_if_needed()` fires → also triggers `compute_and_store_embeddings()`
3. For existing shops: admin endpoint `POST /api/v1/fbt/train/{shop_id}` already triggers full retraining; extend it to also call `compute_and_store_embeddings()`

### Incremental updates
- Each normalization event for an order causes `_trigger_fbt_retraining_if_needed()` — extend to also call `compute_and_store_embeddings()` for affected products
- Text hash check skips unchanged products (cheap md5)

### Model download at startup
- SentenceTransformer models are downloaded to HuggingFace cache on first use (~34MB for bi-encoder, ~80MB for cross-encoder)
- Docker images will need internet access on first deploy, or pre-download in a setup step
- `ponytail:` Models are cached in the container's HF cache dir. If offline deploys are needed, add a download step to Dockerfile.

## 9. Failure Modes

| Failure | Effect | Mitigation |
|---------|--------|------------|
| Model download fails | Service starts, `item_neighbors` returns empty, falls through to FBT | Log error, return empty result (existing fallback chain handles it) |
| pgvector index not created | ANN falls back to exact search (slower but correct) | Log warning; index creation is a one-time DDL |
| Embedding computation fails during normalization | Old vectors remain in `product_vectors` | Catch exception, don't block normalization |
| Cross-encoder OOM (model too large) | Fall back to bi-encoder only (stage 2 disabled) | Configurable model name; MiniLM-L6 needs ~300MB RAM |
| Product text changes (title/description update) | Stale vector until next embedding recompute | Text hash invalidates on next normalization cycle |

## 10. Validation Plan

1. **Unit tests** (file: `python-worker/tests/test_cross_encoder_service.py`)
   - Mock SentenceTransformer, verify `get_similar_products` calls the expected methods
   - Verify fallback when vectors are empty
   - Verify text hash skipping

2. **Integration test**
   - Start with 5 test products in ProductData
   - Call `compute_and_store_embeddings()` → verify `product_vectors` has 5 rows
   - Call `get_similar_products()` → verify returns results with scores
   - Verify the `item_neighbors` endpoint returns non-empty results end-to-end

3. **Manual QA**
   - Deploy to dev, trigger embedding for a shop with real products
   - Hit `/api/v1/recommendations` with `context=product_page` and `product_ids=["..."]`
   - Confirm enriched results with `source="cross_encoder"`

## 11. Order of Implementation

1. **Create `ProductVector` model** + table migration (generate via Alembic or raw SQL)
2. **Add settings** to `MLSettings`
3. **Add `sentence-transformers`** to requirements
4. **Implement `CrossEncoderService`** in `cross_encoder_service.py`
5. **Wire into `RecommendationExecutor`** — replace `item_neighbors` stub
6. **Wire into `HybridRecommendationService`** — replace `item_neighbors` stub
7. **Wire into normalization consumer** — trigger embeddings after data sync
8. **Register model** in `models/__init__.py`
9. **Run validation** — unit tests, integration test, manual QA
10. **Deploy** — ensure model download works in docker env

Steps 1-3 are independent and can be parallelized. Steps 4-8 depend on 1-3. Step 9-10 depend on all previous.

## 12. Open Questions (Deferred)

- **Should we add a `POST /api/v1/embeddings/compute` admin endpoint?** Yes, for manual trigger — add in step 6a.
- **Batch size for embedding computation:** Start with 64, tune based on GPU availability vs CPU-only.
- **pgvector index rebuild frequency:** `IVFFlat` index degrades after many UPSERTs. Rebuild nightly via cron (one `REINDEX` command).
