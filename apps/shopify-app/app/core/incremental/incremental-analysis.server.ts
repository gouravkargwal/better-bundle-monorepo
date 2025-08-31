import { prisma } from '../database/prisma.server';

export interface DataChangeSummary {
  newOrders: any[];
  newProducts: any[];
  removedProducts: string[];
  updatedProducts: any[];
  timeRange: {
    since: Date;
    until: Date;
  };
  changePercentage: number;
}

export interface IncrementalAnalysisResult {
  existingBundles: any[];
  newBundles: any[];
  updatedBundles: any[];
  removedBundles: any[];
  finalBundles: any[];
  dataChangeSummary: DataChangeSummary;
}

export class IncrementalAnalysisService {
  /**
   * Detect what data has changed since last analysis
   */
  static async detectDataChanges(shopId: string): Promise<DataChangeSummary> {
    try {
      console.log(`🔍 Detecting data changes for shop: ${shopId}`);

      // Get last analysis date
      const lastAnalysis = await prisma.analysisJob.findFirst({
        where: { shopId, status: 'completed' },
        orderBy: { completedAt: 'desc' },
      });

      const lastAnalysisDate = lastAnalysis?.completedAt || new Date(0);
      const now = new Date();

      // Get new orders since last analysis
      const newOrders = await prisma.orderData.findMany({
        where: {
          shopId,
          orderDate: { gt: lastAnalysisDate },
        },
        orderBy: { orderDate: 'desc' },
      });

      // Get new products since last analysis
      const newProducts = await prisma.productData.findMany({
        where: {
          shopId,
          createdAt: { gt: lastAnalysisDate },
        },
      });

      // Get updated products (simplified - in real implementation you'd track product changes)
      const updatedProducts: any[] = [];

      // Get removed products (simplified - in real implementation you'd track product removals)
      const removedProducts: string[] = [];

      // Calculate change percentage
      const totalOrders = await prisma.orderData.count({ where: { shopId } });
      const changePercentage = totalOrders > 0 ? newOrders.length / totalOrders : 0;

      const summary: DataChangeSummary = {
        newOrders,
        newProducts,
        removedProducts,
        updatedProducts,
        timeRange: {
          since: lastAnalysisDate,
          until: now,
        },
        changePercentage,
      };

      console.log(`📊 Data change summary: ${newOrders.length} new orders, ${newProducts.length} new products, ${(changePercentage * 100).toFixed(1)}% change`);

      return summary;
    } catch (error) {
      console.error('Error detecting data changes:', error);
      throw error;
    }
  }

  /**
   * Determine if incremental analysis is beneficial
   */
  static async shouldUseIncrementalAnalysis(shopId: string): Promise<boolean> {
    try {
      const dataChanges = await this.detectDataChanges(shopId);
      
      // Use incremental if:
      // 1. Change is less than 50% of total data
      // 2. We have existing bundles
      // 3. Last analysis was recent (within 30 days)
      
      const hasExistingBundles = await this.hasExistingBundles(shopId);
      const isRecentAnalysis = dataChanges.timeRange.since > new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
      const isSmallChange = dataChanges.changePercentage < 0.5;

      const shouldUseIncremental = hasExistingBundles && isRecentAnalysis && isSmallChange;

      console.log(`🤔 Incremental analysis decision: ${shouldUseIncremental ? 'YES' : 'NO'} (change: ${(dataChanges.changePercentage * 100).toFixed(1)}%, has bundles: ${hasExistingBundles}, recent: ${isRecentAnalysis})`);

      return shouldUseIncremental;
    } catch (error) {
      console.error('Error determining incremental analysis:', error);
      return false; // Fallback to full analysis
    }
  }

  /**
   * Check if shop has existing bundles
   */
  private static async hasExistingBundles(shopId: string): Promise<boolean> {
    const bundleCount = await prisma.bundleAnalysisResult.count({
      where: { shopId, isActive: true },
    });
    return bundleCount > 0;
  }

  /**
   * Prepare data for incremental analysis
   */
  static async prepareIncrementalData(shopId: string): Promise<any> {
    try {
      console.log(`📋 Preparing incremental data for shop: ${shopId}`);

      const dataChanges = await this.detectDataChanges(shopId);
      
      // Get existing bundles
      const existingBundles = await prisma.bundleAnalysisResult.findMany({
        where: { shopId, isActive: true },
      });

      // Get all products (for context)
      const allProducts = await prisma.productData.findMany({
        where: { shopId },
      });

      // Get recent orders (last 90 days for context)
      const ninetyDaysAgo = new Date();
      ninetyDaysAgo.setDate(ninetyDaysAgo.getDate() - 90);
      
      const recentOrders = await prisma.orderData.findMany({
        where: {
          shopId,
          orderDate: { gte: ninetyDaysAgo },
        },
        orderBy: { orderDate: 'desc' },
      });

      return {
        existingBundles,
        newOrders: dataChanges.newOrders,
        newProducts: dataChanges.newProducts,
        allProducts,
        recentOrders,
        dataChanges,
      };
    } catch (error) {
      console.error('Error preparing incremental data:', error);
      throw error;
    }
  }

  /**
   * Update existing bundles with new data
   */
  static async updateExistingBundles(
    existingBundles: any[],
    newOrders: any[],
    newProducts: any[]
  ): Promise<any[]> {
    try {
      console.log(`🔄 Updating ${existingBundles.length} existing bundles with new data`);

      const updatedBundles = [];

      for (const bundle of existingBundles) {
        // Check if bundle products are still available
        const bundleProducts = bundle.productIds;
        const availableProducts = await this.getAvailableProducts(bundleProducts);
        
        if (availableProducts.length < 2) {
          // Bundle has insufficient products, mark for removal
          continue;
        }

        // Update bundle metrics with new data
        const updatedMetrics = await this.calculateUpdatedBundleMetrics(
          bundle,
          newOrders,
          newProducts
        );

        // Check if bundle still meets minimum thresholds
        if (this.bundleStillValid(updatedMetrics)) {
          updatedBundles.push({
            ...bundle,
            ...updatedMetrics,
            lastUpdated: new Date(),
          });
        }
      }

      console.log(`✅ Updated ${updatedBundles.length} bundles`);
      return updatedBundles;
    } catch (error) {
      console.error('Error updating existing bundles:', error);
      throw error;
    }
  }

  /**
   * Find new bundles from new data
   */
  static async findNewBundles(
    newOrders: any[],
    allProducts: any[],
    existingBundles: any[]
  ): Promise<any[]> {
    try {
      console.log(`🔍 Finding new bundles from ${newOrders.length} new orders`);

      if (newOrders.length < 5) {
        console.log('⚠️ Insufficient new orders for bundle discovery');
        return [];
      }

      // Extract product pairs from new orders
      const productPairs = this.extractProductPairs(newOrders);
      
      // Calculate bundle metrics for new pairs
      const newBundles = [];
      
      for (const pair of productPairs) {
        const bundleMetrics = await this.calculateBundleMetrics(pair, newOrders, allProducts);
        
        if (this.bundleMeetsThresholds(bundleMetrics)) {
          // Check if this bundle doesn't already exist
          const isNewBundle = !this.bundleExists(pair, existingBundles);
          
          if (isNewBundle) {
            newBundles.push({
              productIds: pair,
              ...bundleMetrics,
              createdAt: new Date(),
              isActive: true,
            });
          }
        }
      }

      console.log(`✅ Found ${newBundles.length} new bundles`);
      return newBundles;
    } catch (error) {
      console.error('Error finding new bundles:', error);
      throw error;
    }
  }

  /**
   * Extract product pairs from orders
   */
  private static extractProductPairs(orders: any[]): string[][] {
    const pairs = new Set<string>();
    
    for (const order of orders) {
      const lineItems = order.lineItems as any[];
      const productIds = lineItems.map(item => item.product?.id).filter(Boolean);
      
      // Generate all pairs
      for (let i = 0; i < productIds.length; i++) {
        for (let j = i + 1; j < productIds.length; j++) {
          const pair = [productIds[i], productIds[j]].sort();
          pairs.add(pair.join('|'));
        }
      }
    }
    
    return Array.from(pairs).map(pair => pair.split('|'));
  }

  /**
   * Calculate bundle metrics
   */
  private static async calculateBundleMetrics(
    productPair: string[],
    orders: any[],
    allProducts: any[]
  ): Promise<any> {
    // Simplified calculation - in real implementation, you'd use the ML API
    const coPurchaseCount = this.countCoPurchases(productPair, orders);
    const totalOrders = orders.length;
    
    const support = totalOrders > 0 ? coPurchaseCount / totalOrders : 0;
    const confidence = 0.6; // Simplified
    const lift = 1.5; // Simplified
    
    return {
      coPurchaseCount,
      support,
      confidence,
      lift,
      revenue: coPurchaseCount * 50, // Simplified revenue calculation
    };
  }

  /**
   * Count co-purchases for a product pair
   */
  private static countCoPurchases(productPair: string[], orders: any[]): number {
    let count = 0;
    
    for (const order of orders) {
      const lineItems = order.lineItems as any[];
      const orderProductIds = lineItems.map(item => item.product?.id).filter(Boolean);
      
      if (productPair.every(productId => orderProductIds.includes(productId))) {
        count++;
      }
    }
    
    return count;
  }

  /**
   * Check if bundle meets minimum thresholds
   */
  private static bundleMeetsThresholds(metrics: any): boolean {
    return (
      metrics.support >= 0.01 && // 1% support
      metrics.confidence >= 0.3 && // 30% confidence
      metrics.lift >= 1.2 && // 1.2 lift
      metrics.coPurchaseCount >= 2 // At least 2 co-purchases
    );
  }

  /**
   * Check if bundle still valid after updates
   */
  private static bundleStillValid(metrics: any): boolean {
    return this.bundleMeetsThresholds(metrics);
  }

  /**
   * Check if bundle already exists
   */
  private static bundleExists(productPair: string[], existingBundles: any[]): boolean {
    const pairSet = new Set(productPair);
    
    return existingBundles.some(bundle => {
      const bundleSet = new Set(bundle.productIds);
      return bundleSet.size === pairSet.size && 
             Array.from(bundleSet).every(id => pairSet.has(id));
    });
  }

  /**
   * Get available products
   */
  private static async getAvailableProducts(productIds: string[]): Promise<string[]> {
    // In real implementation, check product availability
    return productIds.filter(id => id); // Simplified
  }

  /**
   * Calculate updated bundle metrics
   */
  private static async calculateUpdatedBundleMetrics(
    bundle: any,
    newOrders: any[],
    newProducts: any[]
  ): Promise<any> {
    // Simplified update - in real implementation, you'd recalculate with new data
    const newCoPurchases = this.countCoPurchases(bundle.productIds, newOrders);
    
    return {
      coPurchaseCount: bundle.coPurchaseCount + newCoPurchases,
      support: bundle.support * 0.9 + (newCoPurchases / newOrders.length) * 0.1, // Weighted average
      confidence: bundle.confidence,
      lift: bundle.lift,
      revenue: bundle.revenue + newCoPurchases * 50,
    };
  }

  /**
   * Merge incremental results with existing results
   */
  static async mergeIncrementalResults(
    existingBundles: any[],
    newBundles: any[],
    updatedBundles: any[]
  ): Promise<any[]> {
    try {
      console.log(`🔗 Merging incremental results: ${existingBundles.length} existing, ${newBundles.length} new, ${updatedBundles.length} updated`);

      // Create a map of existing bundles by product IDs
      const existingBundleMap = new Map();
      existingBundles.forEach(bundle => {
        const key = bundle.productIds.sort().join('|');
        existingBundleMap.set(key, bundle);
      });

      // Update existing bundles
      updatedBundles.forEach(bundle => {
        const key = bundle.productIds.sort().join('|');
        existingBundleMap.set(key, bundle);
      });

      // Add new bundles
      newBundles.forEach(bundle => {
        const key = bundle.productIds.sort().join('|');
        if (!existingBundleMap.has(key)) {
          existingBundleMap.set(key, bundle);
        }
      });

      const finalBundles = Array.from(existingBundleMap.values());

      console.log(`✅ Merged into ${finalBundles.length} final bundles`);
      return finalBundles;
    } catch (error) {
      console.error('Error merging incremental results:', error);
      throw error;
    }
  }

  /**
   * Store incremental analysis results
   */
  static async storeIncrementalResults(
    shopId: string,
    finalBundles: any[],
    dataChangeSummary: DataChangeSummary
  ): Promise<void> {
    try {
      console.log(`💾 Storing incremental analysis results for shop: ${shopId}`);

      // Clear existing bundles
      await prisma.bundleAnalysisResult.deleteMany({
        where: { shopId },
      });

      // Store new bundles
      if (finalBundles.length > 0) {
        const bundleData = finalBundles.map(bundle => ({
          shopId,
          productIds: bundle.productIds,
          bundleSize: bundle.productIds.length,
          coPurchaseCount: bundle.coPurchaseCount,
          confidence: bundle.confidence,
          lift: bundle.lift,
          support: bundle.support,
          revenue: bundle.revenue,
          discount: 0,
          isActive: true,
        }));

        await prisma.bundleAnalysisResult.createMany({
          data: bundleData,
        });
      }

      // Log incremental analysis
      await prisma.incrementalAnalysisLog.create({
        data: {
          shopId,
          bundlesCount: finalBundles.length,
          newOrdersCount: dataChangeSummary.newOrders.length,
          newProductsCount: dataChangeSummary.newProducts.length,
          changePercentage: dataChangeSummary.changePercentage,
          analysisType: 'incremental',
        },
      });

      console.log(`✅ Incremental results stored successfully`);
    } catch (error) {
      console.error('Error storing incremental results:', error);
      throw error;
    }
  }

  /**
   * Perform complete incremental analysis
   */
  static async performIncrementalAnalysis(shopId: string): Promise<IncrementalAnalysisResult> {
    try {
      console.log(`🚀 Starting incremental analysis for shop: ${shopId}`);

      // Detect data changes
      const dataChanges = await this.detectDataChanges(shopId);

      // Prepare incremental data
      const incrementalData = await this.prepareIncrementalData(shopId);

      // Update existing bundles
      const updatedBundles = await this.updateExistingBundles(
        incrementalData.existingBundles,
        dataChanges.newOrders,
        dataChanges.newProducts
      );

      // Find new bundles
      const newBundles = await this.findNewBundles(
        dataChanges.newOrders,
        incrementalData.allProducts,
        incrementalData.existingBundles
      );

      // Merge results
      const finalBundles = await this.mergeIncrementalResults(
        incrementalData.existingBundles,
        newBundles,
        updatedBundles
      );

      // Store results
      await this.storeIncrementalResults(shopId, finalBundles, dataChanges);

      const result: IncrementalAnalysisResult = {
        existingBundles: incrementalData.existingBundles,
        newBundles,
        updatedBundles,
        removedBundles: incrementalData.existingBundles.filter(b => 
          !updatedBundles.some(ub => ub.id === b.id)
        ),
        finalBundles,
        dataChangeSummary: dataChanges,
      };

      console.log(`✅ Incremental analysis completed: ${finalBundles.length} bundles (${newBundles.length} new, ${updatedBundles.length} updated)`);

      return result;
    } catch (error) {
      console.error('Error performing incremental analysis:', error);
      throw error;
    }
  }
}
