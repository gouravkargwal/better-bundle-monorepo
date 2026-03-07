"""
Tests for FPGrowthEngine class.
Covers config defaults, fallback training, rule matching, ranking,
quality metrics, caching, AssociationRule serialization, and get_recommendations.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.recommandations.fp_growth_engine import (
    AssociationRule,
    FPGrowthConfig,
    FPGrowthEngine,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rule(
    antecedent, consequent, support=0.1, confidence=0.5, lift=2.0,
    recency_weight=1.0, final_score=None,
):
    if final_score is None:
        final_score = confidence * lift * recency_weight
    return AssociationRule(
        antecedent=antecedent,
        consequent=consequent,
        support=support,
        confidence=confidence,
        lift=lift,
        recency_weight=recency_weight,
        final_score=final_score,
    )


# Synthetic transactions used by the fallback-training tests.
TRAINING_TRANSACTIONS = [
    ["A", "B"], ["A", "B"], ["A", "B"], ["A", "B"],
    ["A", "B"], ["A", "B"], ["A", "B"], ["A", "B"],  # A+B  8/20
    ["A", "C"], ["A", "C"], ["A", "C"],               # A+C  3/20
    ["B", "C"], ["B", "C"],                            # B+C  2/20
    ["D", "E"], ["D", "E"],
    ["A", "B", "C"], ["A", "B", "C"],                  # triplets
    ["F", "G"], ["H", "I"], ["J", "K"],
]


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

class TestFPGrowthConfig:

    def test_default_config_values(self):
        cfg = FPGrowthConfig()
        assert cfg.min_support == 0.01
        assert cfg.min_confidence == 0.30
        assert cfg.min_lift == 1.5
        assert cfg.days_back == 90
        assert cfg.max_items_per_order == 20
        assert cfg.min_order_value == 0.0

    def test_default_recency_weights(self):
        cfg = FPGrowthConfig()
        assert cfg.recency_weights == {
            "0-30": 1.0,
            "30-60": 0.8,
            "60-90": 0.6,
        }


# ---------------------------------------------------------------------------
# Fallback training tests
# ---------------------------------------------------------------------------

class TestTrainFallback:

    @pytest.fixture
    def engine(self):
        cfg = FPGrowthConfig(
            min_support=0.05,
            min_confidence=0.3,
            min_lift=1.0,
        )
        return FPGrowthEngine(config=cfg)

    @pytest.mark.asyncio
    async def test_fallback_generates_rules(self, engine):
        rules = await engine._train_fallback(TRAINING_TRANSACTIONS)
        # A->B should exist (pair count 10, support 0.5, high confidence)
        a_to_b = [
            r for r in rules
            if r.antecedent == ["A"] and r.consequent == ["B"]
        ]
        assert len(a_to_b) >= 1
        rule = a_to_b[0]
        assert rule.support > 0
        assert rule.confidence >= 0.3
        assert rule.lift >= 1.0

    @pytest.mark.asyncio
    async def test_fallback_bidirectional(self, engine):
        rules = await engine._train_fallback(TRAINING_TRANSACTIONS)
        a_to_b = [
            r for r in rules
            if r.antecedent == ["A"] and r.consequent == ["B"]
        ]
        b_to_a = [
            r for r in rules
            if r.antecedent == ["B"] and r.consequent == ["A"]
        ]
        assert len(a_to_b) >= 1
        assert len(b_to_a) >= 1

    @pytest.mark.asyncio
    async def test_fallback_respects_thresholds(self, engine):
        rules = await engine._train_fallback(TRAINING_TRANSACTIONS)
        for rule in rules:
            assert rule.support >= engine.config.min_support
            assert rule.confidence >= engine.config.min_confidence
            assert rule.lift >= engine.config.min_lift


# ---------------------------------------------------------------------------
# Rule matching tests
# ---------------------------------------------------------------------------

class TestFindMatchingRules:

    @pytest.fixture
    def engine(self):
        return FPGrowthEngine()

    def test_find_matching_rules_exact_match(self, engine):
        rules = [_make_rule(["A"], ["B"])]
        result = engine._find_matching_rules(rules, ["A"])
        assert len(result) == 1

    def test_find_matching_rules_subset_match(self, engine):
        rules = [_make_rule(["A", "B"], ["C"])]
        result = engine._find_matching_rules(rules, ["A", "B", "C"])
        assert len(result) == 1

    def test_find_matching_rules_no_match(self, engine):
        rules = [_make_rule(["A"], ["B"])]
        result = engine._find_matching_rules(rules, ["X"])
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Ranking tests
# ---------------------------------------------------------------------------

class TestRankRecommendations:

    @pytest.fixture
    def engine(self):
        return FPGrowthEngine()

    def test_rank_excludes_cart_items(self, engine):
        rules = [
            _make_rule(["A"], ["B"], final_score=5.0),
            _make_rule(["A"], ["A"], final_score=9.0),  # consequent in cart
        ]
        recs = engine._rank_recommendations(rules, ["A"], limit=10)
        rec_ids = [r["id"] for r in recs]
        assert "A" not in rec_ids
        assert "B" in rec_ids

    def test_rank_sorted_by_score(self, engine):
        rules = [
            _make_rule(["A"], ["B"], final_score=1.0),
            _make_rule(["A"], ["C"], final_score=5.0),
            _make_rule(["A"], ["D"], final_score=3.0),
        ]
        recs = engine._rank_recommendations(rules, ["A"], limit=10)
        scores = [r["score"] for r in recs]
        assert scores == sorted(scores, reverse=True)
        assert recs[0]["id"] == "C"

    def test_rank_respects_limit(self, engine):
        rules = [
            _make_rule(["A"], ["B"], final_score=3.0),
            _make_rule(["A"], ["C"], final_score=2.0),
            _make_rule(["A"], ["D"], final_score=1.0),
        ]
        recs = engine._rank_recommendations(rules, ["A"], limit=2)
        assert len(recs) == 2


# ---------------------------------------------------------------------------
# Quality metrics tests
# ---------------------------------------------------------------------------

class TestCalculateQualityMetrics:

    @pytest.fixture
    def engine(self):
        return FPGrowthEngine()

    def test_quality_metrics_coverage(self, engine):
        transactions = [["A", "B"], ["C", "D"]]
        rules = [
            _make_rule(["A"], ["B"]),
            _make_rule(["C"], ["D"]),
        ]
        metrics = engine._calculate_quality_metrics(rules, transactions)
        assert metrics["total_products"] == 4
        assert metrics["covered_products"] == 4
        assert metrics["coverage"] == 1.0
        assert metrics["rule_count"] == 2
        assert "avg_confidence" in metrics
        assert "avg_lift" in metrics
        assert "max_lift" in metrics

    def test_quality_metrics_empty_rules(self, engine):
        metrics = engine._calculate_quality_metrics([], [["A", "B"]])
        assert metrics == {"error": "No rules to evaluate", "rule_count": 0}


# ---------------------------------------------------------------------------
# Caching tests
# ---------------------------------------------------------------------------

class TestCaching:

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        return redis

    @pytest.fixture
    def engine(self, mock_redis):
        eng = FPGrowthEngine()
        eng.redis_client = mock_redis
        return eng

    @pytest.mark.asyncio
    async def test_cache_rules_serializes(self, engine, mock_redis):
        rules = [_make_rule(["A"], ["B"], final_score=1.0)]
        await engine._cache_rules("shop_1", rules)

        mock_redis.setex.assert_awaited_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "fp_growth_rules:shop_1"
        assert call_args[0][1] == 86400
        data = json.loads(call_args[0][2])
        assert len(data) == 1
        assert data[0]["antecedent"] == ["A"]

    @pytest.mark.asyncio
    async def test_load_cached_rules_success(self, engine, mock_redis):
        rules_data = [_make_rule(["X"], ["Y"], final_score=2.5).to_dict()]
        mock_redis.get.return_value = json.dumps(rules_data)

        result = await engine._load_cached_rules("shop_1")
        mock_redis.get.assert_awaited_once_with("fp_growth_rules:shop_1")
        assert len(result) == 1
        assert isinstance(result[0], AssociationRule)
        assert result[0].antecedent == ["X"]
        assert result[0].final_score == 2.5

    @pytest.mark.asyncio
    async def test_load_cached_rules_miss_returns_empty(self, engine, mock_redis):
        mock_redis.get.return_value = None
        result = await engine._load_cached_rules("shop_1")
        assert result == []


# ---------------------------------------------------------------------------
# AssociationRule.to_dict
# ---------------------------------------------------------------------------

class TestAssociationRuleToDict:

    def test_to_dict(self):
        rule = AssociationRule(
            antecedent=["A", "B"],
            consequent=["C"],
            support=0.15,
            confidence=0.6,
            lift=2.0,
            recency_weight=0.9,
            final_score=1.08,
        )
        d = rule.to_dict()
        assert d == {
            "antecedent": ["A", "B"],
            "consequent": ["C"],
            "support": 0.15,
            "confidence": 0.6,
            "lift": 2.0,
            "recency_weight": 0.9,
            "final_score": 1.08,
        }


# ---------------------------------------------------------------------------
# get_recommendations (integration-style with mocks)
# ---------------------------------------------------------------------------

class TestGetRecommendations:

    @pytest.mark.asyncio
    async def test_get_recommendations_success(self):
        engine = FPGrowthEngine()

        # Mock redis with cached rules
        cached_rules = [
            _make_rule(["A"], ["B"], final_score=3.0).to_dict(),
            _make_rule(["A"], ["C"], final_score=1.0).to_dict(),
        ]
        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(cached_rules)
        engine.redis_client = mock_redis

        # Mock business rules filter (pass-through)
        engine.business_rules = MagicMock()
        engine.business_rules.filter_recommendations = AsyncMock(
            side_effect=lambda **kwargs: kwargs["recommendations"]
        )

        # Mock embeddings service (pass-through)
        engine.embeddings_service = MagicMock()
        engine.embeddings_service.boost_recommendations = AsyncMock(
            side_effect=lambda **kwargs: kwargs["recommendations"]
        )

        result = await engine.get_recommendations(
            shop_id="shop_1",
            cart_items=["A"],
            limit=5,
            cart_value=10.0,
        )

        assert result["success"] is True
        assert len(result["items"]) > 0
        item_ids = [i["id"] for i in result["items"]]
        assert "B" in item_ids
        assert "A" not in item_ids
        assert result["source"] == "fp_growth_engine_with_business_rules"
