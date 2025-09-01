/**
 * Performance-Based Billing Service
 * Calculates commissions based on recommendation performance and revenue attribution
 */

import { prisma } from "../db.server";

export interface PerformanceMetrics {
  conversionRate: number;
  revenuePerRecommendation: number;
  totalRecommendationsDisplayed: number;
  totalRecommendationsClicked: number;
  totalRecommendationsAddedToCart: number;
  totalRecommendationsPurchased: number;
  totalRevenueAttributed: number;
  averageOrderValue: number;
  customerRetentionRate: number;
  bundleEffectiveness: number;
}

export interface PerformanceTier {
  name: string;
  minConversionRate: number;
  maxConversionRate: number;
  baseCommissionRate: number;
  performanceBonus: number;
  totalCommissionRate: number;
  color: string;
}

export interface BillingCalculation {
  tier: PerformanceTier;
  commissionAmount: number;
  performanceScore: number;
  tierUpgradePotential: number;
  nextTierBonus: number;
  billingPeriod: string;
  startDate: Date;
  endDate: Date;
}

export class PerformanceBillingService {
  private readonly PERFORMANCE_TIERS: PerformanceTier[] = [
    {
      name: "Bronze",
      minConversionRate: 0,
      maxConversionRate: 5,
      baseCommissionRate: 0.015,
      performanceBonus: 0.0,
      totalCommissionRate: 0.015,
      color: "#CD7F32",
    },
    {
      name: "Silver",
      minConversionRate: 5,
      maxConversionRate: 10,
      baseCommissionRate: 0.015,
      performanceBonus: 0.005,
      totalCommissionRate: 0.02,
      color: "#C0C0C0",
    },
    {
      name: "Gold",
      minConversionRate: 10,
      maxConversionRate: 15,
      baseCommissionRate: 0.015,
      performanceBonus: 0.01,
      totalCommissionRate: 0.025,
      color: "#FFD700",
    },
    {
      name: "Platinum",
      minConversionRate: 15,
      maxConversionRate: 100,
      baseCommissionRate: 0.015,
      performanceBonus: 0.015,
      totalCommissionRate: 0.03,
      color: "#E5E4E2",
    },
  ];

  /**
   * Calculate performance metrics for a shop
   */
  async calculatePerformanceMetrics(
    shopId: string,
    startDate: Date,
    endDate: Date,
  ): Promise<PerformanceMetrics> {
    try {
      // Get analytics data for the period
      const analytics = await prisma.shopAnalytics.findUnique({
        where: { shopId },
      });

      if (!analytics) {
        throw new Error("Shop analytics not found");
      }

      // Get tracking events for the period
      const events = await prisma.trackingEvent.findMany({
        where: {
          shopId,
          timestamp: {
            gte: startDate,
            lte: endDate,
          },
        },
      });

      // Calculate conversion rates
      const conversionRate =
        analytics.totalRecommendationsDisplayed > 0
          ? (analytics.totalRecommendationsPurchased /
              analytics.totalRecommendationsDisplayed) *
            100
          : 0;

      const revenuePerRecommendation =
        analytics.totalRecommendationsDisplayed > 0
          ? analytics.totalRevenueAttributed /
            analytics.totalRecommendationsDisplayed
          : 0;

      const averageOrderValue =
        analytics.totalRecommendationsPurchased > 0
          ? analytics.totalRevenueAttributed /
            analytics.totalRecommendationsPurchased
          : 0;

      // Calculate customer retention (simplified - would need more complex logic)
      const customerRetentionRate = this.calculateCustomerRetention(events);

      // Calculate bundle effectiveness
      const bundleEffectiveness = this.calculateBundleEffectiveness(events);

      return {
        conversionRate: Math.round(conversionRate * 100) / 100,
        revenuePerRecommendation:
          Math.round(revenuePerRecommendation * 100) / 100,
        totalRecommendationsDisplayed: analytics.totalRecommendationsDisplayed,
        totalRecommendationsClicked: analytics.totalRecommendationsClicked,
        totalRecommendationsAddedToCart:
          analytics.totalRecommendationsAddedToCart,
        totalRecommendationsPurchased: analytics.totalRecommendationsPurchased,
        totalRevenueAttributed: analytics.totalRevenueAttributed,
        averageOrderValue: Math.round(averageOrderValue * 100) / 100,
        customerRetentionRate: Math.round(customerRetentionRate * 100) / 100,
        bundleEffectiveness: Math.round(bundleEffectiveness * 100) / 100,
      };
    } catch (error) {
      console.error("Error calculating performance metrics:", error);
      throw error;
    }
  }

  /**
   * Determine performance tier based on conversion rate
   */
  determinePerformanceTier(conversionRate: number): PerformanceTier {
    return (
      this.PERFORMANCE_TIERS.find(
        (tier) =>
          conversionRate >= tier.minConversionRate &&
          conversionRate < tier.maxConversionRate,
      ) || this.PERFORMANCE_TIERS[0]
    ); // Default to Bronze
  }

  /**
   * Calculate commission amount
   */
  calculateCommission(
    revenueAttributed: number,
    commissionRate: number,
  ): number {
    const commission = revenueAttributed * commissionRate;
    return commission;
  }

  /**
   * Calculate performance score (0-100)
   */
  calculatePerformanceScore(metrics: PerformanceMetrics): number {
    const weights = {
      conversionRate: 0.35,
      revenuePerRecommendation: 0.25,
      customerRetentionRate: 0.2,
      bundleEffectiveness: 0.2,
    };

    const normalizedConversionRate = Math.min(metrics.conversionRate / 20, 1); // 20% = perfect score
    const normalizedRevenuePerRec = Math.min(
      metrics.revenuePerRecommendation / 100,
      1,
    ); // $100 = perfect score
    const normalizedRetention = metrics.customerRetentionRate / 100;
    const normalizedBundleEffect = metrics.bundleEffectiveness / 100;

    const score =
      (normalizedConversionRate * weights.conversionRate +
        normalizedRevenuePerRec * weights.revenuePerRecommendation +
        normalizedRetention * weights.customerRetentionRate +
        normalizedBundleEffect * weights.bundleEffectiveness) *
      100;

    return Math.round(score);
  }

  /**
   * Calculate billing for a specific period
   */
  async calculateBilling(
    shopId: string,
    startDate: Date,
    endDate: Date,
  ): Promise<BillingCalculation> {
    try {
      const metrics = await this.calculatePerformanceMetrics(
        shopId,
        startDate,
        endDate,
      );
      const tier = this.determinePerformanceTier(metrics.conversionRate);
      const commissionAmount = this.calculateCommission(
        metrics.totalRevenueAttributed,
        tier.totalCommissionRate,
      );
      const performanceScore = this.calculatePerformanceScore(metrics);

      // Calculate tier upgrade potential
      const nextTier = this.PERFORMANCE_TIERS.find(
        (t) => t.minConversionRate > tier.minConversionRate,
      );
      const tierUpgradePotential = nextTier
        ? Math.max(0, nextTier.minConversionRate - metrics.conversionRate)
        : 0;

      // Calculate potential bonus from next tier
      const nextTierBonus =
        nextTier && metrics.totalRevenueAttributed > 0
          ? (nextTier.totalCommissionRate - tier.totalCommissionRate) *
            metrics.totalRevenueAttributed
          : 0;

      return {
        tier,
        commissionAmount: Math.round(commissionAmount * 100) / 100,
        performanceScore,
        tierUpgradePotential: Math.round(tierUpgradePotential * 100) / 100,
        nextTierBonus: Math.round(nextTierBonus * 100) / 100,
        billingPeriod: `${startDate.toLocaleDateString()} - ${endDate.toLocaleDateString()}`,
        startDate,
        endDate,
      };
    } catch (error) {
      console.error("Error calculating billing:", error);
      throw error;
    }
  }

  /**
   * Generate billing report for a shop
   */
  async generateBillingReport(
    shopId: string,
    months: number = 6,
  ): Promise<{
    currentPeriod: BillingCalculation;
    historicalBilling: BillingCalculation[];
    performanceTrends: any[];
    recommendations: string[];
  }> {
    try {
      const endDate = new Date();
      const startDate = new Date();
      startDate.setMonth(startDate.getMonth() - months);

      const currentPeriod = await this.calculateBilling(
        shopId,
        startDate,
        endDate,
      );

      // Generate historical billing for each month
      const historicalBilling: BillingCalculation[] = [];
      for (let i = 0; i < months; i++) {
        const monthStart = new Date();
        monthStart.setMonth(monthStart.getMonth() - i - 1);
        monthStart.setDate(1);

        const monthEnd = new Date(monthStart);
        monthEnd.setMonth(monthEnd.getMonth() + 1);
        monthEnd.setDate(0);

        const monthBilling = await this.calculateBilling(
          shopId,
          monthStart,
          monthEnd,
        );
        historicalBilling.push(monthBilling);
      }

      // Calculate performance trends
      const performanceTrends =
        this.calculatePerformanceTrends(historicalBilling);

      // Generate recommendations
      const recommendations = this.generateRecommendations(
        currentPeriod,
        performanceTrends,
      );

      return {
        currentPeriod,
        historicalBilling,
        performanceTrends,
        recommendations,
      };
    } catch (error) {
      console.error("Error generating billing report:", error);
      throw error;
    }
  }

  /**
   * Calculate performance trends over time
   */
  private calculatePerformanceTrends(
    historicalBilling: BillingCalculation[],
  ): any[] {
    return historicalBilling.map((billing, index) => ({
      period: billing.billingPeriod,
      performanceScore: billing.performanceScore,
      conversionRate: billing.tier.minConversionRate,
      commissionRate: billing.tier.commissionRate,
      commissionAmount: billing.commissionAmount,
      trend:
        index > 0
          ? billing.performanceScore -
            historicalBilling[index - 1].performanceScore
          : 0,
    }));
  }

  /**
   * Generate actionable recommendations
   */
  private generateRecommendations(
    currentBilling: BillingCalculation,
    trends: any[],
  ): string[] {
    const recommendations: string[] = [];

    // Tier upgrade recommendations
    if (currentBilling.tierUpgradePotential > 0) {
      recommendations.push(
        `Increase conversion rate by ${currentBilling.tierUpgradePotential}% to reach ${currentBilling.tier.name} tier and earn ${currentBilling.nextTierBonus > 0 ? `$${currentBilling.nextTierBonus} more` : "higher commission rate"}`,
      );
    }

    // Performance improvement recommendations
    if (currentBilling.performanceScore < 50) {
      recommendations.push(
        "Focus on improving recommendation relevance and user experience",
      );
    } else if (currentBilling.performanceScore < 75) {
      recommendations.push("Optimize product placement and bundle suggestions");
    }

    // Trend-based recommendations
    const recentTrend = trends[0]?.trend || 0;
    if (recentTrend < -10) {
      recommendations.push(
        "Performance declining - review recent changes and optimize",
      );
    } else if (recentTrend > 10) {
      recommendations.push(
        "Great progress! Consider testing new recommendation strategies",
      );
    }

    return recommendations;
  }

  /**
   * Calculate customer retention rate (simplified)
   */
  private calculateCustomerRetention(events: any[]): number {
    // This is a simplified calculation
    // In production, you'd need more sophisticated logic
    const uniqueCustomers = new Set(
      events.filter((e) => e.userId).map((e) => e.userId),
    ).size;

    const repeatCustomers = events
      .filter((e) => e.eventType === "recommendation_purchased")
      .filter((e) => e.userId).length;

    return uniqueCustomers > 0 ? (repeatCustomers / uniqueCustomers) * 100 : 0;
  }

  /**
   * Calculate bundle effectiveness
   */
  private calculateBundleEffectiveness(events: any[]): number {
    const bundleEvents = events.filter(
      (e) =>
        e.eventType === "recommendation_purchased" && e.metadata?.bundle_id,
    );

    const totalPurchases = events.filter(
      (e) => e.eventType === "recommendation_purchased",
    ).length;

    return totalPurchases > 0
      ? (bundleEvents.length / totalPurchases) * 100
      : 0;
  }

  /**
   * Get all performance tiers
   */
  getPerformanceTiers(): PerformanceTier[] {
    return [...this.PERFORMANCE_TIERS];
  }

  /**
   * Calculate potential earnings at different tiers
   */
  calculateTierComparison(revenueAttributed: number): Array<{
    tier: PerformanceTier;
    commission: number;
    difference: number;
  }> {
    return this.PERFORMANCE_TIERS.map((tier) => {
      const commission = this.calculateCommission(
        revenueAttributed,
        tier.totalCommissionRate,
      );

      const baseCommission = this.calculateCommission(
        revenueAttributed,
        this.PERFORMANCE_TIERS[0].totalCommissionRate,
      );

      return {
        tier,
        commission: Math.round(commission * 100) / 100,
        difference: Math.round((commission - baseCommission) * 100) / 100,
      };
    });
  }
}

// Export singleton instance
export const performanceBillingService = new PerformanceBillingService();
