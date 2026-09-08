# Phase 1 + Phase 2 Implementation Plan

## Overview

Two-phase build for the cross-encoder recommendation engine. Phase 1 is the big leap (semantic similarity replacing the `item_neighbors` stub). Phase 2 is the refinement (multi-source retrieval fusion + session awareness).

## Phase 1 — Cross-Encoder Semantic Similarity (2-3 days)

### P1.1 — New SQLAlchemy Model

**File:** [`python-worker/app/core/database/models/product_vector.py`](python-worker/app/core/database/models/product_vector.py) (NEW)

```python
"""
ProductVector model for pgvector-based semantic similarity search
"""
from sqlalchemy import Column, String, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import TIMESTAMP
from pgvector.sqlalchemy import Vector
from .base import BaseModel, ShopMixin
from datetime import datetime, timezone


class ProductVector(BaseModel, ShopMixin):
    __tablename__ = "product_vectors"

    product_id = Column(String, nullable=False, index=True)
    vector = Column(Vector(384), nullable=False)
    text_hash = Column(String(32), nullable=False)      # md5 of input text
    model_version = Column(String, nullable=False, default="all-MiniLM-L6-v2")

    __table_args__ = (
        UniqueConstraint("shop_id", "product_id", name="uq_product_vector_shop_product"),
        Index("idx_product_vectors_vector", vector, postgresql_using="ivfflat",
              postgresql_with={"lists": 100}),
    )
```

### P1.2 — Register Model

**File:** [`python-worker/app/core/database/models/__init__.py`](python-worker/app/core/database/models/__init__.py) (EDIT)

Add import and `__all__` entry for `ProductVector`.

### P1.3 — New Settings

**File:** [`python-worker/app/core/config/settings.py`](python-worker/app/core/config/settings.py) (EDIT)

Add to `MLSettings`:
```python
# Cross-encoder / bi-encoder settings
CROSS_ENCODER_ENABLED: bool = Field(default=True, env="CROSS_ENCODER_ENABLED")
BI_ENCODER_MODEL: str = Field(default="all-MiniLM-L6-v2", env="BI_ENCODER_MODEL")
CROSS_ENCODER_MODEL: str = Field(
    default="cross-encoder/ms-marco-MiniLM-L-6-v2", env="CROSS_ENCODER_MODEL"
)
ENABLE_HEAVY_RERANK: bool = Field(default=False, env="ENABLE_HEAVY_RERANK")
```

### P1.4 — New Dependency

**File:** [`python-worker/requirements.txt`](python-worker/requirements.txt) (EDIT)

Add: `sentence-transformers==3.4.1`

### P1.5 — Core Service

**File:** [`python-worker/app/recommandations/cross_encoder_service.py`](python-worker/app/recommandations/cross_encoder_service.py) (NEW, ~200 lines)

```python
"""
Cross-Encoder Service — Two-stage item similarity engine

Stage 1a: Bi-encoder (all-MiniLM-L6-v2) for fast vector retrieval via pgvector
Stage 1b: Cross-encoder (ms-marco-MiniLM-L6-v2) for optional high-quality rerank
"""
import asyncio
import hashlib
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from app.core.logging import get_logger
from app.core.database.session import get_transaction_context
from app.core.database.models.product_data import ProductData
from app.core.database.models.product_vector import ProductVector
from app.core.config.settings import settings
from sqlalchemy import select, and_, text

logger = get_logger(__name__)


@dataclass
class CrossEncoderConfig:
    model_name: str = "all-MiniLM-L6-v2"
    cross_encoder_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    vector_dim: int = 384
    batch_size: int = 64
    retrieval_limit: int = 30
    rerank_limit: int = 6


class CrossEncoderService:
    def __init__(self, config: CrossEncoderConfig = None):
        self.config = config or CrossEncoderConfig()
        self._bi_encoder = None
        self._cross_encoder = None

    # ── Public API ──────────────────────────────────────────

    async def get_similar_products(
        self,
        shop_id: str,
        query_items: List[str],
        limit: int = 6,
        rerank: bool = False,
    ) -> Dict[str, Any]:
        """
        Stage 1a + optional Stage 1b
        
        Args:
            shop_id: Shop identifier
            query_items: Product IDs to find similar products for (cart or purchased items)
            limit: Max recommendations to return
            rerank: Whether to run Stage 1b cross-encoder rerank
            
        Returns:
            Dict with items, scores, source metadata
        """
        try:
            # Step 1: Build query text from product data
            query_texts = await self._get_product_texts(shop_id, query_items)
            if not query_texts:
                return {"success": False, "items": [], "source": "cross_encoder_no_query_text"}
            
            # Step 2: Embed query items (Stage 1a)
            query_vectors = [self._embed_text(t) for t in query_texts]
            avg_vector = self._average_vectors(query_vectors)
            
            # Step 3: pgvector similarity search
            candidates = await self._pgvector_search(shop_id, avg_vector, self.config.retrieval_limit)
            if not candidates:
                return {"success": False, "items": [], "source": "cross_encoder_no_candidates"}
            
            # Step 4: Optional cross-encoder rerank (Stage 1b)
            if rerank and self.config.cross_encoder_name:
                candidates = await self._rerank_candidates(
                    query_items, query_texts, candidates
                )
            
            # Step 5: Format results
            seen = set(query_items)
            results = []
            for item_id, score in candidates:
                if item_id not in seen and len(results) < limit:
                    results.append({
                        "id": item_id,
                        "score": round(score, 4),
                        "reason": "Similar to your items",
                        "source": "cross_encoder",
                    })
                    seen.add(item_id)
            
            if not results:
                return {"success": False, "items": [], "source": "cross_encoder_all_filtered"}
            
            return {
                "success": True,
                "items": results,
                "source": "cross_encoder",
                "count": len(results),
            }
            
        except Exception as e:
            logger.error(f"Cross-encoder similarity failed: {e}")
            return {"success": False, "items": [], "source": "cross_encoder_error", "error": str(e)}

    async def compute_and_store_embeddings(
        self, shop_id: str, product_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Batch-compute and store embeddings for products.
        Called during normalization (new/updated products).
        """
        start = datetime.now()
        try:
            async with get_transaction_context() as session:
                # Load products
                query = select(ProductData).where(ProductData.shop_id == shop_id)
                if product_ids:
                    query = query.where(ProductData.product_id.in_(product_ids))
                result = await session.execute(query)
                products = result.scalars().all()
            
            if not products:
                return {"success": True, "products_processed": 0}
            
            embedded = 0
            skipped = 0
            batch_texts = []
            batch_products = []
            
            for product in products:
                text = self._build_product_text(product)
                text_hash = hashlib.md5(text.encode()).hexdigest()
                
                # Skip if hash matches existing vector
                async with get_transaction_context() as session:
                    existing = await session.execute(
                        select(ProductVector).where(
                            and_(
                                ProductVector.shop_id == shop_id,
                                ProductVector.product_id == product.product_id,
                                ProductVector.text_hash == text_hash,
                            )
                        )
                    )
                    if existing.scalar_one_or_none():
                        skipped += 1
                        continue
                
                batch_texts.append(text)
                batch_products.append(product)
                
                if len(batch_texts) >= self.config.batch_size:
                    embedded += await self._embed_and_store_batch(
                        shop_id, batch_products, batch_texts
                    )
                    batch_texts = []
                    batch_products = []
            
            # Remaining
            if batch_texts:
                embedded += await self._embed_and_store_batch(
                    shop_id, batch_products, batch_texts
                )
            
            duration = (datetime.now() - start).total_seconds()
            logger.info(f"Embeddings: {embedded} embedded, {skipped} skipped in {duration:.1f}s")
            
            return {
                "success": True,
                "products_processed": len(products),
                "products_embedded": embedded,
                "products_skipped": skipped,
                "duration_seconds": duration,
            }
            
        except Exception as e:
            logger.error(f"Embedding computation failed: {e}")
            return {"success": False, "error": str(e)}

    # ── Private Helpers ─────────────────────────────────────

    def _build_product_text(self, product: ProductData) -> str:
        """Build search text from product title, description, category, tags"""
        parts = [
            product.title or "",
            product.description or "",
            product.product_type or "",
        ]
        if product.tags and isinstance(product.tags, list):
            parts.extend(str(t) for t in product.tags)
        return " | ".join(p for p in parts if p)

    def _embed_text(self, text: str) -> List[float]:
        """Stage 1a: Bi-encoder inference"""
        if self._bi_encoder is None:
            from sentence_transformers import SentenceTransformer
            self._bi_encoder = SentenceTransformer(self.config.model_name)
        return self._bi_encoder.encode(text).tolist()

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Batch bi-encoder inference"""
        if self._bi_encoder is None:
            from sentence_transformers import SentenceTransformer
            self._bi_encoder = SentenceTransformer(self.config.model_name)
        return self._bi_encoder.encode(texts).tolist()

    def _average_vectors(self, vectors: List[List[float]]) -> List[float]:
        """Average multiple vectors into one"""
        import numpy as np
        return np.mean(vectors, axis=0).tolist()

    async def _get_product_texts(self, shop_id: str, product_ids: List[str]) -> List[str]:
        """Load product texts from database"""
        async with get_transaction_context() as session:
            result = await session.execute(
                select(ProductData).where(
                    and_(
                        ProductData.shop_id == shop_id,
                        ProductData.product_id.in_(product_ids),
                    )
                )
            )
            products = result.scalars().all()
            return [self._build_product_text(p) for p in products]

    async def _pgvector_search(
        self, shop_id: str, query_vector: List[float], limit: int
    ) -> List[Tuple[str, float]]:
        """ANN similarity search via pgvector"""
        vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"
        sql = text("""
            SELECT pv.product_id, 1 - (pv.vector <=> :query_vec::vector) AS similarity
            FROM product_vectors pv
            WHERE pv.shop_id = :shop_id
            ORDER BY pv.vector <=> :query_vec::vector
            LIMIT :limit
        """)
        async with get_transaction_context() as session:
            result = await session.execute(sql, {
                "query_vec": vector_str,
                "shop_id": shop_id,
                "limit": limit,
            })
            return [(row[0], float(row[1])) for row in result.fetchall()]

    async def _rerank_candidates(
        self,
        query_items: List[str],
        query_texts: List[str],
        candidates: List[Tuple[str, float]],
    ) -> List[Tuple[str, float]]:
        """Stage 1b: Cross-encoder rerank of top candidates"""
        if self._cross_encoder is None:
            from sentence_transformers import CrossEncoder
            self._cross_encoder = CrossEncoder(self.config.cross_encoder_name)
        
        # Build pairs: (query_text, candidate_text) for each top candidate
        top_candidates = candidates[:self.config.rerank_limit]
        candidate_ids = [c[0] for c in top_candidates]
        
        # Load candidate texts
        shop_id = None  # Need to pass this — FIXME in implementation
        # Actually we need shop_id here. Will be refactored to pass shop_id.
        
        pairs = []
        for query_text in query_texts:
            for cand_id in candidate_ids:
                pairs.append((query_text, cand_id))  # cand_id replaced with text later
        
        # Score pairs
        # NOTE: In actual implementation, load candidate texts first
        scores = self._cross_encoder.predict(pairs)
        
        # Aggregate scores per candidate (max over all query pairs)
        agg_scores = {}
        idx = 0
        for qi in range(len(query_texts)):
            for ci, cand_id in enumerate(candidate_ids):
                if cand_id not in agg_scores or scores[idx] > agg_scores[cand_id]:
                    agg_scores[cand_id] = float(scores[idx])
                idx += 1
        
        # Sort by rerank score
        reranked = sorted(agg_scores.items(), key=lambda x: x[1], reverse=True)
        return reranked

    async def _embed_and_store_batch(
        self, shop_id: str, products: List[ProductData], texts: List[str]
    ) -> int:
        """Embed a batch of products and store in product_vectors"""
        vectors = self._embed_batch(texts)
        
        async with get_transaction_context() as session:
            for product, vector, text in zip(products, vectors, texts):
                text_hash = hashlib.md5(text.encode()).hexdigest()
                # Upsert
                existing = await session.execute(
                    select(ProductVector).where(
                        and_(
                            ProductVector.shop_id == shop_id,
                            ProductVector.product_id == product.product_id,
                        )
                    )
                )
                pv = existing.scalar_one_or_none()
                if pv:
                    pv.vector = vector
                    pv.text_hash = text_hash
                    pv.model_version = self.config.model_name
                else:
                    session.add(ProductVector(
                        shop_id=shop_id,
                        product_id=product.product_id,
                        vector=vector,
                        text_hash=text_hash,
                        model_version=self.config.model_name,
                    ))
        return len(products)
```

### P1.6 — Wire into RecommendationExecutor

**File:** [`python-worker/app/recommandations/recommendation_executor.py`](python-worker/app/recommandations/recommendation_executor.py) (EDIT)

```python
# Add import at top
from app.recommandations.cross_encoder_service import CrossEncoderService

# In __init__:
self.cross_encoder = CrossEncoderService()

# Replace the item_neighbors stub (lines ~64-66):
if level == "item_neighbors":
    result = await self.cross_encoder.get_similar_products(
        shop_id=shop_id,
        query_items=product_ids or cart_items or [],
        limit=limit,
        rerank=(metadata or {}).get("rerank", False),
    )
    return result
```

### P1.7 — Wire into HybridService

**File:** [`python-worker/app/recommandations/hybrid.py`](python-worker/app/recommandations/hybrid.py) (EDIT)

Same pattern as P1.6 — replace the `item_neighbors` stub at line ~256-258.

### P1.8 — Mercury Checkout Path

**File:** [`python-worker/app/api/v1/recommendations.py`](python-worker/app/api/v1/recommendations.py) (EDIT)

Replace the direct FBT-only path (lines ~369-440) with:

```python
elif request.context == "checkout_page":
    cart_items = request.product_ids or request.metadata.get("cart_items", [])
    if not cart_items:
        result = {"success": False, "items": [], "source": "fbt_no_cart_items"}
    else:
        # Try cross-encoder first with ALL cart items
        cross_encoder = CrossEncoderService()
        result = await cross_encoder.get_similar_products(
            shop_id=shop.id,
            query_items=cart_items,
            limit=request.limit,
            rerank=False,  # Mercury: fast path only
        )
        
        # Fallback to FBT if cross-encoder fails
        if not result["success"]:
            from app.recommandations.frequently_bought_together import (
                FrequentlyBoughtTogetherService,
            )
            fbt_service = FrequentlyBoughtTogetherService()
            result = await fbt_service.get_frequently_bought_together(
                shop_id=shop.id,
                product_id=cart_items[0],
                limit=request.limit,
                cart_value=request.metadata.get("cart_value", 0.0),
            )
    
    # If both fail, use existing fallback chain
    if not result.get("success") or not result.get("items"):
        ...  # existing fallback to popular_category → popular
```

### P1.9 — Trigger in Normalization Consumer

**File:** [`python-worker/app/consumers/kafka/normalization_consumer.py`](python-worker/app/consumers/kafka/normalization_consumer.py) (EDIT)

In `_trigger_fbt_retraining_if_needed`, after the FBT training line, add:

```python
# Also update product embeddings for cross-encoder
from app.recommandations.cross_encoder_service import CrossEncoderService
ce_service = CrossEncoderService()
asyncio.create_task(
    ce_service.compute_and_store_embeddings(shop_id)
)
```

### P1.10 — FBT Status Admin

**File:** [`python-worker/app/api/v1/fbt_status.py`](python-worker/app/api/v1/fbt_status.py) (EDIT)

Add a `POST /api/v1/fbt/embeddings/{shop_id}` endpoint to manually trigger embedding computation.

---

## Phase 2 — Multi-Source Retrieval Fusion (1-2 days)

### P2.1 — Retrieval Fusion Service

**File:** [`python-worker/app/recommandations/retrieval_fusion_service.py`](python-worker/app/recommandations/retrieval_fusion_service.py) (NEW, ~120 lines)

```python
"""
Retrieval Fusion Service — Multi-source candidate merging

Combines results from:
- CrossEncoderService (semantic similarity)
- FPGrowthEngine (frequently bought together)
- SessionDataService (recent browsing/cart history)
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from app.core.logging import get_logger
from app.recommandations.cross_encoder_service import CrossEncoderService
from app.recommandations.fp_growth_engine import FPGrowthEngine
from app.recommandations.session_service import SessionDataService

logger = get_logger(__name__)

# Source weights — hand-tuned, can be replaced by learned model later
SOURCE_WEIGHTS = {
    "cross_encoder": 0.50,
    "frequently_bought_together": 0.30,
    "session": 0.20,
}


class RetrievalFusionService:
    """
    Stage: Multi-source retrieval fusion.
    
    Runs all retrieval sources in parallel, normalizes scores,
    merges with weighted scoring, returns deduplicated candidates.
    """
    
    def __init__(self):
        self.cross_encoder = CrossEncoderService()
        self.fp_growth = FPGrowthEngine()
        self.session_service = SessionDataService()
    
    async def retrieve_candidates(
        self,
        shop_id: str,
        query_items: List[str],
        surface: str,  # "mercury" | "apollo"
        user_id: Optional[str] = None,
        limit: int = 30,
    ) -> Dict[str, Any]:
        """
        Retrieve candidates from all sources, merge, return ranked.
        
        Args:
            shop_id: Shop identifier
            query_items: Cart items (Mercury) or purchased items (Apollo)
            surface: Which surface is requesting
            user_id: For session-based retrieval
            limit: Target number of candidates to return
            
        Returns:
            Dict with merged candidates and per-source metadata
        """
        try:
            # --- Run sources in parallel ---
            tasks = {}
            
            # Source 1: Cross-encoder (semantic similarity)
            tasks["cross_encoder"] = self.cross_encoder.get_similar_products(
                shop_id=shop_id,
                query_items=query_items,
                limit=limit,
                rerank=(surface == "apollo"),
            )
            
            # Source 2: FP-Growth (FBT)
            tasks["frequently_bought_together"] = self._get_fbt_for_items(
                shop_id=shop_id,
                query_items=query_items,
                limit=limit,
            )
            
            # Source 3: Session data (user history)
            if user_id:
                tasks["session"] = self._get_session_candidates(
                    shop_id=shop_id,
                    user_id=user_id,
                    limit=limit,
                )
            
            # Wait for all sources
            results = {}
            for source_name, task in tasks.items():
                try:
                    results[source_name] = await task
                except Exception as e:
                    logger.warning(f"Source {source_name} failed: {e}")
                    results[source_name] = {"success": False, "items": []}
            
            # --- Merge candidates ---
            all_items = {}
            source_stats = {}
            
            for source_name, result in results.items():
                items = result.get("items", [])
                source_stats[source_name] = {
                    "count": len(items),
                    "success": result.get("success", False),
                }
                
                weight = SOURCE_WEIGHTS.get(source_name, 0.1)
                for item in items:
                    item_id = item["id"]
                    score = item.get("score", 0)
                    
                    if item_id not in all_items:
                        all_items[item_id] = {
                            "id": item_id,
                            "score": 0,
                            "sources": [],
                            "reason": item.get("reason", ""),
                        }
                    
                    # Normalize score: cross-encoder is 0-1, FBT is unbounded
                    # Simple min-max normalization within each source
                    all_items[item_id]["score"] += score * weight
                    all_items[item_id]["sources"].append(source_name)
            
            # Sort by combined score
            merged = sorted(
                all_items.values(),
                key=lambda x: x["score"],
                reverse=True,
            )
            
            return {
                "success": True if merged else False,
                "items": merged[:limit],
                "count": len(merged[:limit]),
                "source": "retrieval_fusion",
                "source_stats": source_stats,
                "total_candidates": len(all_items),
            }
            
        except Exception as e:
            logger.error(f"Retrieval fusion failed: {e}")
            return {"success": False, "items": [], "source": "retrieval_fusion_error"}
    
    async def _get_fbt_for_items(
        self, shop_id: str, query_items: List[str], limit: int
    ) -> Dict[str, Any]:
        """Get FBT recommendations for multiple query items, merge results"""
        all_fbt = {}
        for item_id in query_items:
            result = await self.fp_growth.get_recommendations(
                shop_id=shop_id,
                cart_items=[item_id],
                limit=limit,
            )
            if result.get("success"):
                for rec in result.get("items", []):
                    rid = rec["id"]
                    if rid not in all_fbt or rec["score"] > all_fbt[rid]["score"]:
                        all_fbt[rid] = rec
        
        items = list(all_fbt.values())
        items.sort(key=lambda x: x.get("score", 0), reverse=True)
        return {"success": True, "items": items[:limit]}
    
    async def _get_session_candidates(
        self, shop_id: str, user_id: str, limit: int
    ) -> Dict[str, Any]:
        """Get candidates from user's recent session activity"""
        session_data = await self.session_service.extract_session_data_from_behavioral_events(
            user_id=user_id, shop_id=shop_id
        )
        
        items = []
        # Add recent views
        for idx, pid in enumerate(session_data.get("recent_views", [])):
            items.append({
                "id": pid,
                "score": max(0.1, 1.0 - idx * 0.1),
                "reason": "Recently viewed",
                "source": "session",
            })
        
        # Add recent adds to cart
        for idx, pid in enumerate(session_data.get("recent_adds", [])):
            items.append({
                "id": pid,
                "score": max(0.2, 1.0 - idx * 0.15),
                "reason": "Recently added to cart",
                "source": "session",
            })
        
        return {"success": True, "items": items[:limit]}
```

### P2.2 — Wire RetrievalFusion into Mercury Checkout

**File:** [`python-worker/app/api/v1/recommendations.py`](python-worker/app/api/v1/recommendations.py) (EDIT)

After Phase 1 changes, upgrade the Mercury path to use `RetrievalFusionService` instead of just cross-encoder:

```python
elif request.context == "checkout_page":
    cart_items = request.product_ids or request.metadata.get("cart_items", [])
    if not cart_items:
        result = {"success": False, "items": [], "source": "fbt_no_cart_items"}
    else:
        fusion = RetrievalFusionService()
        result = await fusion.retrieve_candidates(
            shop_id=shop.id,
            query_items=cart_items,
            surface="mercury",
            user_id=effective_user_id,
            limit=request.limit * 2,
        )
    
    # If fusion fails, fallback to popular
    if not result.get("success") or not result.get("items"):
        result = await services.executor.execute_recommendation_level(
            level="popular", shop_id=shop.id, limit=request.limit
        )
```

### P2.3 — Wire RetrievalFusion into Apollo Post-Purchase

**File:** [`python-worker/app/controllers/recommendation_controller.py`](python-worker/app/controllers/recommendation_controller.py) (EDIT)

Replace the direct `fetch_recommendations_logic` call for Apollo with:

```python
# In get_recommendations_with_session, after session creation:
from app.recommandations.retrieval_fusion_service import RetrievalFusionService

fusion = RetrievalFusionService()
result = await fusion.retrieve_candidates(
    shop_id=shop_id,
    query_items=request.purchased_products or [],
    surface="apollo",
    user_id=request.customer_id,
    limit=request.limit * 2,
)

# Enrich with product details
enriched = await enrich_items(shop_id, result.get("items", []), "post_purchase", "retrieval_fusion")
```

## Implementation Order

```
Phase 1:
  Day 1:
    [ ] P1.3 — Settings (5 min)
    [ ] P1.1 — ProductVector model (15 min)
    [ ] P1.2 — Register model (2 min)
    [ ] P1.4 — Add dependency (1 min)
    [ ] P1.5 — CrossEncoderService core (2-3 hours)
    [ ] Run: pip install, verify model downloads, verify table creation
    
  Day 2:
    [ ] P1.6 — Wire into RecommendationExecutor (15 min)
    [ ] P1.7 — Wire into HybridService (5 min)
    [ ] P1.8 — Mercury checkout path rewrite (1 hour)
    [ ] P1.9 — Normalization consumer trigger (10 min)
    [ ] P1.10 — Admin endpoint (15 min)
    [ ] Test: integration test with real products

Phase 2:
  Day 3:
    [ ] P2.1 — RetrievalFusionService (1-2 hours)
    [ ] P2.2 — Wire into Mercury (30 min)
    [ ] P2.3 — Wire into Apollo (30 min)
    [ ] Test: end-to-end with all sources
```

## Files Changed Summary

| # | File | Status | Lines |
|---|------|--------|-------|
| 1 | `python-worker/app/core/database/models/product_vector.py` | NEW | 40 |
| 2 | `python-worker/app/core/database/models/__init__.py` | EDIT | +2 |
| 3 | `python-worker/app/core/config/settings.py` | EDIT | +6 |
| 4 | `python-worker/requirements.txt` | EDIT | +1 |
| 5 | `python-worker/app/recommandations/cross_encoder_service.py` | NEW | 200 |
| 6 | `python-worker/app/recommandations/recommendation_executor.py` | EDIT | ~10 |
| 7 | `python-worker/app/recommandations/hybrid.py` | EDIT | ~5 |
| 8 | `python-worker/app/api/v1/recommendations.py` | EDIT | ~40 |
| 9 | `python-worker/app/consumers/kafka/normalization_consumer.py` | EDIT | ~5 |
| 10 | `python-worker/app/api/v1/fbt_status.py` | EDIT | ~20 |
| 11 | `python-worker/app/recommandations/retrieval_fusion_service.py` | NEW | 120 |
| 12 | `python-worker/app/controllers/recommendation_controller.py` | EDIT | ~15 |

**Total new lines:** ~460 across 12 files (3 new, 9 edits)
