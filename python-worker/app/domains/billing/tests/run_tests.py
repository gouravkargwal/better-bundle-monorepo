#!/usr/bin/env python3
"""
Billing System Test Runner

This script runs all billing system tests and provides detailed reporting.
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import List, Dict, Any

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_billing_system import run_integration_tests


class TestReporter:
    """Test result reporter."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.test_results = []
        self.passed_tests = 0
        self.failed_tests = 0
    
    def start_test_suite(self):
        """Start the test suite."""
        self.start_time = datetime.utcnow()
        print("🚀 Starting Billing System Test Suite")
        print("=" * 60)
    
    def end_test_suite(self):
        """End the test suite and print summary."""
        self.end_time = datetime.utcnow()
        duration = (self.end_time - self.start_time).total_seconds()
        
        print("\n" + "=" * 60)
        print("📊 TEST SUITE SUMMARY")
        print("=" * 60)
        print(f"⏱️  Duration: {duration:.2f} seconds")
        print(f"✅ Passed: {self.passed_tests}")
        print(f"❌ Failed: {self.failed_tests}")
        print(f"📈 Success Rate: {(self.passed_tests / (self.passed_tests + self.failed_tests) * 100):.1f}%")
        
        if self.failed_tests == 0:
            print("\n🎉 ALL TESTS PASSED! Billing system is ready for production.")
            return True
        else:
            print(f"\n⚠️  {self.failed_tests} tests failed. Please review and fix issues.")
            return False
    
    def record_test_result(self, test_name: str, passed: bool, error: str = None):
        """Record a test result."""
        self.test_results.append({
            "name": test_name,
            "passed": passed,
            "error": error,
            "timestamp": datetime.utcnow()
        })
        
        if passed:
            self.passed_tests += 1
            print(f"✅ {test_name}")
        else:
            self.failed_tests += 1
            print(f"❌ {test_name}: {error}")


async def run_billing_tests():
    """Run all billing system tests."""
    reporter = TestReporter()
    reporter.start_test_suite()
    
    try:
        # Run the integration tests
        await run_integration_tests()
        
        # If we get here, all tests passed
        reporter.record_test_result("Billing System Integration Tests", True)
        
    except Exception as e:
        reporter.record_test_result("Billing System Integration Tests", False, str(e))
    
    # Print final summary
    success = reporter.end_test_suite()
    
    return success


def main():
    """Main entry point."""
    print("🧪 Better Bundle Billing System Test Suite")
    print("=" * 60)
    
    try:
        # Run the tests
        success = asyncio.run(run_billing_tests())
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n⏹️  Test suite interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
