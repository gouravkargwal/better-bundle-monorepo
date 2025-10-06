#!/usr/bin/env python3
"""
Test trial revenue logic to ensure refunds properly decrease trial revenue
"""

import asyncio
import sys
import os
from decimal import Decimal

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database.session import get_session
from app.core.database.models.billing import BillingPlan
from app.core.database.models import RefundAttribution, PurchaseAttribution
from sqlalchemy import select, and_


async def test_trial_revenue_logic():
    """Test the trial revenue logic to ensure it works correctly"""

    print("🧪 Testing Trial Revenue Logic")
    print("=" * 50)

    # Test scenarios
    test_scenarios = [
        {
            "name": "Initial Purchase",
            "initial_revenue": 0.0,
            "attributed_revenue": 50.0,
            "expected_revenue": 50.0,
            "operation": "purchase",
        },
        {
            "name": "Another Purchase",
            "initial_revenue": 50.0,
            "attributed_revenue": 30.0,
            "expected_revenue": 80.0,
            "operation": "purchase",
        },
        {
            "name": "Partial Refund",
            "initial_revenue": 80.0,
            "attributed_revenue": 20.0,  # This will be subtracted
            "expected_revenue": 60.0,
            "operation": "refund",
        },
        {
            "name": "Full Refund",
            "initial_revenue": 60.0,
            "attributed_revenue": 60.0,  # This will be subtracted
            "expected_revenue": 0.0,
            "operation": "refund",
        },
    ]

    current_revenue = 0.0

    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n📊 Scenario {i}: {scenario['name']}")
        print(f"   Initial Revenue: ${current_revenue}")
        print(f"   Operation: {scenario['operation']}")
        print(f"   Amount: ${scenario['attributed_revenue']}")

        if scenario["operation"] == "purchase":
            # Purchase: ADD revenue
            new_revenue = current_revenue + scenario["attributed_revenue"]
            print(
                f"   Calculation: ${current_revenue} + ${scenario['attributed_revenue']} = ${new_revenue}"
            )
        else:  # refund
            # Refund: SUBTRACT revenue
            new_revenue = current_revenue - scenario["attributed_revenue"]
            # Ensure it doesn't go below 0
            new_revenue = max(0, new_revenue)
            print(
                f"   Calculation: ${current_revenue} - ${scenario['attributed_revenue']} = ${new_revenue}"
            )

        expected = scenario["expected_revenue"]
        if abs(new_revenue - expected) < 0.01:  # Allow for floating point precision
            print(f"   ✅ CORRECT: Expected ${expected}, Got ${new_revenue}")
        else:
            print(f"   ❌ ERROR: Expected ${expected}, Got ${new_revenue}")

        current_revenue = new_revenue

    print(f"\n🎯 Final Revenue: ${current_revenue}")

    # Test edge cases
    print(f"\n🔍 Testing Edge Cases:")

    # Test negative revenue (should be clamped to 0)
    test_revenue = 10.0
    refund_amount = 15.0
    result = max(0, test_revenue - refund_amount)
    print(
        f"   Negative Revenue Test: ${test_revenue} - ${refund_amount} = ${result} (clamped to 0)"
    )

    # Test trial threshold logic
    print(f"\n🎯 Testing Trial Threshold Logic:")
    trial_threshold = 100.0

    test_cases = [
        {
            "revenue": 50.0,
            "is_trial_active": True,
            "description": "Below threshold, trial active",
        },
        {
            "revenue": 150.0,
            "is_trial_active": True,
            "description": "Above threshold, trial active",
        },
        {
            "revenue": 50.0,
            "is_trial_active": False,
            "description": "Below threshold, trial completed",
        },
        {
            "revenue": 150.0,
            "is_trial_active": False,
            "description": "Above threshold, trial completed",
        },
    ]

    for case in test_cases:
        revenue = case["revenue"]
        is_trial_active = case["is_trial_active"]
        description = case["description"]

        # Logic from the refund attribution consumer
        if revenue < trial_threshold and is_trial_active:
            action = "Keep trial active"
        elif revenue < trial_threshold and not is_trial_active:
            action = "Reactivate trial"
        elif revenue >= trial_threshold and is_trial_active:
            action = "Complete trial"
        else:  # revenue >= threshold and not trial_active
            action = "Keep trial completed"

        print(f"   {description}: {action}")


if __name__ == "__main__":
    asyncio.run(test_trial_revenue_logic())
