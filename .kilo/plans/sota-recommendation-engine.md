# SOTA Recommendation Engine for Checkout + Post-Purchase Surfaces

## 1. Surfaces & Current State

| Surface | Extension | Context | When | Current Engine | Quality |
|---------|-----------|---------|------|----------------|---------|
| **Mercury** | Checkout | `checkout_page` | During payment, user sees upsells | FBT (FP-Growth) → popular_category → popular | Weak — only uses first cart item, no personalization, item_neighbors is stub |
| **Apollo** | Post-purchase | `post_purchase` | Thank-you page after payment | popular_category → FBT → popular | Weak — starts with generic popular, not what complements the just-purchased items |

### Why "popular_category" is the wrong level-1 for both

Mercury and Apollo's current fallback chains start with either FBT or popular_category. For post-purchase, the most valuable recommendation is **"what complements what the customer just bought"** (FBT/cross-sell), not "what's popular in a category." For checkout, the most valuable is **"what makes sense with what's in the cart right now"** — which could be a lower-price add-on, a complement, or an upgrade — not "what's popular."

## 2. Target Architecture — Retrieve → Rank → Explore

```
                    ┌─────────────────────────────┐
                    │      Request arrives         │
                    │  (cart_items, purchased_items,│
                    │   user_id, session_id,        │
                    │   cart_value, metadata)       │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
              ┌──────────────────────────────────────┐
              │           STAGE 1: RETRIEVE          │
              │ Collect candidates from 3 sources    │
              │                                      │
              │  ┌─────────────────────────────────┐ │
              │  │ Source A: Cross-encoder          │ │
              │  │ (semantic similarity to          │ │
              │  │  cart/purchased items)           │ │
              │  │ top-K: 30                        │ │
              │  └─────────────────────────────────┘ │
              │  ┌─────────────────────────────────┐ │
              │  │ Source B: FP-Growth / FBT       │ │
              │  │ (frequently bought together)    │ │
              │  │ top-K: 20                        │ │
              │  └─────────────────────────────────┘ │
              │  ┌─────────────────────────────────┐ │
              │  │ Source C: Real-time session      │ │
              │  │ (recently viewed, cart history,  │ │
              │  │  abandoned cart)                 │ │
              │  │ top-K: 10                        │ │
              │  └─────────────────────────────────┘ │
              │                                      │
              │  → Merge & deduplicate → 50-60       │
              │    candidate items                   │
              └──────────────────┬───────────────────┘
                                 │
                                 ▼
              ┌──────────────────────────────────────┐
              │       STAGE 2: LIGHT RANKER          │
              │                                      │
              │  Score each candidate with a         │
              │  Gradient Boosted Decision Tree      │
              │  (XGBoost/LightGBM) using features:  │
              │                                      │
              │  • FP-Growth score & lift            │
              │  • Cross-encoder similarity score    │
              │  • Category match with cart          │
              │  • Price relativity (add-on fit)     │
              │  • Product popularity (all-time)     │
              │  • Inventory status                  │
              │  • Margin (if available)             │
              │  • Seasonality score                 │
              │                                      │
              │  → Sort by score, take top-15        │
              └──────────────────┬───────────────────┘
                                 │
                                 ▼
              ┌──────────────────────────────────────┐
              │     STAGE 3: HEAVY RANKER (post-     │
              │     purchase only, async)            │
              │                                      │
              │  Cross-encoder re-rank top-15 pairs  │
              │  → re-order by cross-encoder score   │
              │                                      │
              │  ponytail: Only for post-purchase    │
              │  where latency isn't critical.       │
              │  If latency becomes an issue for     │
              │  checkout, skip this stage.          │
              └──────────────────┬───────────────────┘
                                 │
                                 ▼
              ┌──────────────────────────────────────┐
              │      STAGE 4: EXPLORE (bandit)       │
              │                                      │
              │  ε-greedy:                           │
              │  • 90% of the time: serve top-N from │
              │    Stage 2/3 ranking                 │
              │  • 10% of the time: inject 1 random  │
              │    item from a different category    │
              │    (exploration)                     │
              │                                      │
              │  Track which items get accepted/     │
              │  declined via existing outcome API.  │
              │  Update per-item Q-values daily.     │
              │                                      │
              │  ponytail: ε=0.1 is fixed. If we     │
              │  see enough volume, switch to        │
              │  Thompson sampling per shop.         │
              └──────────────────┬───────────────────┘
                                 │
                                 ▼
              ┌──────────────────────────────────────┐
              │         STAGE 5: FILTER              │
              │                                      │
              │  • Remove already-purchased items    │
              │  • Remove out-of-stock               │
              │  • Price sanity (not >3x cart value) │
              │  • Category diversity (no 3 same)    │
              │                                      │
              │  → Final N items (3 for Apollo,      │
              │    3-4 for Mercury)                  │
              └──────────────────┬───────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────────┐
                    │      Return + Log            │
                    │  • Items with scores, source  │
                    │  • Write to offer_impressions │
                    │  • Log exploration flag       │
                    └─────────────────────────────┘
```

## 3. What Changes Per Surface

### Mercury (checkout_page) — Pre-purchase

**Current flow:**
```
Request → fetch_recommendations_logic()
  → Direct call to FrequentlyBoughtTogetherService using FIRST cart item
  → If fails: custom fallback chain [popular_category, popular]
```

**New flow:**
```
Request → fetch_recommendations_logic()
  → MercuryRecommendationPipeline.execute()
    → Stage 1: Retrieve (cross-encoder + FBT + session) using ALL cart items
    → Stage 2: Light ranker (XGBoost)
    → Stage 3: SKIP (latency critical)
    → Stage 4: Explore (ε-greedy, 5% exploration)
    → Stage 5: Filter
  → Return enriched results
```

Key improvement: Uses **all cart items** for FBT query, not just the first one. The cross-encoder computes the average embedding of all cart items and finds similar products.

### Apollo (post_purchase) — Post-purchase

**Current flow:**
```
Request → recommendation_controller.get_recommendations_with_session()
  → Hardcoded context="post_purchase"
  → fetch_recommendations_logic()
    → Fallback chain: [popular_category, FBT, popular]
```

**New flow:**
```
Request → recommendation_controller.get_recommendations_with_session()
  → Hardcoded context="post_purchase"
  → fetch_recommendations_logic()
    → ApolloRecommendationPipeline.execute()
      → Stage 1: Retrieve (cross-encoder + FBT + session) using PURCHASED items
      → Stage 2: Light ranker (XGBoost)
      → Stage 3: Heavy ranker (cross-encoder re-rank top-15)
      → Stage 4: Explore (ε-greedy, 10% exploration)
      → Stage 5: Filter
  → Return enriched results
```

Key improvement: Uses **purchased products** (not cart items) as the query. Cross-encoder re-ranks top candidates for quality (latency not critical on thank-you page).

## 4. New Components

### File: `python-worker/app/recommandations/retrieval_fusion.py`
```python
class RetrievalFusionService:
    """
    Stage 1: Retrieve candidates from multiple sources, merge, deduplicate.
    
    Sources:
    - CrossEncoderService (semantic similarity)
    - FPGrowthEngine (frequently bought together)
    - SessionDataService (recent views, cart history)
    """
    
    async def retrieve_candidates(
        self,
        shop_id: str,
        query_items: List[str],     # cart items (Mercury) or purchased items (Apollo)
        user_id: Optional[str],
        session_id: Optional[str],
        surface: str,               # "mercury" | "apollo"
        limit: int = 60,
    ) -> List[CandidateItem]:
        ...
```

### File: `python-worker/app/recommandations/ranker.py`
```python
class LightRanker:
    """
    Stage 2: Score candidates with a GBDT model.
    
    Features (computed per (shop, query_items, candidate_item)):
    - fp_growth_score, fp_growth_lift, fp_growth_confidence
    - cross_encoder_similarity
    - category_match (1 if same category as any query item, 0.5 if sibling, 0 otherwise)
    - price_ratio (candidate_price / avg_query_price)
    - global_popularity (purchase count rank)
    - inventory_status (in_stock=1, low=0.5, out=0)
    - margin (if available)
    - seasonality_score (0-1)
    - recency_days (days since last purchase of this item)
    """
    
    async def score(
        self,
        candidates: List[CandidateItem],
        context: RankingContext,
    ) -> List[ScoredItem]:
        ...
    
    async def train(
        self,
        shop_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, Any]:
        """
        Train XGBoost model on historical offer_impressions data.
        
        Target: outcome (accepted=1, declined/shown=0)
        Features: the 9 features above
        """
        ...
```

### File: `python-worker/app/recommandations/exploration_service.py`
```python
class ExplorationService:
    """
    Stage 4: ε-greedy bandit for exploration.
    
    Tracks which items get accepted/declined per shop.
    Maintains Q-values in Redis (shop_id → item_id → accept_rate, n).
    """
    
    def should_explore(self, shop_id: str, epsilon: float = 0.1) -> bool: ...
    def pick_exploration_item(
        self, candidates: List[str], excluded: List[str]
    ) -> Optional[str]: ...
    async def record_outcome(
        self, shop_id: str, item_id: str, accepted: bool
    ) -> None: ...
    async def get_best_items(
        self, shop_id: str, limit: int = 20
    ) -> List[str]: ...
```

### File: `python-worker/app/core/database/models/product_vector.py`
(From previous cross-encoder plan — pgvector table for bi-encoder embeddings.)

## 5. What Changes in Existing Code

| File | Change |
|------|--------|
| [`recommendation_executor.py`](python-worker/app/recommandations/recommendation_executor.py) | Replace `item_neighbors` stub with real cross-encoder call. Add `checkout` and `post_purchase` fallback chain to use new pipeline instead of old fallback chain. |
| [`recommendations.py`](python-worker/app/api/v1/recommendations.py) | Replace the Mercury direct-FBT path (`checkout_page` handler at line 369-440) with a call to `MercuryRecommendationPipeline`. |
| [`recommendation_controller.py`](python-worker/app/controllers/recommendation_controller.py) | Replace the Apollo `post_purchase` path with a call to `ApolloRecommendationPipeline`. |
| [`hybrid.py`](python-worker/app/recommandations/hybrid.py) | Replace `item_neighbors` stub with real cross-encoder call. |
| [`smart_selection_service.py`](python-worker/app/recommandations/smart_selection_service.py) | The `item_neighbors` priority for product_page and cart now returns real results from cross-encoder. |
| [`normalization_consumer.py`](python-worker/app/consumers/kafka/normalization_consumer.py) | Add embedding computation trigger (alongside existing FP-Growth retraining). |
| [`settings.py`](python-worker/app/core/config/settings.py) | Add `ENABLE_EXPLORATION`, `EXPLORATION_EPSILON`, `ENABLE_HEAVY_RERANK` flags. |
| [`requirements.txt`](python-worker/requirements.txt) | Add `sentence-transformers`, `xgboost`. |

## 6. Data Flow for Each Surface

### Mercury (checkout_page)

```
Shopify Checkout Extension
  → POST /api/v1/recommendations
    { context: "checkout_page",
      product_ids: [A, B, C],         ← ALL cart items, not just first
      cart_value: 129.99,
      user_id: "123",
      session_id: "uuid",
      metadata: { checkout_step: "payment" } }

Pipeline:
  1. RetrievalFusionService.retrieve_candidates(
       query_items=[A, B, C],
       surface="mercury",
       ...
     )
     → CrossEncoder: avg(vec(A), vec(B), vec(C)) → ANN search → 30 items
     → FP-Growth: find rules matching {A, B, C} → 20 items
     → Session: recently viewed by user → 10 items
     → Merge → ~55 unique candidates

  2. LightRanker.score(candidates, context)
     → XGBoost scores each → top-15

  3. (Skip heavy rerank — latency critical)

  4. ExplorationService (5% chance: swap in 1 random item)

  5. Filter: remove out-of-stock, >3x cart value, already purchased

  6. Return top-3 or top-4

  → Log offer_impressions (existing)
  → Outcome callback via POST /api/interaction/outcome (existing)
```

### Apollo (post_purchase)

```
Shopify Thank-you Page (Apollo Extension)
  → POST /api/recommendation/get-with-session
    { extension_type: "apollo",
      purchased_products: [X, Y],     ← just purchased
      order_id: "order_456",
      customer_id: "789",
      limit: 3 }

Pipeline:
  1. RetrievalFusionService.retrieve_candidates(
       query_items=[X, Y],
       surface="apollo",
       ...
     )
     → CrossEncoder: vec(X), vec(Y) → ANN search → 30 items
     → FP-Growth: FBT for X, Y → 20 items
     → Session: user's purchase history (not cart) → 10 items
     → Merge → ~55 unique candidates

  2. LightRanker.score(candidates, context) → top-15

  3. HeavyRanker: CrossEncoderService.rerank(top-15, query_items=[X, Y])
     → Cross-encoder scores each (query_item, candidate) pair
     → Re-rank by score
     → ponytail: This adds ~200-500ms but post-purchase is async-loaded

  4. ExplorationService (10% chance: swap in 1 random item)

  5. Filter: remove already-purchased items, out-of-stock

  6. Return top-3

  → Log offer_impressions (existing)
  → Outcome callback via POST /api/interaction/outcome (existing)
```

## 7. Model Training & Lifecycle

### XGBoost Ranker (Stage 2)

- **Training data**: Historical `offer_impressions` rows where `outcome IN ('accepted', 'declined')`.
- **Features**: Per (shop_id, query_item, candidate_item) — computed at recommendation time and logged to `offer_impressions.metadata`.
- **Training frequency**: Daily (cron job or triggered after N new impressions).
- **Cold start**: For shops with <100 impressions, use a global model pre-trained on all shop data. After 100 impressions, switch to shop-specific fine-tuning.
- **`ponytail:`** A single global XGBoost model with shop_id as a feature is simpler than per-shop models. Start there. Per-shop models are an upgrade path when volume justifies it.

### Cross-Encoder (Stage 1 & 3)

- **Bi-encoder model**: `all-MiniLM-L6-v2` (from sentence-transformers). Pre-compute embeddings for all active products. Recompute on product update.
- **Cross-encoder model**: `cross-encoder/ms-marco-MiniLM-L-6-v2`. Loaded on first use, cached in memory.
- **`ponytail:`** Both models are downloaded from HuggingFace Hub on first use (~114MB total). If offline deploys are needed, pre-download in Dockerfile.

### Bandit (Stage 4)

- **Q-values**: Stored in Redis as `exploration:q:{shop_id}:{item_id}` → `{accepts: N, shown: M}`.
- **Update**: On outcome callback, increment accept/shown counters.
- **Decay**: Values decay by 0.99 per day (older data matters less).

## 8. Feature Breakdown (What each stage contributes)

| Stage | Mercury Latency | Apollo Latency | Quality Gain (est.) |
|-------|----------------|----------------|---------------------|
| 1. Retrieve (ANN) | 30ms | 30ms | +20% relevance |
| 1. Retrieve (FBT) | 5ms (cache) | 5ms (cache) | +15% complementarity |
| 1. Retrieve (session) | 10ms | 10ms | +5% personalization |
| 2. Light ranker | 5ms | 5ms | +10% conversion |
| 3. Heavy rerank | SKIP | 300ms | +5% (Apollo only) |
| 4. Explore | 1ms | 1ms | Long-term (data) |
| 5. Filter | 2ms | 2ms | Prevents bad UX |
| **Total (p95)** | **~80ms** | **~400ms** | |

## 9. Migration Path

### Phase 1 (Now — cross-encoder)
1. Create `product_vectors` table
2. Implement `CrossEncoderService` (bi-encoder retrieval)
3. Replace `item_neighbors` stubs
4. Wire embedding computation into normalization consumer
5. Validate: Mercury and Apollo now get real similarity results instead of falling through

### Phase 2 (Next — ranker + fusion)
6. Implement `RetrievalFusionService` (merge multiple sources)
7. Implement `LightRanker` (XGBoost)
8. Add training pipeline (daily cron on offer_impressions data)
9. Replace Mercury direct-FBT path
10. Validate: A/B test new pipeline vs old, measure accept rate

### Phase 3 (Future — exploration + heavy rerank)
11. Implement `ExplorationService` (ε-greedy)
12. Implement heavy rerank for Apollo
13. Wire bandit outcome tracking
14. Validate: Run 2-week holdout test

## 10. Rollback & Safety

- Each stage is independently disable-able via settings flags:
  - `ENABLE_CROSS_ENCODER_RETRIEVAL` (default: true)
  - `ENABLE_XGBOOST_RANKER` (default: false until trained)
  - `ENABLE_HEAVY_RERANK` (default: false)
  - `ENABLE_EXPLORATION` (default: false)
- If any stage fails, the pipeline degrades to the next available stage, eventually falling back to the existing FP-Growth + popular chain.
- The existing holdout mechanism (10% control group) stays in place for measuring incrementality of the new pipeline.

## 11. What Stays Unchanged

| Component | Why |
|-----------|-----|
| [`FPGrowthEngine`](python-worker/app/recommandations/fp_growth_engine.py) | Still primary for complementary/FBT recommendations |
| [`BusinessRulesFilter`](python-worker/app/recommandations/business_rules_filter.py) | Still used for price/inventory/category filtering |
| [`HoldoutService`](python-worker/app/services/holdout_service.py) | Still measures incrementality |
| `offer_impressions` table + outcome API | Still the write path for all tracked data |
| [`ProductEnrichment`](python-worker/app/recommandations/enrichment.py) | Still enriches results with product metadata |
| [`RecommendationCacheService`](python-worker/app/recommandations/cache.py) | Still caches results per cache_key |
| [`ProductExclusionService`](python-worker/app/recommandations/exclusion_service.py) | Still filters already-purchased items |

## 12. Open Questions (Deferred)

1. **XGBoost model storage**: Store in Redis (small, fast) or S3? Redis is fine for <10MB models. S3 for larger.
2. **Shop-specific vs global ranker**: Start with global model + shop_id feature. Per-shop models when >1000 impressions/shop.
3. **Exploration policy**: ε=0.1 is naive. Thompson sampling would be better but adds complexity. Start with ε-greedy.
4. **Feature store**: Features are computed on-the-fly today. If latency becomes an issue, pre-compute candidate features in a nightly batch.
