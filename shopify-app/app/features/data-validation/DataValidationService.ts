import { prisma } from "../../core/database/prisma.server";
import { 
  NoOrdersError, 
  InsufficientDataError, 
  NoProductsError,
  ValidationError 
} from "../../core/errors/AppError";
import type { DataValidationResult, StoreStats } from "../../types";
import { 
  ANALYSIS_CONFIG, 
  ERROR_MESSAGES, 
  RECOMMENDATIONS,
  SUCCESS_MESSAGES 
} from "../../constants";

export class DataValidationService {
  /**
   * Validate if store has sufficient data for analysis
   */
  async validateStoreData(shopId: string): Promise<DataValidationResult> {
    try {
  

      // Find the internal shop ID
      const shop = await prisma.shop.findUnique({
        where: { shopId },
        select: { id: true },
      });

      if (!shop) {
        console.log(`❌ Shop not found in database: ${shopId}`);
        return {
          isValid: false,
          orderCount: 0,
          productCount: 0,
          error: "Shop not found in database. Please run data collection first.",
          errorType: "no-data",
          recommendations: [
            "Click 'Start Analysis' to collect your store data",
            "This will automatically set up your shop in our system",
            "Then you can run bundle analysis",
          ],
        };
      }

      const internalShopId = shop.id;
      console.log(`✅ Found internal shop ID: ${internalShopId}`);

      // Get counts
      const [orderCount, productCount] = await Promise.all([
        prisma.orderData.count({ where: { shopId: internalShopId } }),
        prisma.productData.count({ where: { shopId: internalShopId } }),
      ]);

      console.log(`📊 Store data: ${orderCount} orders, ${productCount} products`);

      // Validate data requirements
      if (orderCount === 0) {
        console.log(`❌ No orders found for shop: ${shopId}`);
        throw new NoOrdersError(ERROR_MESSAGES.NO_ORDERS);
      }

      if (orderCount < ANALYSIS_CONFIG.MIN_ORDERS_REQUIRED) {
        console.log(`⚠️ Insufficient orders for shop: ${shopId} (${orderCount} orders)`);
        throw new InsufficientDataError(ERROR_MESSAGES.INSUFFICIENT_DATA);
      }

      if (productCount < ANALYSIS_CONFIG.MIN_PRODUCTS_REQUIRED) {
        console.log(`⚠️ Not enough products for shop: ${shopId} (${productCount} products)`);
        throw new NoProductsError(ERROR_MESSAGES.NO_PRODUCTS);
      }

      console.log(`✅ Store validation passed for: ${shopId}`);
      return {
        isValid: true,
        orderCount,
        productCount,
        recommendations: [
          `Found ${orderCount} orders and ${productCount} products`,
          SUCCESS_MESSAGES.VALIDATION_PASSED,
        ],
      };
    } catch (error) {
      console.error(`❌ Error validating store data for ${shopId}:`, error);
      
      if (error instanceof NoOrdersError) {
        return {
          isValid: false,
          orderCount: 0,
          productCount: 0,
          error: error.message,
          errorType: error.errorType,
          recommendations: RECOMMENDATIONS.NO_ORDERS,
        };
      }

      if (error instanceof InsufficientDataError) {
        return {
          isValid: false,
          orderCount: 0,
          productCount: 0,
          error: error.message,
          errorType: error.errorType,
          recommendations: RECOMMENDATIONS.INSUFFICIENT_DATA,
        };
      }

      if (error instanceof NoProductsError) {
        return {
          isValid: false,
          orderCount: 0,
          productCount: 0,
          error: error.message,
          errorType: error.errorType,
          recommendations: RECOMMENDATIONS.NO_PRODUCTS,
        };
      }

      return {
        isValid: false,
        orderCount: 0,
        productCount: 0,
        error: ERROR_MESSAGES.VALIDATION_FAILED,
        errorType: "api-error",
        recommendations: RECOMMENDATIONS.GENERAL_ERROR,
      };
    }
  }

  /**
   * Get store statistics for display
   */
  async getStoreStats(shopId: string): Promise<StoreStats | null> {
    try {
      const shop = await prisma.shop.findUnique({
        where: { shopId },
        select: { id: true },
      });

      if (!shop) return null;

      const [orderCount, productCount, lastAnalysis] = await Promise.all([
        prisma.orderData.count({ where: { shopId: shop.id } }),
        prisma.productData.count({ where: { shopId: shop.id } }),
        prisma.bundleAnalysisResult.findFirst({
          where: { shopId: shop.id },
          orderBy: { analysisDate: "desc" },
          select: { analysisDate: true },
        }),
      ]);

      return {
        orderCount,
        productCount,
        lastAnalysisDate: lastAnalysis?.analysisDate,
        hasAnalysis: !!lastAnalysis,
      };
    } catch (error) {
      console.error("Error getting store stats:", error);
      return null;
    }
  }
}
