/**
 * Manual Testing Utilities for Trial Flow
 *
 * Provides tools to manually test the $200 trial flow in development
 */

import {
  getTrialStatus,
  updateTrialRevenue,
  createTrialPlan,
  completeTrialWithConsent,
} from "../trialStatus";
import prisma from "../../db.server";

export class TrialTestingUtils {
  private shopId: string;
  private shopDomain: string;

  constructor(shopId: string, shopDomain: string) {
    this.shopId = shopId;
    this.shopDomain = shopDomain;
  }

  /**
   * Test 1: Create Fresh Trial
   * Tests the initial trial creation flow
   */
  async testCreateTrial(): Promise<{
    success: boolean;
    status: any;
    error?: string;
  }> {
    try {
      console.log("🧪 Testing: Create Fresh Trial");

      const result = await createTrialPlan(this.shopId, this.shopDomain, "USD");

      if (!result) {
        return {
          success: false,
          status: null,
          error: "Failed to create trial plan",
        };
      }

      const status = await getTrialStatus(this.shopId);

      console.log("✅ Trial created successfully:", {
        isTrialActive: status.isTrialActive,
        currentRevenue: status.currentRevenue,
        threshold: status.threshold,
        remainingRevenue: status.remainingRevenue,
        progress: status.progress,
      });

      return { success: true, status };
    } catch (error) {
      console.error("❌ Error creating trial:", error);
      return { success: false, status: null, error: error.message };
    }
  }

  /**
   * Test 2: Simulate Revenue Generation
   * Tests revenue updates and progress tracking
   */
  async testRevenueUpdates(revenueAmounts: number[]): Promise<{
    success: boolean;
    results: any[];
    error?: string;
  }> {
    try {
      console.log("🧪 Testing: Revenue Updates");
      console.log("Revenue amounts to test:", revenueAmounts);

      const results = [];

      for (const amount of revenueAmounts) {
        console.log(`💰 Adding $${amount} in revenue...`);

        const result = await updateTrialRevenue(this.shopId, amount);

        if (!result) {
          return {
            success: false,
            results: [],
            error: `Failed to update revenue by $${amount}`,
          };
        }

        const status = await getTrialStatus(this.shopId);

        const resultData = {
          revenueAdded: amount,
          currentRevenue: status.currentRevenue,
          remainingRevenue: status.remainingRevenue,
          progress: status.progress,
          isTrialActive: status.isTrialActive,
          trialCompleted: status.trialCompleted,
          needsConsent: status.needsConsent,
        };

        results.push(resultData);

        console.log("📊 Status after update:", resultData);
      }

      return { success: true, results };
    } catch (error) {
      console.error("❌ Error updating revenue:", error);
      return { success: false, results: [], error: error.message };
    }
  }

  /**
   * Test 3: Complete Trial Flow
   * Tests the complete trial from start to finish
   */
  async testCompleteTrialFlow(): Promise<{
    success: boolean;
    steps: any[];
    error?: string;
  }> {
    try {
      console.log("🧪 Testing: Complete Trial Flow");

      const steps = [];

      // Step 1: Create trial
      console.log("Step 1: Creating trial...");
      const createResult = await this.testCreateTrial();
      if (!createResult.success) {
        return { success: false, steps: [], error: createResult.error };
      }
      steps.push({
        step: 1,
        action: "create_trial",
        result: createResult.status,
      });

      // Step 2: Add $100 revenue (50% complete)
      console.log("Step 2: Adding $100 revenue...");
      const revenueResult1 = await this.testRevenueUpdates([100]);
      if (!revenueResult1.success) {
        return { success: false, steps: [], error: revenueResult1.error };
      }
      steps.push({
        step: 2,
        action: "add_revenue_100",
        result: revenueResult1.results[0],
      });

      // Step 3: Add $50 more revenue (75% complete)
      console.log("Step 3: Adding $50 more revenue...");
      const revenueResult2 = await this.testRevenueUpdates([50]);
      if (!revenueResult2.success) {
        return { success: false, steps: [], error: revenueResult2.error };
      }
      steps.push({
        step: 3,
        action: "add_revenue_50",
        result: revenueResult2.results[0],
      });

      // Step 4: Add $50 more revenue (100% complete)
      console.log("Step 4: Adding $50 more revenue (completing trial)...");
      const revenueResult3 = await this.testRevenueUpdates([50]);
      if (!revenueResult3.success) {
        return { success: false, steps: [], error: revenueResult3.error };
      }
      steps.push({
        step: 4,
        action: "add_revenue_50_complete",
        result: revenueResult3.results[0],
      });

      // Step 5: Complete with consent
      console.log("Step 5: Completing trial with consent...");
      const consentResult = await completeTrialWithConsent(this.shopId);
      if (!consentResult) {
        return {
          success: false,
          steps: [],
          error: "Failed to complete trial with consent",
        };
      }
      steps.push({
        step: 5,
        action: "complete_with_consent",
        result: { success: true },
      });

      // Step 6: Verify final status
      console.log("Step 6: Verifying final status...");
      const finalStatus = await getTrialStatus(this.shopId);
      steps.push({
        step: 6,
        action: "verify_final_status",
        result: finalStatus,
      });

      console.log("✅ Complete trial flow tested successfully!");
      return { success: true, steps };
    } catch (error) {
      console.error("❌ Error in complete trial flow:", error);
      return { success: false, steps: [], error: error.message };
    }
  }

  /**
   * Test 4: Edge Cases
   * Tests various edge cases and error scenarios
   */
  async testEdgeCases(): Promise<{
    success: boolean;
    results: any[];
    error?: string;
  }> {
    try {
      console.log("🧪 Testing: Edge Cases");

      const results = [];

      // Test 1: Exact threshold amount
      console.log("Edge Case 1: Exact threshold amount ($200)");
      const exactThreshold = await this.testRevenueUpdates([200]);
      results.push({ case: "exact_threshold", result: exactThreshold });

      // Test 2: Revenue exceeding threshold
      console.log("Edge Case 2: Revenue exceeding threshold ($250)");
      const exceedingThreshold = await this.testRevenueUpdates([250]);
      results.push({ case: "exceeding_threshold", result: exceedingThreshold });

      // Test 3: Multiple small updates
      console.log("Edge Case 3: Multiple small updates");
      const smallUpdates = await this.testRevenueUpdates([
        10, 20, 30, 40, 50, 50,
      ]);
      results.push({ case: "small_updates", result: smallUpdates });

      return { success: true, results };
    } catch (error) {
      console.error("❌ Error testing edge cases:", error);
      return { success: false, results: [], error: error.message };
    }
  }

  /**
   * Test 5: Currency Support
   * Tests trial with different currencies
   */
  async testCurrencySupport(): Promise<{
    success: boolean;
    results: any[];
    error?: string;
  }> {
    try {
      console.log("🧪 Testing: Currency Support");

      const currencies = ["USD", "EUR", "GBP", "CAD", "AUD"];
      const results = [];

      for (const currency of currencies) {
        console.log(`Testing currency: ${currency}`);

        // Create trial with specific currency
        const createResult = await createTrialPlan(
          this.shopId,
          this.shopDomain,
          currency,
        );

        if (createResult) {
          const status = await getTrialStatus(this.shopId);
          results.push({ currency, status });
        }
      }

      return { success: true, results };
    } catch (error) {
      console.error("❌ Error testing currency support:", error);
      return { success: false, results: [], error: error.message };
    }
  }

  /**
   * Run All Tests
   * Executes all manual tests in sequence
   */
  async runAllTests(): Promise<{
    success: boolean;
    testResults: any;
    summary: any;
  }> {
    console.log("🚀 Starting Manual Trial Testing Suite");
    console.log("=====================================");

    const testResults = {
      createTrial: null,
      revenueUpdates: null,
      completeFlow: null,
      edgeCases: null,
      currencySupport: null,
    };

    try {
      // Test 1: Create Trial
      console.log("\n📋 Test 1: Create Trial");
      testResults.createTrial = await this.testCreateTrial();

      // Test 2: Revenue Updates
      console.log("\n📋 Test 2: Revenue Updates");
      testResults.revenueUpdates = await this.testRevenueUpdates([50, 100, 50]);

      // Test 3: Complete Flow
      console.log("\n📋 Test 3: Complete Flow");
      testResults.completeFlow = await this.testCompleteTrialFlow();

      // Test 4: Edge Cases
      console.log("\n📋 Test 4: Edge Cases");
      testResults.edgeCases = await this.testEdgeCases();

      // Test 5: Currency Support
      console.log("\n📋 Test 5: Currency Support");
      testResults.currencySupport = await this.testCurrencySupport();

      // Summary
      const summary = {
        totalTests: 5,
        passedTests: Object.values(testResults).filter(
          (result) => result?.success,
        ).length,
        failedTests: Object.values(testResults).filter(
          (result) => result?.success === false,
        ).length,
        successRate:
          (Object.values(testResults).filter((result) => result?.success)
            .length /
            5) *
          100,
      };

      console.log("\n📊 Test Summary");
      console.log("================");
      console.log(`Total Tests: ${summary.totalTests}`);
      console.log(`Passed: ${summary.passedTests}`);
      console.log(`Failed: ${summary.failedTests}`);
      console.log(`Success Rate: ${summary.successRate.toFixed(1)}%`);

      return {
        success: summary.failedTests === 0,
        testResults,
        summary,
      };
    } catch (error) {
      console.error("❌ Error running tests:", error);
      return {
        success: false,
        testResults,
        summary: { error: error.message },
      };
    }
  }
}

// Export for use in other files
export { TrialTestingUtils };
