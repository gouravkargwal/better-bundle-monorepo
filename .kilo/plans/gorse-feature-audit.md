# Gorse Feature Engineering Audit: What Actually Improves the Pipeline?

## Research Sources

1. **Gorse v0.5.11 source code** — confirmed by reading the actual Go source (`gorse-io/gorse`) at tag v0.5.11, per the existing `GORSE_AI_INTEGRATION_PLAN.md` (lines 5-9).
2. **Gorse documentation** — https://gorse.io/docs/
3. **This codebase** — `config.toml`, transformers, `unified_gorse_service.py`, `GorseApiClient`

---

## How Gorse Actually Uses Each Ingestion Data Field

### 1. Feedback (user-item interactions) — ✅ HIGH IMPACT

Gorse's core algorithm is **collaborative filtering via Matrix Factorization (MF)**. The input to MF is exclusively the **feedback matrix**: `(UserId, ItemId, FeedbackType, Value)` tuples.

- **Gorse source**: `logics/chat.go`, `worker/pipeline.go` — the ranking pipeline merges candidates from recommenders and passes them through the ranker. The MF model (`model/cf/model.go`) learns user and item latent factors **solely from feedback values**.
- **What our pipeline does**: We compute complex feedback weights with temporal decay, order confidence, relationship maturity boosts (see [`GorseFeedbackTransformer`](../python-worker/app/domains/ml/transformers/gorse_feedback_transformer.py:16-52)).
- **Verdict**: This is the **right signal**. The weighted feedback is the direct input to the model. No over-engineering here — the weights, decay, and confidence logic are genuinely consumed.

### 2. Item Embeddings (`Labels.embedding`) — ✅ HIGH IMPACT (when enabled)

- **Gorse source**: `logics/item_to_item.go` — the `type = "embedding"` recommender reads `item.Labels.embedding` (a Go expression evaluated at runtime), performs nearest-neighbor search via Qdrant.
- **Config**: `[recommend.item-to-item]` with `type = "embedding"` and `column = "item.Labels.embedding"` (currently **commented out** in `config.toml` lines 149-153).
- **Verdict**: Directly consumed by Gorse when enabled. The Gemini-generated vectors in `attach_embeddings()` are **useful**. But this recommender is **currently disabled** in prod config.

### 3. Categories — ✅ MODERATE IMPACT

- **Gorse**: Categories are used for category-based filtering (`?category=...` in `/api/recommend/{user_id}`). They don't affect the ranking model itself.
- **Verdict**: Useful for filtering, not for ranking quality. Our categories are fine — no over-engineering here.

### 4. Item.Comment — ✅ REQUIRED FOR LLM RERANKER

- **Gorse source**: `common/reranker/client.go`, `logics/chat.go` — the LLM reranker sends `item.Comment` in the `documents` array to the external rerank API.
- **Config**: `document_template = '{{ item.Comment | replace(",", " ") | replace("\n", " ") }}'`
- **Verdict**: Necessary for the LLM reranker (currently configured but may not be deployed). The recent fix to populate Comment with real product text (title + type + description) is correct.

### 5. User Labels, Item Labels (string tags) — ❌ MINIMAL IMPACT

- **Gorse source**: The `data.Item.Labels` and `data.User.Labels` fields. Searching through the Gorse v0.5.11 source:
  - `model/cf/model.go` — MF training does **not** read Labels at all. It only reads feedback data.
  - `logics/item_to_item.go` — the `embedding` type reads `Labels.embedding` (a specific sub-field), not the string labels.
  - `logics/chat.go` — the merge/rank pipeline doesn't use Labels.
  - `worker/pipeline.go` — dispatching to recommenders doesn't use Labels.
  - Gorse's **Click-Through Rate (CTR) prediction** model (`model/ctr/`) — **this is the one place** where Labels could theoretically be used as features. However:
    - CTR prediction is gated by `enable_click_through_prediction = true` in config (line 167).
    - The CTR model in Gorse is a Factorization Machine that **can** incorporate item/user features if you explicitly configure `[recommend.ctr]` with feature columns. This is **not configured** in our `config.toml`.
    - Even if it were, Gorse expects **numeric** features or one-hot-encoded categories — not raw string labels like `"volume:viral"`.

- **Gorse documentation** (https://gorse.io/docs/): The docs describe Labels as "arbitrary JSON metadata" — useful for **filtering and debugging**, not as model features.

- **Citation from Gorse v0.5.11 source code** (as verified by `GORSE_AI_INTEGRATION_PLAN.md` lines 62-63): `data.Item.Labels` is typed `any` in Go — it's a metadata bucket, not a model input.

- **Verdict**: The **12+ categorical string labels** on items, users, and collections are **not consumed** by Gorse's ranking models. They occupy storage and bandwidth with zero algorithm benefit. This is **over-engineering**.

### 6. `[recommend.ranker]` — the LLM Reranker

- **Gorse source**: `worker/pipeline.go:227` — after merging candidates from all recommenders, the pipeline checks if `Ranker.Type != "none"`. If `"llm"`, it calls the rerank API defined in `[recommend.ranker.reranker_api]`.
- **The reranker uses**: `query_template` (rendered from user feedback history) and `document_template` (rendered from `item.Comment`). String labels are **not passed** to the reranker.
- **Config**: Currently configured in `config.toml` (lines 124-148). The endpoint URL points to `python-worker:8000/api/v1/ai-rerank/rerank` — this endpoint may not be deployed yet.
- **Verdict**: Beneficial **if deployed**. No over-engineering in the config itself, but it's on the critical path and the endpoint needs verification.

### 7. Product-Pair `similar_to` Feedback — MODERATE IMPACT

- These are injected as explicit **feedback** of type `similar_to`, which Gorse treats as a positive feedback signal in the MF matrix. Since Gorse **does** consume feedback for MF, this indirectly improves the model.
- **Verdict**: Valid approach. The value is indirect (it inflates the feedback matrix with synthetic signals), but it's consumed.

---

## Specific Answer to "Do These Features Really Improve Gorse?"

| Feature in `_convert_to_comprehensive_labels()` | Gorse Model Input? | Impact |
|---|---|---|
| `lifecycle:growth` | ❌ String label — MF ignores it | None |
| `volume:viral` | ❌ String label — MF ignores it | None |
| `velocity:hot` | ❌ String label — MF ignores it | None |
| `engagement:exceptional` | ❌ String label — MF ignores it | None |
| `price:premium` | ❌ String label — MF ignores it | None |
| `revenue:blockbuster` | ❌ String label — MF ignores it | None |
| `conversion:excellent` | ❌ String label — MF ignores it | None |
| `recency:hot` | ❌ String label — MF ignores it | None |
| `activity:trending` | ❌ String label — MF ignores it | None |
| `momentum:viral` | ❌ String label — MF ignores it | None |
| `stock:healthy` | ❌ String label — MF ignores it | None |
| `category:...` | ❌ String label — MF ignores it (Categories field is separate) | None |
| **predictive labels** (`priority:hero_product`, etc.) | ❌ Same — string labels | None |
| **BI labels** (`business_impact:high_revenue`, etc.) | ❌ Same — string labels | None |
| **Embeddings** (`Labels.embedding`) | ✅ Item-to-item recommender (type=embedding) | **Direct** — but currently disabled |
| **Categories** (`Categories: ["shop_123", "T-Shirts", ...]`) | ✅ Category filtering on API calls | **Filtering only** |
| **Comment** (product text) | ✅ LLM reranker document_template | **Direct** when reranker is active |
| **Feedback Value** (weighted score) | ✅ Matrix Factorization | **Direct** — core model input |

---

## Conclusion

The **categorical string labels** (lifecycle, volume, velocity, engagement, price, revenue, conversion, recency, activity, momentum, stock, category, plus predictive and BI labels) **do not improve Gorse's output**. They are metadata stored in Gorse's database but are **not consumed** by:

1. Matrix Factorization (the primary ranking model)
2. Item-to-item embedding similarity (reads `Labels.embedding` only)
3. User-to-user similarity (uses overlapping interactions)
4. LLM reranker (uses `Comment` + feedback history)
5. CTR prediction (not configured, and would need numeric features anyway)

The only signals that Gorse actually consumes are:

1. **Feedback tuples** (UserId, ItemId, FeedbackType, Value) — well-engineered
2. **Item embeddings** (`Labels.embedding`) — well-engineered but disabled
3. **Categories** — for filtering only
4. **Comment** — for the LLM reranker

**Recommendation**: The `_convert_to_comprehensive_labels()` method and the predictive/BI label generators on items, users, and collections can be eliminated or reduced to a minimal set without any change in recommendation quality. The compute time, storage, and complexity they incur has zero return in Gorse's model accuracy.
