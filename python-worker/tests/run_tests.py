#!/usr/bin/env python3
"""
Simple Command-Line Test Runner for Attribution Scenarios

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py --scenario 6       # Run specific scenario
    python run_tests.py --generate-data   # Generate test data only
    python run_tests.py --performance     # Run performance tests only
"""

import asyncio
import argparse
import sys
import os
from datetime import datetime

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_runner import AttributionScenarioTester
from test_data_generator import AttributionTestDataGenerator


def print_banner():
    """Print test suite banner"""
    print("=" * 80)
    print("🧪 ATTRIBUTION SCENARIOS TEST SUITE")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


def print_scenario_list():
    """Print available scenarios"""
    scenarios = {
        6: "Multiple Recommendations for Same Product",
        7: "Cross-Extension Attribution",
        8: "Session vs Customer Attribution",
        9: "Long Attribution Window",
        10: "Multiple Sessions Same Customer",
        11: "Refund Attribution",
        12: "Partial Refund Attribution",
        14: "Payment Failure Attribution",
        15: "Subscription Cancellation",
        17: "Cross-Shop Attribution",
        18: "Cross-Device Attribution",
        19: "Client ID vs Session ID Attribution",
        20: "Session Expiration During Journey",
        21: "Low-Quality Recommendations",
        22: "Recommendation Timing",
        26: "Data Loss Recovery",
        27: "Fraudulent Attribution Detection",
        28: "Attribution Manipulation Detection",
        33: "Anonymous to Customer Conversion",
        34: "Multiple Devices Same Customer",
    }

    print("\n📋 Available Scenarios:")
    for num, name in scenarios.items():
        print(f"  {num:2d}. {name}")
    print()


async def run_specific_scenario(scenario_num: int):
    """Run a specific scenario test"""
    tester = AttributionScenarioTester()

    scenario_methods = {
        6: tester.test_scenario_6_multiple_recommendations,
        7: tester.test_scenario_7_cross_extension_attribution,
        14: tester.test_scenario_14_payment_failure,
        15: tester.test_scenario_15_subscription_cancellation,
        17: tester.test_scenario_17_cross_shop_attribution,
        21: tester.test_scenario_21_low_quality_recommendations,
        22: tester.test_scenario_22_recommendation_timing,
        26: tester.test_scenario_26_data_loss_recovery,
        27: tester.test_scenario_27_fraudulent_attribution,
        28: tester.test_scenario_28_attribution_manipulation,
        33: tester.test_scenario_33_anonymous_to_customer_conversion,
        34: tester.test_scenario_34_multiple_devices_same_customer,
    }

    if scenario_num not in scenario_methods:
        print(f"❌ Scenario {scenario_num} not found or not implemented")
        return

    print(f"🧪 Running Scenario {scenario_num}...")
    try:
        result = await scenario_methods[scenario_num]()
        print(f"✅ Scenario {scenario_num} completed: {result.get('success', False)}")
        return result
    except Exception as e:
        print(f"❌ Scenario {scenario_num} failed: {e}")
        return {"success": False, "error": str(e)}


async def run_performance_tests():
    """Run performance tests only"""
    print("🚀 Running Performance Tests...")
    tester = AttributionScenarioTester()
    result = await tester.test_performance_scenarios()
    print(f"✅ Performance test completed: {result.get('success', False)}")
    return result


def generate_test_data():
    """Generate test data"""
    print("📊 Generating Test Data...")
    generator = AttributionTestDataGenerator()
    test_data = generator.save_test_data()
    print("✅ Test data generation completed")
    return test_data


async def run_all_tests():
    """Run all tests"""
    print("🚀 Running All Attribution Scenario Tests...")
    tester = AttributionScenarioTester()
    results = await tester.run_all_tests()
    return results


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Attribution Scenarios Test Runner")
    parser.add_argument("--scenario", type=int, help="Run specific scenario number")
    parser.add_argument(
        "--generate-data", action="store_true", help="Generate test data only"
    )
    parser.add_argument(
        "--performance", action="store_true", help="Run performance tests only"
    )
    parser.add_argument("--list", action="store_true", help="List available scenarios")
    parser.add_argument("--all", action="store_true", help="Run all tests (default)")

    args = parser.parse_args()

    print_banner()

    if args.list:
        print_scenario_list()
        return

    if args.generate_data:
        generate_test_data()
        return

    if args.scenario:
        asyncio.run(run_specific_scenario(args.scenario))
    elif args.performance:
        asyncio.run(run_performance_tests())
    else:
        # Default: run all tests
        asyncio.run(run_all_tests())


if __name__ == "__main__":
    main()
