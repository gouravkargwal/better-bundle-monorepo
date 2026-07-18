# Gorse: LLM Reranking + Vector Embeddings via Gemini/Vertex AI

## Context

BetterBundle runs Gorse (`zhenghaoz/gorse-in-one:latest`, resolves to v0.5.11) as its
recommendation engine, configured via `config.toml`. Confirmed by reading Gorse's actual Go source
(`gorse-io/gorse`: `config/config.go`, `common/reranker/client.go`, `logics/chat.go`,
`logics/item_to_item.go`, `worker/pipeline.go`), checked out at the exact `v0.5.11` release tag
(not master) — rather than relying on docs/guesswork:

**Production finding (pre-existing, unrelated to this feature but blocking it):** the live
`config.toml` has a `[recommend.ranking]` section (`model = "fm"`, `factors = 64`, ...). That key
was renamed to `[recommend.ranker]` a while back and `[recommend.ranking]` **does not exist** in
v0.5.11's config schema at all. Since the image floats on `:latest`, `Ranker.Type` is currently
empty in prod, so `worker/pipeline.go`'s ranking dispatch falls through to
`results = candidates` — **no ranking/reranking currently happens in production**, items are
served in raw merged-candidate order. `fm` and `llm` ranking are mutually exclusive
(`type = "none" | "fm" | "llm"`, if/else-if dispatch in `pipeline.go:227`), so turning on LLM
reranking is a straight fix+upgrade, not a tradeoff against a working feature (confirmed with user).

**Reranking** needs a small translation endpoint — neither Gemini nor Vertex AI expose Gorse's
required Jina-shaped contract. Exact contract confirmed from `common/reranker/client.go` +
`logics/chat.go`:

- Gorse → our endpoint: `POST {url}`, header `Authorization: Bearer {auth_token}`, body
  `{"model": str, "query": str, "documents": [str], "top_n"?: int}` (Gorse never sets `top_n`).
- Our endpoint → Gorse: `{"model": str, "usage": {"total_tokens": int}, "results": [{"index": int,
"relevance_score": float64}, ...]}`.
- **Order-sensitive**: Gorse walks `results` in array order to build final ranking
  (`logics/chat.go:97-103`) — it does **not** re-sort by `relevance_score` itself. Our endpoint
  must return `results` already sorted descending by score.
- No batching on Gorse's side (all merged candidates in one request), no client timeout set.
- Query template renders from `{user, feedback}` (gonja/Jinja2), document template from `{item}` —
  matches the `ItemId`/`Labels`/`Categories`/`Comment` shape already produced by
  `gorse_item_transformer.py`. Real example from Gorse's own `config/config.toml`:
  ```
  query_template = """
  You are a GitHub repository recommender system. Given a user is interested in the following repositories:
  {% for repo in feedback -%}
  - {{ repo.Comment }}
  {% endfor -%}
  Please sort repositories by the user's interests.
  """
  document_template = '{{ item.Comment | replace(",", " ") | replace("\n", " ") }}'
  ```

**Embeddings** do NOT work the way the feature description implied. Confirmed from
`logics/item_to_item.go`: the `type = "embedding"` item-to-item recommender (Euclidean-distance
similarity) reads a pre-existing vector off each item via a `column` expression (e.g.
`item.Labels.embedding`, evaluated in `embeddingItemToItem.Push()`) — Gorse never calls the
`[openai]` config to _compute_ item embeddings. `[openai]`'s `embedding_model`/`embedding_dimensions`
are only used by a separate, optional `type = "chat"` item-to-item mode (LLM-generates search-query
text for an item, embeds _that_ live, searches against the same pre-populated
`Labels.embedding` index) — not needed for basic embedding similarity.

**Net implication (confirmed with user):** embeddings must be computed by us and attached to each
item's `Labels.embedding` at ingestion time — this can't be pure config, but it also means no
Gorse-facing gateway/shim is needed for embeddings either, since we call Gemini/Vertex's embedding
API ourselves during item sync, not as a service Gorse calls. Reranking still needs the one
translation endpoint, unavoidably, in both environments.

**Labels shape (confirmed with user):** Gorse's `data.Item.Labels` field is typed `any` (arbitrary
JSON) in the actual Go struct, but this codebase currently sends it as a flat `List[str]` of
`"key:value"` tags, relied on in several places (label-quality validation, predictive/BI label
generation, stats tracking). `item.Labels.embedding` only resolves if `Labels` is a JSON object, not
a list — there's no other per-item field to hold a vector (`Comment` is reused for the reranker's
document text, `Categories` is a plain string list). Chose the minimal-diff option: wrap the
existing flat tag list under `Labels.tags`, add `Labels.embedding` as a sibling key — i.e.
`{"tags": [...], "embedding": [...]}` — rather than converting every tag into its own dict key.
Only the final assembly point in `gorse_item_transformer.py` and the one label-stats-tracking line
in `unified_gorse_service.py` change shape; `validate_label_quality`/predictive/BI label generation
keep operating on flat lists internally. `gorse_user_transformer.py` and
`gorse_collection_transformer.py` are untouched — this only applies to product items.

No existing LLM/embedding provider abstraction exists in this repo — greenfield for Google AI
integration. `product_embeddings.py` (Word2Vec) and `hybrid.py` (weighted blending) are a separate,
non-Gorse-native pipeline and stay untouched.

## Implementation

### 1. `app/shared/ai_provider.py` — shared Gemini/Vertex client

New module (mirrors `GorseApiClient`'s pattern: thin class, `get_logger`, settings-driven). Uses
the `google-genai` SDK (add to `requirements.txt`) — Google's unified client for exactly this
staging/prod split: `genai.Client(api_key=...)` for AI Studio, `genai.Client(vertexai=True,
project=..., location=...)` for Vertex AI (auth via `GOOGLE_APPLICATION_CREDENTIALS`/ADC
service-account file). Selects Gemini vs Vertex internally based on `settings.ml.AI_PROVIDER`
(`"gemini"` | `"vertex"`). Two methods:

- `embed(texts: list[str]) -> list[list[float]]` — batches through the embedding model.
- `score_relevance(query: str, documents: list[str]) -> list[float]` — used by the rerank endpoint.

Models: `AI_EMBEDDING_MODEL` (default `gemini-embedding-001`, GA on both AI Studio and Vertex AI),
`AI_EMBEDDING_DIMENSIONS` (default 768, matryoshka-truncated), `AI_CHAT_MODEL` (flash-tier,
configurable — verify the current cheapest Gemini flash model name at deploy time).

### 2. `app/api/v1/ai_rerank.py` — the one translation endpoint

Added to the existing python-worker FastAPI app (`main.py` → `app.main:app`, routers under
`app/api/v1/`) — no new service/container.

- `POST /api/v1/ai-rerank/rerank` — validates a static bearer token (`AI_RERANK_TOKEN`), matches
  the exact request/response shape confirmed above. Calls `ai_provider.score_relevance(query,
documents)`, zips scores back to `{index, relevance_score}`, **sorts descending**, returns.

### 3. Item embeddings — extend `gorse_item_transformer.py`

In `transform_to_gorse_item` (and batch variant), add an embedding step: build embeddable text from
product title + description/category, call `ai_provider.embed([text])`, attach the vector into the
item's `Labels` dict as `embedding` (so Gorse's `column = "item.Labels.embedding"` expression
resolves). Cache per-product embeddings keyed by a content hash (title+description) — same spirit
as `product_embeddings.py`'s Redis caching — so unchanged products aren't re-embedded on every sync.
Batch the embedding calls (the embedding API accepts a list of texts) rather than one call per item.

Also fix the current dead `Comment` field
(`"Comment": f"Product: {product_id} (using ALL 12 optimized features)"` — no real semantic
content) to include actual product text, since the reranker's `document_template` renders from
`item.Comment` and would otherwise score every item against a near-constant string.

### 4. Settings (`python-worker/app/core/config/settings.py`)

Extend `MLSettings`:

```python
AI_PROVIDER: str = Field(default="gemini", env="AI_PROVIDER")  # "gemini" | "vertex"
GEMINI_API_KEY: str = Field(default="", env="GEMINI_API_KEY")
VERTEX_PROJECT_ID: str = Field(default="", env="VERTEX_PROJECT_ID")
VERTEX_LOCATION: str = Field(default="us-central1", env="VERTEX_LOCATION")
AI_EMBEDDING_MODEL: str = Field(default="gemini-embedding-001", env="AI_EMBEDDING_MODEL")
AI_EMBEDDING_DIMENSIONS: int = Field(default=768, env="AI_EMBEDDING_DIMENSIONS")
AI_CHAT_MODEL: str = Field(default="gemini-3.1-flash-lite", env="AI_CHAT_MODEL")  # verify current name at deploy time
AI_RERANK_TOKEN: str = Field(default="", env="AI_RERANK_TOKEN")
```

`GOOGLE_APPLICATION_CREDENTIALS` is read directly by ADC, not an explicit settings field.

### 5. `config.toml` — replace `[recommend.ranking]` with `[recommend.ranker]`

```toml
[recommend.ranker]
type = "llm"
cache_expire = "120h"
recommenders = ["latest", "collaborative", "item-to-item/product_embedding"]
fit_period = "45m"
fit_epoch = 100
optimize_period = "360m"
optimize_trials = 10
query_template = """
... (adapt the GitHub example to BetterBundle's product/purchase-history domain) ...
"""
document_template = '{{ item.Comment | replace(",", " ") | replace("\n", " ") }}'

[recommend.ranker.early_stopping]
patience = 10

[recommend.ranker.reranker_api]
url = "http://python-worker:${PORT}/api/v1/ai-rerank/rerank"
auth_token = "${AI_RERANK_TOKEN}"
model = "gemini-rerank"

[[recommend.item-to-item]]
name = "product_embedding"
type = "embedding"
column = "item.Labels.embedding"
```

No `[openai]` section needed (that's only for the optional `chat`-type item-to-item search, out of
scope here). The old `[recommend.ranking]` block is removed entirely (dead key, replaced above).

**Verify before touching prod**: bring up the same `zhenghaoz/gorse-in-one` image in dev with this
config and check container startup logs — Gorse validates config with struct tags
(`validate:"oneof=..."`, `validate:"gt=0"`, etc.) and fails fast on invalid values, so this is a
cheap, authoritative check.

### 6. Env vars & docker-compose

Add to `env.example` / `env.dev.example` / `env.prod.example`:

```
AI_PROVIDER=gemini            # dev/staging
AI_PROVIDER=vertex            # prod
GEMINI_API_KEY=...            # staging (embeddings + reranking)
VERTEX_PROJECT_ID=...         # prod
VERTEX_LOCATION=us-central1
AI_RERANK_TOKEN=...           # shared secret between Gorse and python-worker, same pattern as GORSE_API_KEY
```

- `docker-compose.prod.yml`: mount a service-account JSON into `python-worker` and set
  `GOOGLE_APPLICATION_CREDENTIALS=/path/in/container`; add the new vars to its `env_file`-sourced
  `.env.prod`.
- `docker-compose.dev.yml`: same shape, `AI_PROVIDER=gemini`, no credentials file needed.
- `gorse` service itself needs no compose changes beyond what's already templated via
  `config.toml` env substitution (`${AI_RERANK_TOKEN}` etc.), consistent with the existing
  `${GORSE_API_KEY}` pattern.

## Verification

1. Bring up `docker-compose.dev.yml` locally with the new `config.toml`; confirm Gorse's master
   container starts cleanly (check logs for config validation errors).
2. Curl `/api/v1/ai-rerank/rerank` directly with a stub bearer token and a few real product
   titles; confirm the response matches Gorse's exact expected shape and is sorted descending.
3. Trigger a small item/feedback sync into Gorse (existing `GorseApiClient`/`unified_gorse_service`
   path) with the updated transformer; confirm items carry a populated `Labels.embedding`, and call
   `GET /api/item/{item_id}/neighbors` to confirm embedding-based item-to-item similarity returns
   sensible neighbors.
4. Call `GET /api/recommend/{user_id}` end-to-end with reranking enabled; compare ordering
   before/after to confirm the LLM reranker is actually influencing results (not silently falling
   back to `results = candidates`).
5. Confirm the prod `AI_PROVIDER=vertex` path with real service-account credentials over a
   > 1h-long-running container (token refresh, no restart needed).
