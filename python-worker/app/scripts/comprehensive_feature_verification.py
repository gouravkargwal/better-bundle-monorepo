#!/usr/bin/env python3
"""
Comprehensive Feature Verification Script
Verifies all feature types and their computation status
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

# Add the python-worker directory to Python path
python_worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, python_worker_dir)

from app.core.database.session import get_session_factory
from app.core.logging import get_logger
from app.core.database.models.shop import Shop
from app.core.database.models import (
    ProductData,
    CustomerData,
    OrderData,
    LineItemData,
    CollectionData,
    UserSession,
    UserInteraction,
    UserIdentityLink,
)
from app.core.database.models import PurchaseAttribution
from app.core.database.models import (
    RefundData,
    RefundLineItemData,
    RefundAttributionAdjustment,
)
from app.core.database.models import (
    ProductFeatures,
    CollectionFeatures,
    SessionFeatures,
    CustomerBehaviorFeatures,
    SearchProductFeatures,
    ProductPairFeatures,
    InteractionFeatures,
)
from app.domains.ml.services.feature_engineering import FeatureEngineeringService

logger = get_logger(__name__)


class ComprehensiveFeatureVerifier:
    """Comprehensive feature verification system"""

    def __init__(self):
        self.session_factory = None
        self.shop_id = None
        self.verification_results = {}

    async def initialize(self):
        """Initialize the verifier"""
        self.session_factory = await get_session_factory()

    async def verify_all_features(self) -> Dict[str, Any]:
        """Verify all features comprehensively"""
        print("🔍 Starting comprehensive feature verification...")

        async with self.session_factory() as session:
            # Global snapshot (unscoped) to detect environment/data issues
            await self._print_shops_overview(session)
            await self._print_global_counts(session)

            # Get the latest shop
            shop = await session.scalar(select(Shop).order_by(Shop.created_at.desc()))
            if not shop:
                print("❌ No shop found in database")
                return {"error": "No shop found"}

            # Ensure shop_id used in filters is a string to avoid type mismatch (UUID vs String)
            self.shop_id = str(shop.id)
            print(f"🏪 Verifying features for shop: {self.shop_id}")

            # Type check: compare shop_id type in a sample table
            await self._print_shop_id_type_checks(session)

            # Verify all feature types
            results = await asyncio.gather(
                self._verify_input_data(session),
                self._verify_product_features(session),
                self._verify_collection_features(session),
                self._verify_session_features(session),
                self._verify_customer_behavior_features(session),
                self._verify_search_product_features(session),
                self._verify_interaction_features(session),
                self._verify_product_pair_features(session),
                self._verify_purchase_attribution_features(session),
                self._verify_refund_features(session),
                return_exceptions=True,
            )

            # Compile results
            verification_results = {
                "shop_id": self.shop_id,
                "timestamp": datetime.utcnow().isoformat(),
                "input_data": (
                    results[0]
                    if not isinstance(results[0], Exception)
                    else {"error": str(results[0])}
                ),
                "product_features": (
                    results[1]
                    if not isinstance(results[1], Exception)
                    else {"error": str(results[1])}
                ),
                "collection_features": (
                    results[2]
                    if not isinstance(results[2], Exception)
                    else {"error": str(results[2])}
                ),
                "session_features": (
                    results[3]
                    if not isinstance(results[3], Exception)
                    else {"error": str(results[3])}
                ),
                "customer_behavior_features": (
                    results[4]
                    if not isinstance(results[4], Exception)
                    else {"error": str(results[4])}
                ),
                "search_product_features": (
                    results[5]
                    if not isinstance(results[5], Exception)
                    else {"error": str(results[5])}
                ),
                "interaction_features": (
                    results[6]
                    if not isinstance(results[6], Exception)
                    else {"error": str(results[6])}
                ),
                "product_pair_features": (
                    results[7]
                    if not isinstance(results[7], Exception)
                    else {"error": str(results[7])}
                ),
                "purchase_attribution_features": (
                    results[8]
                    if not isinstance(results[8], Exception)
                    else {"error": str(results[8])}
                ),
                "refund_features": (
                    results[9]
                    if not isinstance(results[9], Exception)
                    else {"error": str(results[9])}
                ),
            }
            # Generate summary
            await self._generate_summary(verification_results)

            return verification_results

    async def _verify_input_data(self, session) -> Dict[str, Any]:
        """Verify input data availability (data that is directly seeded)"""
        print("\n📊 Verifying Seeded Input Data...")

        # Count all input data types
        product_count = await session.scalar(
            select(func.count(ProductData.id)).where(
                ProductData.shop_id == self.shop_id
            )
        )
        customer_count = await session.scalar(
            select(func.count(CustomerData.id)).where(
                CustomerData.shop_id == self.shop_id
            )
        )
        order_count = await session.scalar(
            select(func.count(OrderData.id)).where(OrderData.shop_id == self.shop_id)
        )
        collection_count = await session.scalar(
            select(func.count(CollectionData.id)).where(
                CollectionData.shop_id == self.shop_id
            )
        )
        session_count = await session.scalar(
            select(func.count(UserSession.id)).where(
                UserSession.shop_id == self.shop_id
            )
        )
        interaction_count = await session.scalar(
            select(func.count(UserInteraction.id)).where(
                UserInteraction.shop_id == self.shop_id
            )
        )
        attribution_count = await session.scalar(
            select(func.count(PurchaseAttribution.id)).where(
                PurchaseAttribution.shop_id == self.shop_id
            )
        )
        refund_count = await session.scalar(
            select(func.count(RefundData.id)).where(RefundData.shop_id == self.shop_id)
        )
        search_product_features_count = await session.scalar(
            select(func.count(SearchProductFeatures.id)).where(
                SearchProductFeatures.shop_id == self.shop_id
            )
        )

        # Check data quality
        recent_interactions = await session.scalar(
            select(func.count(UserInteraction.id)).where(
                and_(
                    UserInteraction.shop_id == self.shop_id,
                    UserInteraction.created_at >= datetime.utcnow() - timedelta(days=1),
                )
            )
        )

        search_interactions = await session.scalar(
            select(func.count(UserInteraction.id)).where(
                and_(
                    UserInteraction.shop_id == self.shop_id,
                    UserInteraction.interaction_type == "search_submitted",
                )
            )
        )

        return {
            "product_data": product_count,
            "customer_data": customer_count,
            "order_data": order_count,
            "collection_data": collection_count,
            "user_sessions": session_count,
            "user_interactions": interaction_count,
            "purchase_attributions": attribution_count,
            "refund_data": refund_count,
            "search_product_features": search_product_features_count,
            "recent_interactions": recent_interactions,
            "search_interactions": search_interactions,
            "data_quality": {
                "has_recent_data": recent_interactions > 0,
                "has_search_data": search_interactions > 0,
                "has_attribution_data": attribution_count > 0,
                "has_refund_data": refund_count > 0,
                "has_search_features": search_product_features_count > 0,
            },
        }

    async def _print_shops_overview(self, session) -> None:
        """Print list of shops and quick per-shop counts to aid diagnostics."""
        print("\n🧭 Shops overview (top 10):")
        shops = (
            (
                await session.execute(
                    select(Shop).order_by(Shop.created_at.desc()).limit(10)
                )
            )
            .scalars()
            .all()
        )
        if not shops:
            print("  (no shops)")
            return
        for s in shops:
            sid = str(s.id)
            # quick counts per shop (lightweight)
            ui = await session.scalar(
                select(func.count(UserInteraction.id)).where(
                    UserInteraction.shop_id == sid
                )
            )
            us = await session.scalar(
                select(func.count(UserSession.id)).where(UserSession.shop_id == sid)
            )
            pf = await session.scalar(
                select(func.count(ProductFeatures.id)).where(
                    ProductFeatures.shop_id == sid
                )
            )
            cf = await session.scalar(
                select(func.count(CollectionFeatures.id)).where(
                    CollectionFeatures.shop_id == sid
                )
            )
            print(
                f"  • {sid} | interactions={ui} sessions={us} product_features={pf} collection_features={cf}"
            )

    async def _print_global_counts(self, session) -> None:
        """Print global counts (unscoped) to distinguish empty DB vs shop filter mismatch."""
        print("\n🌐 Global counts (unscoped):")
        global_counts = {
            "ProductData": await session.scalar(select(func.count(ProductData.id))),
            "CustomerData": await session.scalar(select(func.count(CustomerData.id))),
            "OrderData": await session.scalar(select(func.count(OrderData.id))),
            "CollectionData": await session.scalar(
                select(func.count(CollectionData.id))
            ),
            "UserSession": await session.scalar(select(func.count(UserSession.id))),
            "UserInteraction": await session.scalar(
                select(func.count(UserInteraction.id))
            ),
            "PurchaseAttribution": await session.scalar(
                select(func.count(PurchaseAttribution.id))
            ),
            "RefundData": await session.scalar(select(func.count(RefundData.id))),
            "ProductFeatures": await session.scalar(
                select(func.count(ProductFeatures.id))
            ),
            "CollectionFeatures": await session.scalar(
                select(func.count(CollectionFeatures.id))
            ),
            "SessionFeatures": await session.scalar(
                select(func.count(SessionFeatures.id))
            ),
            "CustomerBehaviorFeatures": await session.scalar(
                select(func.count(CustomerBehaviorFeatures.id))
            ),
            "SearchProductFeatures": await session.scalar(
                select(func.count(SearchProductFeatures.id))
            ),
            "InteractionFeatures": await session.scalar(
                select(func.count(InteractionFeatures.id))
            ),
            "ProductPairFeatures": await session.scalar(
                select(func.count(ProductPairFeatures.id))
            ),
        }
        for k, v in global_counts.items():
            print(f"  {k}: {v}")

    async def _print_shop_id_type_checks(self, session) -> None:
        """Print type diagnostics for shop_id fields across representative tables."""
        print("\n🔎 Shop ID type checks:")

        # Take one sample row from each table if present and print the python type of shop_id
        async def sample_type(model, name: str):
            row = await session.scalar(select(model).limit(1))
            if not row:
                print(f"  {name}: (no rows)")
            else:
                v = getattr(row, "shop_id", None)
                print(f"  {name}.shop_id type: {type(v).__name__} value: {v}")

        await sample_type(UserSession, "UserSession")
        await sample_type(UserInteraction, "UserInteraction")
        await sample_type(ProductData, "ProductData")
        await sample_type(CollectionData, "CollectionData")
        await sample_type(ProductFeatures, "ProductFeatures")

    # A helper function to check computed features
    async def _verify_computed_feature(
        self, session, model, feature_name: str
    ) -> Dict[str, Any]:
        """Generic verifier for a computed feature table."""
        print(f"⚙️  Verifying {feature_name}...")

        count = await session.scalar(
            select(func.count(model.id)).where(model.shop_id == self.shop_id)
        )

        if count > 0:
            sample = await session.scalar(
                select(model).where(model.shop_id == self.shop_id).limit(1)
            )
            return {
                "count": count,
                "status": "✅ Available",
                "sample_id": getattr(sample, "id", None) if sample else None,
            }
        else:
            return {
                "count": 0,
                "status": "🟡 Missing (Expected, generated by Feature Engineering service)",
                "sample_id": None,
            }

    async def _verify_product_features(self, session) -> Dict[str, Any]:
        """Verify product features"""
        return await self._verify_computed_feature(
            session, ProductFeatures, "Product Features"
        )

    async def _verify_collection_features(self, session) -> Dict[str, Any]:
        """Verify collection features"""
        return await self._verify_computed_feature(
            session, CollectionFeatures, "Collection Features"
        )

    async def _verify_session_features(self, session) -> Dict[str, Any]:
        """Verify session features"""
        return await self._verify_computed_feature(
            session, SessionFeatures, "Session Features"
        )

    async def _verify_customer_behavior_features(self, session) -> Dict[str, Any]:
        """Verify customer behavior features"""
        return await self._verify_computed_feature(
            session, CustomerBehaviorFeatures, "Customer Behavior Features"
        )

    async def _verify_interaction_features(self, session) -> Dict[str, Any]:
        """Verify interaction features"""
        return await self._verify_computed_feature(
            session, InteractionFeatures, "Interaction Features"
        )

    async def _verify_product_pair_features(self, session) -> Dict[str, Any]:
        """Verify product pair features"""
        return await self._verify_computed_feature(
            session, ProductPairFeatures, "Product Pair Features"
        )

    async def _verify_search_product_features(self, session) -> Dict[str, Any]:
        """Verify search product features (this one is seeded)"""
        print("🔍 Verifying Search Product Features (Seeded)...")

        count = await session.scalar(
            select(func.count(SearchProductFeatures.id)).where(
                SearchProductFeatures.shop_id == self.shop_id
            )
        )

        if count > 0:
            sample = await session.scalar(
                select(SearchProductFeatures)
                .where(SearchProductFeatures.shop_id == self.shop_id)
                .limit(1)
            )

            return {
                "count": count,
                "status": "✅ Available",
                "sample_product_id": sample.product_id if sample else None,
            }
        else:
            # Check if we have search interactions, which are the inputs
            search_interaction_count = await session.scalar(
                select(func.count(UserInteraction.id)).where(
                    and_(
                        UserInteraction.shop_id == self.shop_id,
                        UserInteraction.interaction_type == "search_submitted",
                    )
                )
            )

            return {
                "count": 0,
                "status": "❌ Missing",
                "sample_product_id": None,
                "input_analysis": {
                    "search_interactions": search_interaction_count,
                    "has_required_input": search_interaction_count > 0,
                },
            }

    async def _verify_purchase_attribution_features(self, session) -> Dict[str, Any]:
        """Verify purchase attribution data (seeded)"""
        print("💰 Verifying Purchase Attribution Data (Seeded)...")

        count = await session.scalar(
            select(func.count(PurchaseAttribution.id)).where(
                PurchaseAttribution.shop_id == self.shop_id
            )
        )

        if count > 0:
            sample = await session.scalar(
                select(PurchaseAttribution)
                .where(PurchaseAttribution.shop_id == self.shop_id)
                .limit(1)
            )

            return {
                "count": count,
                "status": "✅ Available",
                "sample_attribution": (
                    {
                        "order_id": sample.order_id,
                        "total_revenue": float(sample.total_revenue),
                        "contributing_extensions": sample.contributing_extensions,
                    }
                    if sample
                    else None
                ),
            }
        else:
            return {"count": 0, "status": "❌ Missing", "sample_attribution": None}

    async def _verify_refund_features(self, session) -> Dict[str, Any]:
        """Verify refund data (seeded)"""
        print("💸 Verifying Refund Data (Seeded)...")

        # MODIFIED: Simplified and more robust query.
        # The seeder populates shop_id on RefundData, so we can rely on that directly.
        # This avoids potential type mismatch issues when joining on order_id.
        refund_ids_for_shop_subq = select(RefundData.id).where(
            RefundData.shop_id == self.shop_id
        )

        refund_count = await session.scalar(
            select(func.count(RefundData.id)).where(RefundData.shop_id == self.shop_id)
        )

        if refund_count == 0:
            # FIXED: Return a dictionary for the "missing" case to prevent errors.
            return {
                "refund_data": 0,
                "line_items": 0,
                "adjustments": 0,
                "status": "❌ Missing",
                "sample_refund": None,
            }

        line_item_count = await session.scalar(
            select(func.count(RefundLineItemData.id)).where(
                RefundLineItemData.refund_id.in_(refund_ids_for_shop_subq)
            )
        )

        adjustment_count = await session.scalar(
            select(func.count(RefundAttributionAdjustment.id)).where(
                RefundAttributionAdjustment.shop_id == self.shop_id
            )
        )

        sample_refund = await session.scalar(
            select(RefundData)
            .where(RefundData.id.in_(refund_ids_for_shop_subq))
            .limit(1)
        )

        return {
            "refund_data": refund_count,
            "line_items": line_item_count,
            "adjustments": adjustment_count,
            "status": "✅ Available",
            "sample_refund": (
                {
                    "order_id": sample_refund.order_id,
                    "total_refund_amount": float(sample_refund.total_refund_amount),
                    "refunded_at": sample_refund.refunded_at.isoformat(),
                }
                if sample_refund
                else None
            ),
        }

    async def _generate_summary(self, results: Dict[str, Any]):
        """Generate a comprehensive and actionable summary"""
        print("\n" + "=" * 80)
        print("📋 COMPREHENSIVE FEATURE VERIFICATION SUMMARY")
        print("=" * 80)
        print(f"Shop ID: {results.get('shop_id')}")

        # --- Seeded Data Summary ---
        print("\n📊 SEEDED DATA (Should be present after running the seeder)")
        input_data = results.get("input_data", {})
        seeded_items = [
            ("Products", "product_data"),
            ("Customers", "customer_data"),
            ("Orders", "order_data"),
            ("Collections", "collection_data"),
            ("User Sessions", "user_sessions"),
            ("User Interactions", "user_interactions"),
        ]
        for name, key in seeded_items:
            count = input_data.get(key, 0)
            status = "✅" if count > 0 else "❌"
            print(f"  {name:<25}: {count:<5} records {status}")

        # --- Seeded Analytics Data ---
        print("\n💰 SEEDED ANALYTICS DATA (Should be present after running the seeder)")
        attribution_data = results.get("purchase_attribution_features", {})
        refund_data = results.get("refund_features", {})
        search_features_data = results.get("search_product_features", {})

        print(
            f"  Purchase Attributions: {attribution_data.get('count', 0)} records {attribution_data.get('status', '❌')}"
        )
        print(
            f"  Refund Data:           {refund_data.get('refund_data', 0)} records {refund_data.get('status', '❌')}"
        )
        print(
            f"  Search Product Features: {search_features_data.get('count', 0)} records {search_features_data.get('status', '❌')}"
        )

        # --- Computed Features Summary ---
        print("\n⚙️  COMPUTED FEATURES (Generated by the Feature Engineering service)")
        computed_feature_types = [
            ("Product Features", "product_features"),
            ("Collection Features", "collection_features"),
            ("Session Features", "session_features"),
            ("Customer Behavior Features", "customer_behavior_features"),
            ("Interaction Features", "interaction_features"),
            ("Product Pair Features", "product_pair_features"),
        ]
        for name, key in computed_feature_types:
            feature_data = results.get(key, {})
            count = feature_data.get("count", 0)
            status = feature_data.get("status", "❌ Unknown")
            print(f"  {name:<25}: {count:<5} records {status}")

        # --- Issues and Recommendations ---
        print("\n🔧 ISSUES & RECOMMENDATIONS:")
        has_issues = False

        # Check for missing seeded data
        for name, key in seeded_items:
            if input_data.get(key, 0) == 0:
                print(
                    f"  ❌ Critical: Seeded '{name}' data is missing. Check the SeedPipelineRunner script."
                )
                has_issues = True

        if search_features_data.get("count", 0) == 0:
            print(
                f"  ❌ Critical: Seeded 'Search Product Features' data is missing. Ensure it's called in the seeder."
            )
            has_issues = True

        # Check data quality
        data_quality = input_data.get("data_quality", {})
        if not data_quality.get("has_recent_data", False):
            print(f"  ⚠️  Warning: No recent interaction data found (last 24h).")
            has_issues = True
        if not data_quality.get("has_search_data", False):
            print(f"  ⚠️  Warning: No 'search_submitted' interactions found.")
            has_issues = True

        # Guidance on computed features
        missing_computed_features = [
            name
            for name, key in computed_feature_types
            if results.get(key, {}).get("count", 0) == 0
        ]
        if missing_computed_features:
            print(
                f"  ℹ️  Info: The following computed features are missing as expected: {', '.join(missing_computed_features)}."
            )
            print(
                f"     → To generate them, run the Feature Engineering pipeline/service after the seeder."
            )
        else:
            print("  ✅ All computed features have been generated.")

        if not has_issues and not missing_computed_features:
            print(
                "  ✅ All checks passed! Seeded data and computed features are present."
            )
        elif not has_issues and missing_computed_features:
            print(
                "  ✅ All seeded data is present. You can now proceed to run the feature engineering service."
            )

        print(f"\n✅ Verification completed at {datetime.utcnow().isoformat()}")


async def main():
    """Main verification function"""
    verifier = ComprehensiveFeatureVerifier()
    await verifier.initialize()

    try:
        results = await verifier.verify_all_features()
        return results
    except Exception as e:
        logger.error(f"Verification failed: {e}", exc_info=True)
        print(f"❌ Verification failed: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    asyncio.run(main())
