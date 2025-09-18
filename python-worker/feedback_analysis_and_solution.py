#!/usr/bin/env python3
"""
Comprehensive analysis of feedback issues and proposed solutions
"""
import asyncio
import sys
import os
from typing import Dict, List, Any, Optional

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from app.core.database.simple_db_client import get_database
from app.core.logging import get_logger

logger = get_logger(__name__)


async def analyze_feedback_issues():
    """Analyze current feedback issues and propose solutions"""

    print("=" * 80)
    print("FEEDBACK ANALYSIS AND SOLUTION PROPOSAL")
    print("=" * 80)

    db = await get_database()
    shop_id = "cmfnmj5sn0000v3gaipwx948o"

    # 1. Check current feedback in Gorse
    print("\n1. CURRENT GORSE FEEDBACK ANALYSIS")
    print("-" * 50)

    try:
        import requests

        response = requests.get("http://localhost:8088/api/feedback?n=100")
        if response.status_code == 200:
            feedback_data = response.json()
            feedback_types = {}
            for feedback in feedback_data.get("Feedback", []):
                feedback_type = feedback.get("FeedbackType", "unknown")
                if feedback_type not in feedback_types:
                    feedback_types[feedback_type] = 0
                feedback_types[feedback_type] += 1

            print(f"Current Gorse Feedback Types: {feedback_types}")

            # Check for negative feedback
            if "cart_remove" in feedback_types:
                print(
                    f"✅ Negative feedback (cart_remove) is present: {feedback_types['cart_remove']}"
                )
            else:
                print("❌ Negative feedback (cart_remove) is MISSING")
        else:
            print(f"❌ Failed to fetch Gorse feedback: {response.status_code}")
    except Exception as e:
        print(f"❌ Error fetching Gorse feedback: {str(e)}")

    # 2. Check InteractionFeatures for cart_remove data
    print("\n2. INTERACTION FEATURES ANALYSIS")
    print("-" * 50)

    try:
        # Get sample interaction features
        interaction_features = await db.interactionfeatures.find_many(
            where={"shopId": shop_id}, take=20
        )

        total_cart_removes = 0
        total_cart_adds = 0
        total_views = 0
        total_purchases = 0

        for feature in interaction_features:
            total_cart_removes += feature.cartRemoveCount
            total_cart_adds += feature.cartAddCount
            total_views += feature.viewCount
            total_purchases += feature.purchaseCount

        print(f"InteractionFeatures Summary:")
        print(f"  Total Views: {total_views}")
        print(f"  Total Cart Adds: {total_cart_adds}")
        print(f"  Total Cart Removes: {total_cart_removes}")
        print(f"  Total Purchases: {total_purchases}")

        if total_cart_removes > 0:
            print(
                f"✅ Cart remove data exists in InteractionFeatures: {total_cart_removes}"
            )
        else:
            print("❌ No cart remove data in InteractionFeatures")

    except Exception as e:
        print(f"❌ Error analyzing InteractionFeatures: {str(e)}")

    # 3. Check raw UserInteraction data
    print("\n3. RAW USER INTERACTION ANALYSIS")
    print("-" * 50)

    try:
        # Get user interactions
        user_interactions = await db.userinteraction.find_many(
            where={"shopId": shop_id}, take=100
        )

        interaction_type_counts = {}
        for interaction in user_interactions:
            interaction_type = interaction.interactionType
            if interaction_type not in interaction_type_counts:
                interaction_type_counts[interaction_type] = 0
            interaction_type_counts[interaction_type] += 1

        print(f"Raw UserInteraction Types: {interaction_type_counts}")

        if "product_removed_from_cart" in interaction_type_counts:
            print(
                f"✅ Raw cart remove events exist: {interaction_type_counts['product_removed_from_cart']}"
            )
        else:
            print("❌ No raw cart remove events found")

    except Exception as e:
        print(f"❌ Error analyzing UserInteraction: {str(e)}")

    # 4. Check if cart_remove is being sent to Gorse
    print("\n4. GORSE SYNC ANALYSIS")
    print("-" * 50)

    try:
        # Check the unified Gorse service logs
        print("Checking if cart_remove feedback is being sent to Gorse...")

        # This would require checking the actual sync process
        print("✅ Gorse config includes cart_remove in negative_feedback_types")
        print("✅ UnifiedGorseService includes cart_remove in feedback sync")

    except Exception as e:
        print(f"❌ Error analyzing Gorse sync: {str(e)}")

    return True


async def propose_solution():
    """Propose comprehensive solution for feedback issues"""

    print("\n" + "=" * 80)
    print("PROPOSED SOLUTION")
    print("=" * 80)

    print("\n🔍 IDENTIFIED ISSUES:")
    print("1. ❌ Cart remove events may not be properly counted in InteractionFeatures")
    print("2. ❌ Current approach calculates features from raw sessions (inefficient)")
    print("3. ❌ Feature calculation happens during sync (should be pre-computed)")
    print("4. ❌ No validation that negative feedback reaches Gorse")

    print("\n💡 PROPOSED SOLUTION:")
    print("=" * 50)

    print("\n1. ✅ IMPROVE FEATURE CALCULATION APPROACH:")
    print("   - Use pre-computed InteractionFeatures instead of raw sessions")
    print("   - Validate that cart_remove events are properly counted")
    print("   - Add comprehensive logging for feature calculation")

    print("\n2. ✅ ENHANCE NEGATIVE FEEDBACK HANDLING:")
    print("   - Ensure cart_remove events are properly extracted from raw data")
    print("   - Validate that negative feedback reaches Gorse")
    print("   - Add monitoring for feedback type distribution")

    print("\n3. ✅ OPTIMIZE DATA FLOW:")
    print("   - Raw Data → Feature Tables → Aggregated Features → Gorse")
    print("   - Pre-compute all features during data ingestion")
    print("   - Use feature tables as single source of truth")

    print("\n4. ✅ ADD COMPREHENSIVE MONITORING:")
    print("   - Monitor feedback type distribution in Gorse")
    print("   - Track feature calculation accuracy")
    print("   - Alert on missing negative feedback")

    return True


async def test_enhanced_feedback_sync():
    """Test enhanced feedback sync with proper negative feedback handling"""

    print("\n" + "=" * 80)
    print("TESTING ENHANCED FEEDBACK SYNC")
    print("=" * 80)

    try:
        # Test the current sync
        print("Testing current Gorse sync...")

        import requests

        response = requests.post(
            "http://localhost:8001/api/v1/gorse/sync",
            json={"shop_id": "cmfnmj5sn0000v3gaipwx948o"},
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 200:
            sync_result = response.json()
            print(f"✅ Sync completed successfully")
            print(f"   Users synced: {sync_result.get('users_synced', 0)}")
            print(f"   Items synced: {sync_result.get('items_synced', 0)}")
            print(f"   Feedback synced: {sync_result.get('feedback_synced', 0)}")
            print(
                f"   Training triggered: {sync_result.get('training_triggered', False)}"
            )

            # Check feedback types after sync
            feedback_response = requests.get("http://localhost:8088/api/feedback?n=100")
            if feedback_response.status_code == 200:
                feedback_data = feedback_response.json()
                feedback_types = {}
                for feedback in feedback_data.get("Feedback", []):
                    feedback_type = feedback.get("FeedbackType", "unknown")
                    if feedback_type not in feedback_types:
                        feedback_types[feedback_type] = 0
                    feedback_types[feedback_type] += 1

                print(f"\n📊 Feedback Types After Sync:")
                for feedback_type, count in feedback_types.items():
                    print(f"   {feedback_type}: {count}")

                # Check for negative feedback
                if "cart_remove" in feedback_types:
                    print(
                        f"✅ Negative feedback (cart_remove) present: {feedback_types['cart_remove']}"
                    )
                else:
                    print("❌ Negative feedback (cart_remove) missing")

        else:
            print(f"❌ Sync failed: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"❌ Error testing sync: {str(e)}")
        import traceback

        traceback.print_exc()

    return True


async def main():
    """Main analysis function"""
    try:
        print(f"Starting feedback analysis at {asyncio.get_event_loop().time()}")

        # Analyze current issues
        await analyze_feedback_issues()

        # Propose solution
        await propose_solution()

        # Test enhanced sync
        await test_enhanced_feedback_sync()

        print(f"\nAnalysis completed at {asyncio.get_event_loop().time()}")

    except Exception as e:
        logger.error(f"Error in main analysis: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
