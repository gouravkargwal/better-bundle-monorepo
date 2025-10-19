"""
FP-Growth Engine for High-Performance FBT
Implements Layer 1 of the three-layer FBT system (70% quality)

Based on your existing database structure - no new tables needed.
Uses OrderData and LineItemData tables directly.
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple, Set
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
import pickle
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.database.session import get_transaction_context
from app.core.database.models.order_data import OrderData, LineItemData
from app.core.redis_client import get_redis_client
from app.recommandations.business_rules_filter import (
    BusinessRulesFilter,
    BusinessRulesConfig,
)
from app.recommandations.product_embeddings import (
    ProductEmbeddingsService,
    EmbeddingConfig,
)

logger = get_logger(__name__)


@dataclass
class FPGrowthConfig:
    """Configuration for FP-Growth algorithm"""

    # Core parameters
    min_support: float = 0.01  # 1% of orders (sweet spot)
    min_confidence: float = 0.30  # 30% confidence (sweet spot)
    min_lift: float = 1.5  # 50% lift (sweet spot)

    # Data window
    days_back: int = 90  # Last 90 days of orders

    # Performance
    max_items_per_order: int = 20  # Prevent memory issues
    min_order_value: float = 0.0  # Filter out $0 orders

    # Recency weighting
    recency_weights: Dict[str, float] = None

    def __post_init__(self):
        if self.recency_weights is None:
            self.recency_weights = {
                "0-30": 1.0,  # Last 30 days
                "30-60": 0.8,  # 30-60 days ago
                "60-90": 0.6,  # 60-90 days ago
            }


@dataclass
class AssociationRule:
    """Represents a single association rule"""

    antecedent: List[str]  # IF items (trigger products)
    consequent: List[str]  # THEN items (recommended products)
    support: float  # How often the rule appears
    confidence: float  # How often THEN happens given IF
    lift: float  # How much more likely than random
    recency_weight: float  # Time-based weight
    final_score: float  # Hybrid score for ranking

    def to_dict(self) -> Dict[str, Any]:
        return {
            "antecedent": self.antecedent,
            "consequent": self.consequent,
            "support": self.support,
            "confidence": self.confidence,
            "lift": self.lift,
            "recency_weight": self.recency_weight,
            "final_score": self.final_score,
        }


class FPGrowthEngine:
    """
    High-performance FP-Growth engine for FBT recommendations

    Uses your existing OrderData and LineItemData tables.
    No new database tables required.
    """

    def __init__(self, config: FPGrowthConfig = None):
        self.config = config or FPGrowthConfig()
        self.redis_client = None
        self._rules_cache = {}
        self.business_rules = BusinessRulesFilter()
        self.embeddings_service = ProductEmbeddingsService()

    async def get_redis_client(self):
        """Get Redis client for caching"""
        if self.redis_client is None:
            self.redis_client = await get_redis_client()
        return self.redis_client

    async def train_model(self, shop_id: str) -> Dict[str, Any]:
        """Train FP-Growth model using mlxtend"""
        logger.info(f"🧠 Training FP-Growth model for shop {shop_id}")
        start_time = datetime.now()

        try:
            # Step 1: Load transactions
            transactions = await self._load_transactions(shop_id)
            logger.info(f"📊 Loaded {len(transactions)} transactions")

            if len(transactions) < 100:
                return {
                    "success": False,
                    "error": "Need at least 100 orders for training",
                }

            # Step 2: Use mlxtend (complete pipeline)
            try:
                rules = await self._train_with_mlxtend(transactions)
            except ImportError:
                logger.warning("⚠️ mlxtend not installed, using fallback")
                rules = await self._train_fallback(transactions)

            if not rules:
                return {"success": False, "error": "No association rules generated"}

            # Step 3: Apply recency weighting
            weighted_rules = await self._apply_recency_weighting(rules, shop_id)

            # Step 4: Cache rules
            await self._cache_rules(shop_id, weighted_rules)

            # Step 5: Calculate metrics
            metrics = self._calculate_quality_metrics(weighted_rules, transactions)

            training_time = (datetime.now() - start_time).total_seconds()

            return {
                "success": True,
                "shop_id": shop_id,
                "training_time_seconds": training_time,
                "transactions_processed": len(transactions),
                "association_rules": len(weighted_rules),
                "quality_metrics": metrics,
            }

        except Exception as e:
            logger.error(f"❌ Training failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _train_with_mlxtend(
        self, transactions: List[List[str]]
    ) -> List[AssociationRule]:
        """Train using mlxtend (corrected implementation)"""
        from mlxtend.frequent_patterns import fpgrowth, association_rules
        from mlxtend.preprocessing import TransactionEncoder
        import pandas as pd

        # Validate input
        if not transactions or len(transactions) < 10:
            logger.warning("Insufficient transactions for training")
            return []

        # Clean and validate transactions
        clean_transactions = []
        for transaction in transactions:
            # Remove duplicates and filter empty
            clean_transaction = list(set([str(item) for item in transaction if item]))
            if len(clean_transaction) >= 2:  # Need at least 2 items
                clean_transactions.append(clean_transaction)

        if len(clean_transactions) < 10:
            logger.warning("Insufficient clean transactions for training")
            return []

        # Convert transactions to binary DataFrame
        te = TransactionEncoder()
        try:
            te_ary = te.fit(clean_transactions).transform(clean_transactions)
            df = pd.DataFrame(te_ary, columns=te.columns_)
        except Exception as e:
            logger.error(f"Transaction encoding failed: {e}")
            return []

        logger.info(f"📊 Created transaction matrix: {df.shape}")

        # Mine frequent itemsets with better error handling
        try:
            # Use adaptive min_support to ensure we get some results
            adaptive_min_support = max(
                self.config.min_support, 1.0 / len(clean_transactions)
            )
            frequent_itemsets_df = fpgrowth(
                df,
                min_support=adaptive_min_support,
                use_colnames=True,
                max_len=3,
            )
        except Exception as e:
            logger.error(f"FP-Growth mining failed: {e}")
            return []

        if frequent_itemsets_df.empty:
            logger.warning("No frequent itemsets found")
            return []

        logger.info(f"🔍 Found {len(frequent_itemsets_df)} frequent itemsets")

        # Generate association rules with proper error handling
        try:
            rules_df = association_rules(
                frequent_itemsets_df,
                metric="confidence",
                min_threshold=self.config.min_confidence,
            )
        except Exception as e:
            logger.error(f"Association rule generation failed: {e}")
            return []

        if rules_df.empty:
            logger.warning("No association rules generated")
            return []

        # Filter by lift
        rules_df = rules_df[rules_df["lift"] >= self.config.min_lift]

        logger.info(f"📋 Generated {len(rules_df)} association rules")

        # Convert to AssociationRule objects
        rules = []
        for _, row in rules_df.iterrows():
            try:
                rule = AssociationRule(
                    antecedent=list(row["antecedents"]),
                    consequent=list(row["consequents"]),
                    support=float(row["support"]),
                    confidence=float(row["confidence"]),
                    lift=float(row["lift"]),
                    recency_weight=1.0,
                    final_score=float(row["confidence"] * row["lift"]),
                )
                rules.append(rule)
            except Exception as e:
                logger.warning(f"Failed to create rule from row: {e}")
                continue

        return rules

    async def _train_fallback(
        self, transactions: List[List[str]]
    ) -> List[AssociationRule]:
        """
        Improved fallback when mlxtend not available

        Generates both 1->1 and 2->1 rules for better quality
        """
        logger.warning("⚠️ Using improved fallback - quality will be reduced")

        # Count single items
        item_counts = Counter()
        for transaction in transactions:
            for item in transaction:
                item_counts[item] += 1

        min_support_count = int(len(transactions) * self.config.min_support)
        total_transactions = len(transactions)
        rules = []

        # Generate 1->1 rules (A -> B)
        pair_counts = Counter()
        for transaction in transactions:
            items = list(transaction)
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    if items[i] < items[j]:  # Consistent ordering
                        pair = (items[i], items[j])
                    else:
                        pair = (items[j], items[i])
                    pair_counts[pair] += 1

        for (item_a, item_b), pair_count in pair_counts.items():
            if pair_count < min_support_count:
                continue

            count_a = item_counts[item_a]
            count_b = item_counts[item_b]

            # Rule: A -> B
            if count_a > 0:
                support = pair_count / total_transactions
                confidence = pair_count / count_a
                lift = confidence / (count_b / total_transactions)

                if (
                    confidence >= self.config.min_confidence
                    and lift >= self.config.min_lift
                ):
                    rules.append(
                        AssociationRule(
                            antecedent=[item_a],
                            consequent=[item_b],
                            support=support,
                            confidence=confidence,
                            lift=lift,
                            recency_weight=1.0,
                            final_score=confidence * lift,
                        )
                    )

            # Rule: B -> A
            if count_b > 0:
                support = pair_count / total_transactions
                confidence = pair_count / count_b
                lift = confidence / (count_a / total_transactions)

                if (
                    confidence >= self.config.min_confidence
                    and lift >= self.config.min_lift
                ):
                    rules.append(
                        AssociationRule(
                            antecedent=[item_b],
                            consequent=[item_a],
                            support=support,
                            confidence=confidence,
                            lift=lift,
                            recency_weight=1.0,
                            final_score=confidence * lift,
                        )
                    )

        # Generate 2->1 rules (A,B -> C) for better FBT quality
        triplet_counts = Counter()
        for transaction in transactions:
            items = list(transaction)
            if len(items) >= 3:  # Need at least 3 items for triplets
                for i in range(len(items)):
                    for j in range(i + 1, len(items)):
                        for k in range(j + 1, len(items)):
                            # Create ordered triplet
                            triplet = tuple(sorted([items[i], items[j], items[k]]))
                            triplet_counts[triplet] += 1

        for triplet, count in triplet_counts.items():
            if count < min_support_count:
                continue

            # Generate rules: A,B -> C
            for i in range(len(triplet)):
                antecedent = [triplet[j] for j in range(len(triplet)) if j != i]
                consequent = [triplet[i]]

                # Count antecedent support
                antecedent_count = 0
                for transaction in transactions:
                    if all(item in transaction for item in antecedent):
                        antecedent_count += 1

                if antecedent_count > 0:
                    support = count / total_transactions
                    confidence = count / antecedent_count
                    consequent_count = item_counts[consequent[0]]
                    lift = confidence / (consequent_count / total_transactions)

                    if (
                        confidence >= self.config.min_confidence
                        and lift >= self.config.min_lift
                    ):
                        rules.append(
                            AssociationRule(
                                antecedent=antecedent,
                                consequent=consequent,
                                support=support,
                                confidence=confidence,
                                lift=lift,
                                recency_weight=1.0,
                                final_score=confidence * lift,
                            )
                        )

        logger.info(
            f"📋 Improved fallback generated {len(rules)} rules (1->1 and 2->1)"
        )
        return rules

    async def train_embeddings(self, shop_id: str) -> Dict[str, Any]:
        """Train product embeddings for semantic similarity"""
        try:
            logger.info(f"🧠 Training product embeddings for shop {shop_id}")
            result = await self.embeddings_service.train_embeddings(shop_id)

            if result["success"]:
                logger.info(
                    f"✅ Embeddings training completed: {result['products_embedded']} products embedded"
                )
            else:
                logger.error(f"❌ Embeddings training failed: {result.get('error')}")

            return result

        except Exception as e:
            logger.error(f"Error training embeddings: {str(e)}")
            return {"success": False, "error": str(e)}

    async def get_recommendations(
        self,
        shop_id: str,
        cart_items: List[str],
        limit: int = 6,
        cart_value: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Get FBT recommendations for cart items

        Args:
            shop_id: Shop identifier
            cart_items: List of product IDs in cart
            limit: Maximum recommendations to return

        Returns:
            Recommendations with scores and metadata
        """
        try:
            # Load cached rules
            rules = await self._load_cached_rules(shop_id)
            if not rules:
                logger.warning(
                    f"⚠️ No cached rules for shop {shop_id} - may need training"
                )
                return {
                    "success": False,
                    "items": [],
                    "source": "fp_growth_no_rules",
                    "error": "No trained rules available",
                }

            # Find matching rules
            matching_rules = self._find_matching_rules(rules, cart_items)

            if not matching_rules:
                logger.info(f"🔍 No matching rules found for cart items: {cart_items}")
                return {
                    "success": False,
                    "items": [],
                    "source": "fp_growth_no_matches",
                    "error": "No association rules match cart items",
                }

            # Rank and filter recommendations
            raw_recommendations = self._rank_recommendations(
                matching_rules, cart_items, limit * 2
            )  # Get more for filtering

            # Apply business rules filtering (Layer 2)
            filtered_recommendations = await self.business_rules.filter_recommendations(
                shop_id=shop_id,
                cart_items=cart_items,
                cart_value=cart_value,
                recommendations=raw_recommendations,
            )

            # Apply semantic boosting (Layer 3)
            boosted_recommendations = (
                await self.embeddings_service.boost_recommendations(
                    shop_id=shop_id,
                    recommendations=filtered_recommendations,
                    cart_items=cart_items,
                    boost_factor=1.2,
                )
            )

            # Limit to requested number
            final_recommendations = boosted_recommendations[:limit]

            logger.info(
                f"🎯 Generated {len(final_recommendations)} FBT recommendations (filtered from {len(raw_recommendations)})"
            )

            return {
                "success": True,
                "items": final_recommendations,
                "source": "fp_growth_engine_with_business_rules",
                "count": len(final_recommendations),
                "rules_matched": len(matching_rules),
                "raw_recommendations": len(raw_recommendations),
                "filtered_recommendations": len(final_recommendations),
            }

        except Exception as e:
            logger.error(f"❌ FBT recommendation failed: {str(e)}")
            return {
                "success": False,
                "items": [],
                "source": "fp_growth_error",
                "error": str(e),
            }

    async def _load_transactions(self, shop_id: str) -> List[List[str]]:
        """Load order transactions with better validation"""
        transactions = []
        cutoff_date = datetime.now() - timedelta(days=self.config.days_back)

        async with get_transaction_context() as session:
            # Get orders with line items from last N days with better filtering
            result = await session.execute(
                select(OrderData.id, LineItemData.product_id, OrderData.order_date)
                .join(LineItemData)
                .where(
                    and_(
                        OrderData.shop_id == shop_id,
                        OrderData.order_date >= cutoff_date,
                        OrderData.financial_status == "paid",
                        OrderData.total_amount >= self.config.min_order_value,
                        LineItemData.product_id.isnot(None),  # Ensure valid product IDs
                    )
                )
                .order_by(OrderData.order_date.desc())
            )

            # Group by order with validation
            order_items = defaultdict(set)
            for row in result.fetchall():
                order_id, product_id, order_date = row
                # Validate and clean product_id
                if product_id and str(product_id).strip():
                    order_items[order_id].add(str(product_id))

            # Convert to transaction format with filtering
            for order_id, products in order_items.items():
                # Need at least 2 items for meaningful rules
                if 2 <= len(products) <= self.config.max_items_per_order:
                    transactions.append(list(products))

        logger.info(f"📊 Loaded {len(transactions)} valid transactions")
        return transactions

    async def _apply_recency_weighting(
        self, rules: List[AssociationRule], shop_id: str
    ) -> List[AssociationRule]:
        """Apply actual recency weighting based on order dates"""
        try:
            async with get_transaction_context() as session:
                # Get recent order frequency for each product (last 30 days)
                cutoff_date = datetime.now() - timedelta(days=30)

                result = await session.execute(
                    select(LineItemData.product_id, func.count(OrderData.id))
                    .join(OrderData)
                    .where(
                        and_(
                            OrderData.shop_id == shop_id,
                            OrderData.order_date >= cutoff_date,
                            OrderData.financial_status == "paid",
                        )
                    )
                    .group_by(LineItemData.product_id)
                )

                recent_counts = dict(result.fetchall())

                # Apply recency weights to rules
                weighted_rules = []
                for rule in rules:
                    # Calculate recency weight based on how recently items appeared
                    recency_weight = 1.0
                    for item in rule.antecedent + rule.consequent:
                        if item in recent_counts:
                            # Boost based on recent frequency (capped at 2x)
                            recency_weight *= min(
                                1.2, 1.0 + (recent_counts[item] / 100)
                            )

                    rule.recency_weight = min(recency_weight, 2.0)  # Cap at 2x
                    rule.final_score = rule.confidence * rule.lift * rule.recency_weight
                    weighted_rules.append(rule)

                logger.info(
                    f"⚖️ Applied recency weighting to {len(weighted_rules)} rules"
                )
                return weighted_rules

        except Exception as e:
            logger.warning(f"⚠️ Error applying recency weighting: {str(e)}")
            # Fallback to simple weighting
            for rule in rules:
                rule.recency_weight = 1.0
                rule.final_score = rule.confidence * rule.lift
            return rules

    async def _cache_rules(self, shop_id: str, rules: List[AssociationRule]) -> None:
        """Cache rules in Redis for fast inference"""
        try:
            redis_client = await self.get_redis_client()
            cache_key = f"fp_growth_rules:{shop_id}"

            # Convert rules to JSON-serializable format
            rules_data = [rule.to_dict() for rule in rules]

            # Cache for 24 hours
            await redis_client.setex(
                cache_key, 86400, json.dumps(rules_data)  # 24 hours
            )

            logger.info(f"💾 Cached {len(rules)} rules for shop {shop_id}")

        except Exception as e:
            logger.warning(f"⚠️ Failed to cache rules: {str(e)}")

    async def _load_cached_rules(self, shop_id: str) -> List[AssociationRule]:
        """Load cached rules from Redis"""
        try:
            redis_client = await self.get_redis_client()
            cache_key = f"fp_growth_rules:{shop_id}"

            cached_data = await redis_client.get(cache_key)
            if not cached_data:
                return []

            rules_data = json.loads(cached_data)
            rules = []

            for rule_dict in rules_data:
                rule = AssociationRule(
                    antecedent=rule_dict["antecedent"],
                    consequent=rule_dict["consequent"],
                    support=rule_dict["support"],
                    confidence=rule_dict["confidence"],
                    lift=rule_dict["lift"],
                    recency_weight=rule_dict["recency_weight"],
                    final_score=rule_dict["final_score"],
                )
                rules.append(rule)

            return rules

        except Exception as e:
            logger.warning(f"⚠️ Failed to load cached rules: {str(e)}")
            return []

    def _find_matching_rules(
        self, rules: List[AssociationRule], cart_items: List[str]
    ) -> List[AssociationRule]:
        """Find rules where antecedent matches cart items"""
        matching_rules = []
        cart_set = set(cart_items)

        for rule in rules:
            # Check if cart contains all antecedent items
            if all(item in cart_set for item in rule.antecedent):
                matching_rules.append(rule)

        return matching_rules

    def _rank_recommendations(
        self, rules: List[AssociationRule], cart_items: List[str], limit: int
    ) -> List[Dict[str, Any]]:
        """Rank and format recommendations"""
        # Group by consequent item and sum scores
        item_scores = defaultdict(float)

        for rule in rules:
            for item in rule.consequent:
                if item not in cart_items:  # Don't recommend items already in cart
                    item_scores[item] += rule.final_score

        # Sort by score and limit
        sorted_items = sorted(item_scores.items(), key=lambda x: x[1], reverse=True)

        recommendations = []
        for item_id, score in sorted_items[:limit]:
            recommendations.append(
                {
                    "id": item_id,
                    "score": score,
                    "reason": "Frequently bought together",
                    "source": "fp_growth_engine",
                }
            )

        return recommendations

    def _calculate_quality_metrics(
        self, rules: List[AssociationRule], transactions: List[List[str]]
    ) -> Dict[str, Any]:
        """Calculate quality metrics for the trained model"""
        if not rules:
            return {"error": "No rules to evaluate", "rule_count": 0}

        # Calculate coverage (how many products appear in rules)
        all_products = set()
        for transaction in transactions:
            all_products.update(transaction)

        rule_products = set()
        for rule in rules:
            rule_products.update(rule.antecedent)
            rule_products.update(rule.consequent)

        coverage = len(rule_products) / len(all_products) if all_products else 0

        # Calculate average confidence and lift
        avg_confidence = sum(rule.confidence for rule in rules) / len(rules)
        avg_lift = sum(rule.lift for rule in rules) / len(rules)

        return {
            "total_products": len(all_products),
            "covered_products": len(rule_products),
            "coverage": round(coverage, 3),
            "avg_confidence": round(avg_confidence, 3),
            "avg_lift": round(avg_lift, 3),
            "max_lift": round(max(rule.lift for rule in rules), 3),
            "rule_count": len(rules),
        }
