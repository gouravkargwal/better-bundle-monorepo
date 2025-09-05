#!/usr/bin/env python3
"""
Script to analyze feature importance for Gorse recommendations
Run this to discover which features matter most for your shop
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.domains.ml.services.feature_importance_service import FeatureImportanceService
from app.core.logging import get_logger

logger = get_logger(__name__)


async def main():
    """Main function to run feature importance analysis"""

    print("🔍 GORSE FEATURE IMPORTANCE ANALYZER")
    print("=" * 50)

    # Initialize the service
    service = FeatureImportanceService()

    # Analyze feature importance for a shop
    shop_id = "your-shop-id"  # Replace with your actual shop ID

    print(f"📊 Analyzing feature importance for shop: {shop_id}")
    print("⏳ This may take a few minutes...")

    try:
        # Run the analysis
        results = await service.analyze_feature_importance_for_shop(
            shop_id=shop_id,
            days_back=30,  # Analyze last 30 days
            min_samples=50,  # Need at least 50 samples
        )

        if "error" in results:
            print(f"❌ Error: {results['error']}")
            return

        # Display results
        print("\n✅ ANALYSIS COMPLETE!")
        print("=" * 50)

        print(f"📈 Samples analyzed: {results['samples_analyzed']}")
        print(f"📅 Analysis date: {results['analysis_date']}")

        # Show top features
        print("\n🏆 TOP 10 MOST IMPORTANT FEATURES:")
        print("-" * 50)
        for i, feature in enumerate(results["top_features"][:10], 1):
            importance = results["importance_scores"].get(feature, 0)
            print(f"{i:2d}. {feature:<40} {importance:.3f}")

        # Show feature weights
        print("\n⚖️  RECOMMENDED FEATURE WEIGHTS:")
        print("-" * 50)
        weights = results["feature_weights"]
        sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)

        for feature, weight in sorted_weights[:15]:
            print(f"{feature:<40} {weight:.3f}")

        # Show full report
        print("\n📋 DETAILED REPORT:")
        print("-" * 50)
        print(results["report"])

        # Show how to use the weights
        print("\n🛠️  HOW TO USE THESE WEIGHTS:")
        print("-" * 50)
        print("1. Copy the feature weights above")
        print("2. Add them to your feature generators")
        print("3. Multiply each feature by its weight")
        print("4. This will improve your recommendation accuracy!")

        print("\n💡 EXAMPLE USAGE:")
        print("-" * 50)
        print(
            """
# In your feature generator:
def apply_feature_weights(features):
    weights = {
        "customer_product_affinity_score": 0.9,
        "purchase_intent_score": 0.9,
        "view_to_cart_conversion": 0.8,
        # ... add more weights from the analysis
    }
    
    weighted_features = {}
    for feature_name, value in features.items():
        weight = weights.get(feature_name, 0.5)
        weighted_features[feature_name] = value * weight
    
    return weighted_features
        """
        )

    except Exception as e:
        print(f"❌ Failed to analyze features: {str(e)}")
        logger.error(f"Feature importance analysis failed: {str(e)}")


async def run_optimization_experiment():
    """Run a feature optimization experiment"""

    print("\n🧪 FEATURE OPTIMIZATION EXPERIMENT")
    print("=" * 50)

    service = FeatureImportanceService()
    shop_id = "your-shop-id"  # Replace with your actual shop ID

    try:
        results = await service.run_feature_optimization_experiment(
            shop_id=shop_id, test_duration_days=7
        )

        if "error" in results:
            print(f"❌ Error: {results['error']}")
            return

        print("✅ EXPERIMENT COMPLETE!")
        print(f"🏆 Winner: {results['winner']}")
        print(f"📈 Click rate improvement: {results['improvement']['click_rate']:.1%}")
        print(
            f"💰 Conversion rate improvement: {results['improvement']['conversion_rate']:.1%}"
        )
        print(f"💡 Recommendation: {results['recommendation']}")

    except Exception as e:
        print(f"❌ Experiment failed: {str(e)}")


if __name__ == "__main__":
    print("🚀 Starting Gorse Feature Importance Analysis...")

    # Run the main analysis
    asyncio.run(main())

    # Ask if user wants to run experiment
    print("\n" + "=" * 50)
    response = input(
        "🧪 Would you like to run a feature optimization experiment? (y/n): "
    )

    if response.lower() in ["y", "yes"]:
        asyncio.run(run_optimization_experiment())

    print(
        "\n🎉 Analysis complete! Use these insights to improve your Gorse recommendations."
    )
