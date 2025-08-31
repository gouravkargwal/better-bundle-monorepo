import { prisma } from '../database/prisma.server';

export interface HeuristicFactors {
  orderVolume: number;           // Orders per day
  revenueVelocity: number;       // Revenue per day
  productChurn: number;          // New/removed products percentage
  bundleEffectiveness: number;   // Bundle performance score (0-1)
  dataChangeRate: number;        // Percentage of data changed
  seasonality: number;           // Seasonal adjustment factor
  shopActivityLevel: 'low' | 'medium' | 'high';
  userEngagement: number;        // User interaction with recommendations
}

export interface HeuristicResult {
  nextAnalysisHours: number;
  factors: HeuristicFactors;
  reasoning: string[];
  confidence: number;
}

export class AnalysisHeuristicService {
  // Minimum and maximum intervals (1 day to 30 days)
  private static readonly MIN_INTERVAL_HOURS = 24;
  private static readonly MAX_INTERVAL_HOURS = 24 * 30;

  /**
   * Calculate next analysis time based on current analysis results
   */
  static async calculateNextAnalysisTime(
    shopId: string,
    analysisResult: any
  ): Promise<HeuristicResult> {
    try {
      console.log(`🧠 Calculating heuristic for shop: ${shopId}`);

      // Gather all heuristic factors
      const factors = await this.gatherHeuristicFactors(shopId, analysisResult);
      
      // Calculate individual intervals based on each factor
      const intervals = this.calculateFactorIntervals(factors);
      
      // Apply weights and calculate weighted average
      const weightedInterval = this.calculateWeightedInterval(intervals, factors);
      
      // Apply seasonal adjustments
      const seasonalInterval = this.applySeasonalAdjustment(weightedInterval, factors.seasonality);
      
      // Ensure within bounds (1-30 days)
      const finalInterval = this.clampInterval(seasonalInterval);
      
      // Generate reasoning
      const reasoning = this.generateReasoning(intervals, factors, finalInterval);
      
      // Calculate confidence score
      const confidence = this.calculateConfidence(factors);

      const result: HeuristicResult = {
        nextAnalysisHours: finalInterval,
        factors,
        reasoning,
        confidence,
      };

      console.log(`✅ Heuristic calculated: ${finalInterval} hours (${(finalInterval / 24).toFixed(1)} days)`);
      
      return result;
    } catch (error) {
      console.error('Error calculating heuristic:', error);
      // Fallback to default 7 days
      return {
        nextAnalysisHours: 24 * 7,
        factors: {} as HeuristicFactors,
        reasoning: ['Fallback to default 7-day interval due to calculation error'],
        confidence: 0.5,
      };
    }
  }

  /**
   * Gather all heuristic factors for a shop
   */
  private static async gatherHeuristicFactors(
    shopId: string,
    analysisResult: any
  ): Promise<HeuristicFactors> {
    const [
      orderVolume,
      revenueVelocity,
      productChurn,
      bundleEffectiveness,
      dataChangeRate,
      userEngagement
    ] = await Promise.all([
      this.calculateOrderVolume(shopId),
      this.calculateRevenueVelocity(shopId),
      this.calculateProductChurn(shopId),
      this.calculateBundleEffectiveness(analysisResult),
      this.calculateDataChangeRate(shopId),
      this.calculateUserEngagement(shopId),
    ]);

    const shopActivityLevel = this.determineActivityLevel(orderVolume);
    const seasonality = this.calculateSeasonality();

    return {
      orderVolume,
      revenueVelocity,
      productChurn,
      bundleEffectiveness,
      dataChangeRate,
      seasonality,
      shopActivityLevel,
      userEngagement,
    };
  }

  /**
   * Calculate daily order volume
   */
  private static async calculateOrderVolume(shopId: string): Promise<number> {
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const orderCount = await prisma.orderData.count({
      where: {
        shopId,
        orderDate: { gte: thirtyDaysAgo },
      },
    });

    return orderCount / 30; // Daily average
  }

  /**
   * Calculate daily revenue velocity
   */
  private static async calculateRevenueVelocity(shopId: string): Promise<number> {
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const orders = await prisma.orderData.findMany({
      where: {
        shopId,
        orderDate: { gte: thirtyDaysAgo },
      },
      select: { totalAmount: true },
    });

    const totalRevenue = orders.reduce((sum, order) => sum + order.totalAmount, 0);
    return totalRevenue / 30; // Daily average
  }

  /**
   * Calculate product churn rate
   */
  private static async calculateProductChurn(shopId: string): Promise<number> {
    const lastAnalysis = await prisma.analysisJob.findFirst({
      where: { shopId, status: 'completed' },
      orderBy: { completedAt: 'desc' },
    });

    if (!lastAnalysis) return 0;

    const productsBefore = await prisma.productData.count({
      where: { shopId },
    });

    // This is a simplified calculation - in a real implementation,
    // you'd track product additions/removals over time
    return 0.05; // Assume 5% churn for now
  }

  /**
   * Calculate bundle effectiveness from analysis results
   */
  private static calculateBundleEffectiveness(analysisResult: any): number {
    if (!analysisResult.bundles || analysisResult.bundles.length === 0) {
      return 0.3; // Default low effectiveness
    }

    // Calculate average confidence and lift
    const avgConfidence = analysisResult.bundles.reduce(
      (sum: number, bundle: any) => sum + bundle.confidence, 0
    ) / analysisResult.bundles.length;

    const avgLift = analysisResult.bundles.reduce(
      (sum: number, bundle: any) => sum + bundle.lift, 0
    ) / analysisResult.bundles.length;

    // Combine confidence and lift into effectiveness score
    const effectiveness = (avgConfidence * 0.6) + (Math.min(avgLift / 3, 1) * 0.4);
    return Math.min(Math.max(effectiveness, 0), 1);
  }

  /**
   * Calculate data change rate since last analysis
   */
  private static async calculateDataChangeRate(shopId: string): Promise<number> {
    const lastAnalysis = await prisma.analysisJob.findFirst({
      where: { shopId, status: 'completed' },
      orderBy: { completedAt: 'desc' },
    });

    if (!lastAnalysis) return 0.1; // Default 10% change

    const lastAnalysisDate = lastAnalysis.completedAt;
    
    // Count new orders since last analysis
    const newOrders = await prisma.orderData.count({
      where: {
        shopId,
        orderDate: { gt: lastAnalysisDate },
      },
    });

    // Count total orders in last analysis period
    const totalOrders = await prisma.orderData.count({
      where: { shopId },
    });

    return totalOrders > 0 ? newOrders / totalOrders : 0.1;
  }

  /**
   * Calculate user engagement with recommendations
   */
  private static async calculateUserEngagement(shopId: string): Promise<number> {
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const widgetEvents = await prisma.widgetEvent.findMany({
      where: {
        shopId,
        createdAt: { gte: thirtyDaysAgo },
      },
    });

    if (widgetEvents.length === 0) return 0.1; // Default low engagement

    // Calculate engagement score based on event types
    const clickEvents = widgetEvents.filter(e => e.eventType === 'bundle_click').length;
    const viewEvents = widgetEvents.filter(e => e.eventType === 'bundle_view').length;
    
    const engagementRate = viewEvents > 0 ? clickEvents / viewEvents : 0.1;
    return Math.min(engagementRate, 1);
  }

  /**
   * Determine shop activity level
   */
  private static determineActivityLevel(dailyOrders: number): 'low' | 'medium' | 'high' {
    if (dailyOrders > 20) return 'high';
    if (dailyOrders > 5) return 'medium';
    return 'low';
  }

  /**
   * Calculate seasonal adjustment factor
   */
  private static calculateSeasonality(): number {
    const now = new Date();
    const month = now.getMonth();
    const day = now.getDate();

    // Holiday season (November-December)
    if (month === 10 || month === 11) return 0.6; // 40% more frequent

    // Black Friday / Cyber Monday
    if (month === 10 && day >= 20) return 0.5; // 50% more frequent

    // Back to school (August-September)
    if (month === 7 || month === 8) return 0.7; // 30% more frequent

    // Valentine's Day
    if (month === 1 && day >= 10) return 0.8; // 20% more frequent

    // Mother's Day
    if (month === 4 && day >= 20) return 0.8; // 20% more frequent

    return 1.0; // Normal frequency
  }

  /**
   * Calculate intervals based on individual factors
   */
  private static calculateFactorIntervals(factors: HeuristicFactors) {
    return {
      orderBased: this.getOrderBasedInterval(factors.orderVolume),
      effectivenessBased: this.getEffectivenessBasedInterval(factors.bundleEffectiveness),
      changeBased: this.getChangeBasedInterval(factors.dataChangeRate),
      engagementBased: this.getEngagementBasedInterval(factors.userEngagement),
      activityBased: this.getActivityBasedInterval(factors.shopActivityLevel),
    };
  }

  /**
   * Order volume based interval
   */
  private static getOrderBasedInterval(dailyOrders: number): number {
    if (dailyOrders > 50) return 12;        // High activity: 12 hours
    if (dailyOrders > 20) return 24;        // Medium activity: 24 hours
    if (dailyOrders > 5) return 72;         // Low activity: 3 days
    return 168;                             // Very low: 1 week
  }

  /**
   * Bundle effectiveness based interval
   */
  private static getEffectivenessBasedInterval(effectiveness: number): number {
    if (effectiveness > 0.8) return 12;     // High performing: Run more often
    if (effectiveness > 0.6) return 24;     // Good performing: Standard
    if (effectiveness > 0.4) return 48;     // Medium performing: Less frequent
    if (effectiveness > 0.2) return 96;     // Low performing: 4 days
    return 168;                             // Poor performing: Weekly
  }

  /**
   * Data change rate based interval
   */
  private static getChangeBasedInterval(changeRate: number): number {
    if (changeRate > 0.2) return 6;         // High change: 6 hours
    if (changeRate > 0.1) return 12;        // Medium change: 12 hours
    if (changeRate > 0.05) return 24;       // Low change: 24 hours
    if (changeRate > 0.02) return 48;       // Minimal change: 2 days
    return 168;                             // Very low change: Weekly
  }

  /**
   * User engagement based interval
   */
  private static getEngagementBasedInterval(engagement: number): number {
    if (engagement > 0.3) return 12;        // High engagement: 12 hours
    if (engagement > 0.15) return 24;       // Medium engagement: 24 hours
    if (engagement > 0.05) return 48;       // Low engagement: 2 days
    return 168;                             // Very low engagement: Weekly
  }

  /**
   * Activity level based interval
   */
  private static getActivityBasedInterval(activityLevel: string): number {
    switch (activityLevel) {
      case 'high': return 12;               // High activity: 12 hours
      case 'medium': return 24;             // Medium activity: 24 hours
      case 'low': return 72;                // Low activity: 3 days
      default: return 168;                  // Default: Weekly
    }
  }

  /**
   * Calculate weighted interval from all factors
   */
  private static calculateWeightedInterval(intervals: any, factors: HeuristicFactors): number {
    const weights = {
      orderBased: 0.25,           // 25% weight
      effectivenessBased: 0.20,    // 20% weight
      changeBased: 0.20,          // 20% weight
      engagementBased: 0.15,      // 15% weight
      activityBased: 0.20,        // 20% weight
    };

    const weightedSum = Object.entries(intervals).reduce((sum, [key, interval]) => {
      return sum + (interval as number) * weights[key as keyof typeof weights];
    }, 0);

    return weightedSum;
  }

  /**
   * Apply seasonal adjustment
   */
  private static applySeasonalAdjustment(interval: number, seasonality: number): number {
    return interval * seasonality;
  }

  /**
   * Clamp interval to min/max bounds
   */
  private static clampInterval(interval: number): number {
    return Math.max(
      this.MIN_INTERVAL_HOURS,
      Math.min(this.MAX_INTERVAL_HOURS, interval)
    );
  }

  /**
   * Generate reasoning for the calculated interval
   */
  private static generateReasoning(
    intervals: any,
    factors: HeuristicFactors,
    finalInterval: number
  ): string[] {
    const reasoning: string[] = [];

    // Add reasoning for each factor
    if (factors.orderVolume > 20) {
      reasoning.push(`High order volume (${factors.orderVolume.toFixed(1)} orders/day) suggests frequent analysis`);
    } else if (factors.orderVolume < 5) {
      reasoning.push(`Low order volume (${factors.orderVolume.toFixed(1)} orders/day) allows less frequent analysis`);
    }

    if (factors.bundleEffectiveness > 0.7) {
      reasoning.push(`High bundle effectiveness (${(factors.bundleEffectiveness * 100).toFixed(0)}%) - running analysis more frequently`);
    } else if (factors.bundleEffectiveness < 0.3) {
      reasoning.push(`Low bundle effectiveness (${(factors.bundleEffectiveness * 100).toFixed(0)}%) - less frequent analysis needed`);
    }

    if (factors.dataChangeRate > 0.1) {
      reasoning.push(`High data change rate (${(factors.dataChangeRate * 100).toFixed(0)}%) requires frequent updates`);
    }

    if (factors.seasonality !== 1.0) {
      reasoning.push(`Seasonal adjustment applied (${factors.seasonality.toFixed(2)}x frequency)`);
    }

    reasoning.push(`Final interval: ${(finalInterval / 24).toFixed(1)} days`);

    return reasoning;
  }

  /**
   * Calculate confidence in the heuristic decision
   */
  private static calculateConfidence(factors: HeuristicFactors): number {
    let confidence = 0.5; // Base confidence

    // Higher confidence with more data
    if (factors.orderVolume > 10) confidence += 0.2;
    if (factors.userEngagement > 0.1) confidence += 0.1;
    if (factors.bundleEffectiveness > 0.5) confidence += 0.1;
    if (factors.dataChangeRate > 0.05) confidence += 0.1;

    return Math.min(confidence, 1.0);
  }

  /**
   * Store heuristic decision for learning
   */
  static async storeHeuristicDecision(
    shopId: string,
    heuristicResult: HeuristicResult,
    analysisResult: any
  ) {
    try {
      await prisma.heuristicDecision.create({
        data: {
          shopId,
          predictedInterval: heuristicResult.nextAnalysisHours,
          factors: heuristicResult.factors,
          reasoning: heuristicResult.reasoning,
          confidence: heuristicResult.confidence,
          analysisResult: analysisResult,
        },
      });
    } catch (error) {
      console.error('Error storing heuristic decision:', error);
    }
  }
}
