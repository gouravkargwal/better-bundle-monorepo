import { prisma } from "../../../core/database/prisma.server";
import type {
  BundleAnalysisConfig,
  Bundle,
  AnalysisResults,
  ProcessedOrder,
} from "../../../types";
import { ANALYSIS_CONFIG } from "../../../constants";

export class BundleAnalyticsService {
  private config: BundleAnalysisConfig;

  constructor(config?: Partial<BundleAnalysisConfig>) {
    // Start with minimal config - thresholds will be calculated dynamically
    this.config = {
      minSupport: 0, // Will be calculated based on store data
      minConfidence: 0, // Will be calculated based on store data
      minLift: 0, // Will be calculated based on store data
      maxBundleSize: 2, // Currently only supports size 2 (pairs)
      analysisWindow: ANALYSIS_CONFIG.DEFAULT_ANALYSIS_WINDOW,
      minRevenue: 0,
      minUniqueCustomers: 1,
      minAvgOrderValue: 0,
      minBundleFrequency: 1,
      maxBundlePrice: 1000,
      minBundlePrice: 0,
      categoryCompatibility: false,
      inventoryCheck: false,
      excludeOutOfStock: false,
      seasonalFiltering: false,
      customerSegmentFiltering: false,
      marginThreshold: 0,
      bundleComplexity: "moderate",
      ...config,
    };
  }

  /**
   * Optimize thresholds using provided order data
   */
  private async optimizeThresholdsWithData(
    shopId: string,
    orderData: ProcessedOrder[],
  ): Promise<BundleAnalysisConfig> {
    try {
      if (!orderData || orderData.length === 0) {
        console.log(`⚠️ No order data available, using fallback thresholds`);
        return this.getFallbackThresholds(0, 2);
      }

      const orderCount = orderData.length;
      const totalProducts = new Set(
        orderData.flatMap((order) =>
          order.lineItems.map((item) => item.productId),
        ),
      ).size;

      // Debug: Let's see what product IDs we're actually getting
      const allProductIds = orderData.flatMap((order) =>
        order.lineItems.map((item) => item.productId),
      );
      const uniqueProductIds = [...new Set(allProductIds)];

      console.log(`📊 Data characteristics for optimization:`, {
        orderCount,
        totalProducts,
        avgProductsPerOrder: totalProducts / orderCount,
        dataDensity: totalProducts / Math.max(orderCount, 1),
        debug: {
          totalLineItems: orderData.reduce(
            (sum, order) => sum + order.lineItems.length,
            0,
          ),
          allProductIds: allProductIds.length,
          uniqueProductIds: uniqueProductIds.length,
          sampleProductIds: uniqueProductIds.slice(0, 5), // Show first 5 product IDs
          // DEBUG: Show actual line item structure
          sampleLineItems: orderData.slice(0, 1).flatMap((order) =>
            order.lineItems.slice(0, 2).map((item, index) => {
              console.log(
                `📊 Analysis Line Item ${index + 1}:`,
                JSON.stringify(item, null, 2),
              );
              return {
                productId: item.productId,
                hasProductId: !!item.productId,
                productIdType: typeof item.productId,
                itemKeys: Object.keys(item || {}),
              };
            }),
          ),
        },
      });

      // Find optimal thresholds based on data characteristics
      const optimalThresholds = this.findOptimalThresholds(
        orderCount,
        totalProducts,
      );

      console.log(`✅ Optimized thresholds for ${shopId}:`, optimalThresholds);

      return {
        ...this.config,
        ...optimalThresholds,
      };
    } catch (error) {
      console.error(`❌ Error optimizing thresholds for ${shopId}:`, error);
      return this.getFallbackThresholds(0, 2);
    }
  }

  /**
   * Find optimal thresholds based on data characteristics
   */
  private findOptimalThresholds(
    orderCount: number,
    productCount: number,
  ): Partial<BundleAnalysisConfig> {
    console.log(
      `🧮 Calculating optimal thresholds for ${orderCount} orders and ${productCount} products`,
    );

    // Base thresholds on data volume
    let minSupport = 0.01;
    let minConfidence = 0.3;
    let minLift = 1.2;
    let maxBundleSize = 3;

    // Adjust based on order count
    if (orderCount < 20) {
      minSupport = 0.05;
      minConfidence = 0.5;
      minLift = 1.5;
      maxBundleSize = 2;
    } else if (orderCount < 50) {
      minSupport = 0.03;
      minConfidence = 0.4;
      minLift = 1.3;
      maxBundleSize = 3;
    } else if (orderCount < 100) {
      minSupport = 0.02;
      minConfidence = 0.35;
      minLift = 1.25;
      maxBundleSize = 3;
    } else {
      minSupport = 0.01;
      minConfidence = 0.3;
      minLift = 1.2;
      maxBundleSize = 4;
    }

    // Adjust based on product count
    if (productCount < 10) {
      minSupport = Math.max(minSupport, 0.1);
      maxBundleSize = Math.min(maxBundleSize, 2);
    } else if (productCount > 100) {
      minSupport = Math.max(minSupport, 0.005);
      maxBundleSize = Math.min(maxBundleSize, 4);
    }

    const result = {
      minSupport,
      minConfidence,
      minLift,
      maxBundleSize,
    };

    console.log(`🎯 Final calculated thresholds:`, result);
    return result;
  }

  /**
   * Generate reasoning for threshold choices
   */
  private generateThresholdReasoning(
    thresholds: Partial<BundleAnalysisConfig>,
    orderCount: number,
    productCount: number,
  ): string {
    const reasons = [];

    if (orderCount < 20) {
      reasons.push("Higher thresholds due to limited order data");
    } else if (orderCount > 100) {
      reasons.push("Lower thresholds due to abundant order data");
    }

    if (productCount < 10) {
      reasons.push("Higher support threshold due to small product catalog");
    } else if (productCount > 100) {
      reasons.push("Lower support threshold due to large product catalog");
    }

    return reasons.join("; ");
  }

  /**
   * Get fallback thresholds when optimization fails
   */
  private getFallbackThresholds(
    orderCount: number,
    productCount: number,
  ): BundleAnalysisConfig {
    return {
      ...this.config,
      minSupport: 0.05,
      minConfidence: 0.4,
      minLift: 1.3,
      maxBundleSize: 2,
    };
  }

  /**
   * Fetch order data for analysis
   */
  private async fetchOrderData(shopId: string): Promise<ProcessedOrder[]> {
    try {
      const shop = await prisma.shop.findUnique({
        where: { shopId },
        select: { id: true },
      });

      if (!shop) {
        throw new Error(`Shop not found: ${shopId}`);
      }

      const orders = await prisma.orderData.findMany({
        where: { shopId: shop.id },
        orderBy: { orderDate: "desc" },
        take: 1000, // Limit to recent orders for performance
      });

      return orders.map((order) => ({
        orderId: order.orderId,
        customerId: order.customerId || undefined,
        totalAmount: order.totalAmount,
        orderDate: order.orderDate,
        lineItems: ((order.lineItems as any[]) || []).map((item: any) => ({
          productId: item.product?.id || item.productId, // Fix: Extract from nested product.id
          variantId: item.variant?.id || item.variantId,
          quantity: item.quantity,
          price: parseFloat(item.variant?.price || item.price || "0"),
          product: item.product,
          variant: item.variant,
        })),
      }));
    } catch (error) {
      console.error(`Error fetching order data for ${shopId}:`, error);
      return [];
    }
  }

  /**
   * Analyze shop and extract bundle opportunities
   */
  async analyzeShop(shopId: string): Promise<AnalysisResults> {
    try {
      console.log(`🚀 Starting bundle analysis for shop: ${shopId}`);

      // Fetch order data once and reuse it
      const orderData = await this.fetchOrderData(shopId);
      if (!orderData || orderData.length === 0) {
        throw new Error("No order data available for analysis");
      }

      // Optimize thresholds using the already fetched data
      console.log(`🔧 Starting smart threshold optimization for ${shopId}...`);
      const optimizedThresholds = await this.optimizeThresholdsWithData(
        shopId,
        orderData,
      );
      this.config = { ...this.config, ...optimizedThresholds };

      console.log(`🎯 Smart optimization results:`, {
        original: {
          minSupport: 0,
          minConfidence: 0,
          minLift: 0,
          maxBundleSize: 2,
        },
        optimized: optimizedThresholds,
        final: {
          minSupport: this.config.minSupport,
          minConfidence: this.config.minConfidence,
          minLift: this.config.minLift,
          maxBundleSize: this.config.maxBundleSize,
        },
      });

      // Extract product pairs (bundles of size 2)
      // TODO: For bundles of size 3+, implement Apriori/FP-Growth algorithms
      const productPairs = this.extractProductPairs(orderData);
      const bundles = this.extractProductBundles(productPairs, orderData);

      // Calculate summary statistics
      const summary = this.calculateSummary(bundles);

      const results: AnalysisResults = {
        bundles,
        summary,
        metadata: {
          ordersAnalyzed: orderData.length,
          productsAnalyzed: new Set(
            orderData.flatMap((order) =>
              order.lineItems.map((item) => item.productId),
            ),
          ).size,
          analysisDate: new Date().toISOString(),
        },
      };

      console.log(
        `✅ Analysis complete for ${shopId}: Found ${bundles.length} bundle opportunities`,
      );
      return results;
    } catch (error) {
      console.error(`❌ Error analyzing shop ${shopId}:`, error);
      throw error;
    }
  }

  /**
   * Extract product pairs from order data
   *
   * Note: This method is specifically designed for bundles of size 2 (pairs).
   * For bundles of size 3+, we would need to implement Apriori or FP-Growth algorithms.
   * The maxBundleSize config is currently not used but kept for future expansion.
   *
   * @param orders - Array of processed orders
   * @returns Map of product pairs and their co-purchase frequencies
   */
  private extractProductPairs(orders: ProcessedOrder[]): Map<string, number> {
    const pairCounts = new Map<string, number>();

    for (const order of orders) {
      const productIds = order.lineItems.map((item) => item.productId);

      // Generate all pairs of products in this order
      // For bundles of size 3+, we would need more complex algorithms
      for (let i = 0; i < productIds.length; i++) {
        for (let j = i + 1; j < productIds.length; j++) {
          const pair = [productIds[i], productIds[j]].sort().join("|");
          pairCounts.set(pair, (pairCounts.get(pair) || 1) + 1);
        }
      }
    }

    return pairCounts;
  }

  /**
   * Extract product bundles from pairs
   */
  private extractProductBundles(
    pairCounts: Map<string, number>,
    orders: ProcessedOrder[],
  ): Bundle[] {
    const bundles: Bundle[] = [];
    const totalOrders = orders.length;

    // Calculate individual product frequencies and average prices
    const productFrequencies = new Map<string, number>();
    const productPrices = new Map<string, number>();

    for (const order of orders) {
      for (const item of order.lineItems) {
        // Update frequency
        productFrequencies.set(
          item.productId,
          (productFrequencies.get(item.productId) || 0) + 1,
        );

        // Calculate average price for this product
        const currentTotal = productPrices.get(item.productId) || 0;
        const currentCount = productFrequencies.get(item.productId) || 0;
        const newTotal = currentTotal + item.price * item.quantity;
        productPrices.set(item.productId, newTotal);
      }
    }

    // Calculate average prices
    for (const [productId, totalPrice] of productPrices) {
      const frequency = productFrequencies.get(productId) || 1;
      productPrices.set(productId, totalPrice / frequency);
    }

    // Process each pair
    for (const [pair, coPurchaseCount] of pairCounts) {
      const [productId1, productId2] = pair.split("|");

      const support = coPurchaseCount / totalOrders;
      const confidence1 =
        coPurchaseCount / (productFrequencies.get(productId1) || 1);
      const confidence2 =
        coPurchaseCount / (productFrequencies.get(productId2) || 1);
      const lift1 =
        confidence1 / ((productFrequencies.get(productId2) || 1) / totalOrders);
      const lift2 =
        confidence2 / ((productFrequencies.get(productId1) || 1) / totalOrders);

      // Use the better confidence and lift values
      const confidence = Math.max(confidence1, confidence2);
      const lift = Math.max(lift1, lift2);

      // Apply thresholds
      if (
        support >= this.config.minSupport &&
        confidence >= this.config.minConfidence &&
        lift >= this.config.minLift
      ) {
        // Calculate actual revenue for this bundle
        const { revenue, avgOrderValue } = this.calculateBundleRevenue(
          productId1,
          productId2,
          coPurchaseCount,
          productPrices,
        );

        const bundle: Bundle = {
          id: `bundle-${productId1}-${productId2}`,
          productIds: [productId1, productId2],
          coPurchaseCount,
          confidence,
          lift,
          support,
          revenue,
          avgOrderValue,
          strength: this.calculateBundleStrength(confidence, lift),
          strengthColor: this.getStrengthColor(confidence, lift),
        };

        bundles.push(bundle);
      }
    }

    // Sort by confidence and lift
    return bundles.sort((a, b) => {
      const scoreA = a.confidence * a.lift;
      const scoreB = b.confidence * b.lift;
      return scoreB - scoreA;
    });
  }

  /**
   * Calculate bundle strength based on confidence and lift
   */
  private calculateBundleStrength(
    confidence: number,
    lift: number,
  ): "Strong" | "Medium" | "Weak" {
    const score = confidence * lift;

    if (score >= 0.5) return "Strong";
    if (score >= 0.2) return "Medium";
    return "Weak";
  }

  /**
   * Get color for bundle strength
   */
  private getStrengthColor(confidence: number, lift: number): string {
    const strength = this.calculateBundleStrength(confidence, lift);

    switch (strength) {
      case "Strong":
        return "#52c41a";
      case "Medium":
        return "#faad14";
      case "Weak":
        return "#ff4d4f";
      default:
        return "#d9d9d9";
    }
  }

  /**
   * Calculate summary statistics
   */
  private calculateSummary(bundles: Bundle[]) {
    if (bundles.length === 0) {
      return {
        totalBundles: 0,
        totalRevenue: 0,
        avgConfidence: 0,
        avgLift: 0,
        avgBundleValue: 0,
      };
    }

    const totalRevenue = bundles.reduce(
      (sum, bundle) => sum + bundle.revenue,
      0,
    );
    const avgConfidence =
      bundles.reduce((sum, bundle) => sum + bundle.confidence, 0) /
      bundles.length;
    const avgLift =
      bundles.reduce((sum, bundle) => sum + bundle.lift, 0) / bundles.length;
    const avgBundleValue =
      bundles.reduce((sum, bundle) => sum + bundle.avgOrderValue, 0) /
      bundles.length;

    return {
      totalBundles: bundles.length,
      totalRevenue,
      avgConfidence,
      avgLift,
      avgBundleValue,
    };
  }

  /**
   * Calculate actual revenue for a bundle based on product prices
   */
  private calculateBundleRevenue(
    productId1: string,
    productId2: string,
    coPurchaseCount: number,
    productPrices: Map<string, number>,
  ): { revenue: number; avgOrderValue: number } {
    const product1Price = productPrices.get(productId1) || 0;
    const product2Price = productPrices.get(productId2) || 0;
    const bundlePrice = product1Price + product2Price;
    const actualRevenue = coPurchaseCount * bundlePrice;

    return {
      revenue: actualRevenue,
      avgOrderValue: bundlePrice,
    };
  }

  /**
   * TODO: Future enhancement - Extract larger bundles (size 3+)
   *
   * This would require implementing Apriori or FP-Growth algorithms:
   * 1. Apriori: Uses candidate generation and pruning
   * 2. FP-Growth: Uses frequent pattern trees
   *
   * For now, we focus on pairs (size 2) which provide good insights
   * and are computationally efficient for MVP.
   */
  private extractLargerBundles(
    orders: ProcessedOrder[],
    minSize: number = 3,
    maxSize: number = 4,
  ): Map<string, number> {
    // TODO: Implement Apriori or FP-Growth algorithm
    // This is a placeholder for future enhancement
    console.log(
      `TODO: Implement larger bundle extraction (${minSize}-${maxSize})`,
    );
    return new Map();
  }
}
