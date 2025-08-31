import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { BundleAnalyticsService } from "../features/bundle-analysis";
import { formatCurrency } from "../utils/currency.server";
import { prisma } from "../core/database/prisma.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  try {
    const { session } = await authenticate.admin(request);
    const shopDomain = session.shop;

    // First, find the internal shop ID and currency info
    const shop = await prisma.shop.findUnique({
      where: { shopDomain },
      select: {
        id: true,
        lastAnalysisAt: true,
        currencyCode: true,
        moneyFormat: true,
      },
    });

    if (!shop) {
      console.error(`Shop not found in database: ${shopDomain}`);
      return json({
        success: true,
        data: {
          bundles: [],
          analytics: {
            totalBundles: 0,
            totalRevenue: 0,
            avgConfidence: 0,
            lastAnalysis: null,
          },
          lastAnalysisAt: null,
        },
      });
    }

    const internalShopId = shop.id;

    // Get bundle analysis results using internal shop ID
    const bundles = await prisma.bundleAnalysisResult.findMany({
      where: {
        shopId: internalShopId,
        isActive: true,
      },
      orderBy: [{ confidence: "desc" }, { lift: "desc" }, { revenue: "desc" }],
      take: 50, // Limit to top 50 bundles
    });

    // Get shop analytics summary
    const analyticsService = new BundleAnalyticsService();
    const analytics = await analyticsService.getShopAnalytics(shopDomain);

    // Prepare currency config for formatting
    const currencyConfig = {
      currencyCode: shop?.currencyCode || "USD",
      moneyFormat: shop?.moneyFormat,
    };

    // If no bundles found, return empty array with last analysis info
    if (bundles.length === 0) {
      return json({
        success: true,
        data: {
          bundles: [],
          analytics: {
            totalBundles: 0,
            totalRevenue: 0,
            totalRevenueFormatted: formatCurrency(0, currencyConfig),
            avgConfidence: 0,
            lastAnalysis: shop?.lastAnalysisAt,
          },
          lastAnalysisAt: shop?.lastAnalysisAt,
          currencyConfig,
        },
      });
    }

    // Get product details for bundles
    const productIds = new Set<string>();
    bundles.forEach((bundle) => {
      bundle.productIds.forEach((id) => productIds.add(id));
    });

    const products = await prisma.productData.findMany({
      where: {
        shopId: internalShopId,
        productId: {
          in: Array.from(productIds),
        },
      },
    });

    // Create product lookup map
    const productMap = new Map(products.map((p) => [p.productId, p]));

    // Enhance bundles with product details, formatted prices, and business metrics
    const enhancedBundles = bundles.map((bundle) => {
      // Get all products in the bundle
      const bundleProducts = bundle.productIds
        .map((productId) => productMap.get(productId))
        .filter(Boolean);

      const totalPrice = bundleProducts.reduce(
        (sum, product) => sum + (product?.price || 0),
        0,
      );

      // Calculate business-friendly metrics
      const confidencePercent = Math.round(bundle.confidence * 100);
      const strength =
        bundle.lift >= 5.0 && bundle.confidence >= 0.4
          ? "Strong"
          : bundle.lift >= 2.0 && bundle.confidence >= 0.2
            ? "Medium"
            : "Weak";
      const strengthColor =
        strength === "Strong"
          ? "success"
          : strength === "Medium"
            ? "warning"
            : "critical";

      // Create dynamic customer behavior message based on bundle size
      const bundleSize = bundle.bundleSize || bundle.productIds.length;
      const customerBehavior =
        bundleSize === 2
          ? `${confidencePercent}% of customers who buy the first product also buy the second`
          : `${confidencePercent}% of customers buy all ${bundleSize} products together`;

      const businessInsight =
        strength === "Strong"
          ? `Excellent ${bundleSize}-product bundle opportunity! Consider displaying these products together.`
          : strength === "Medium"
            ? `Good ${bundleSize}-product potential. Try cross-selling these products on product pages.`
            : `Limited ${bundleSize}-product bundle potential. Focus on stronger combinations.`;

      return {
        ...bundle,
        // Keep legacy product1/product2 for backward compatibility
        product1: bundleProducts[0]
          ? {
              id: bundleProducts[0].productId,
              title: bundleProducts[0].title,
              price: bundleProducts[0].price,
              priceFormatted: formatCurrency(
                bundleProducts[0].price,
                currencyConfig,
              ),
              category: bundleProducts[0].category,
            }
          : null,
        product2: bundleProducts[1]
          ? {
              id: bundleProducts[1].productId,
              title: bundleProducts[1].title,
              price: bundleProducts[1].price,
              priceFormatted: formatCurrency(
                bundleProducts[1].price,
                currencyConfig,
              ),
              category: bundleProducts[1].category,
            }
          : null,
        // New products array for dynamic display
        products: bundleProducts.map((product) => ({
          id: product!.productId,
          title: product!.title,
          price: product!.price,
          priceFormatted: formatCurrency(product!.price, currencyConfig),
          category: product!.category,
          imageUrl: product!.imageUrl,
          imageAlt: product!.imageAlt,
        })),
        totalPrice,
        totalPriceFormatted: formatCurrency(totalPrice, currencyConfig),
        revenueFormatted: formatCurrency(bundle.revenue, currencyConfig),
        // Business-friendly metrics
        strength,
        strengthColor,
        customerBehavior,
        businessInsight,
        confidencePercent,
        savings: 0, // Will be calculated when bundle pricing is implemented
      };
    });

    return json({
      success: true,
      data: {
        bundles: enhancedBundles,
        analytics: {
          totalBundles: analytics.totalBundles,
          totalRevenue: analytics.totalRevenue,
          totalRevenueFormatted: formatCurrency(
            analytics.totalRevenue,
            currencyConfig,
          ),
          avgConfidence: analytics.avgConfidence,
          lastAnalysis: analytics.lastAnalysis?.lastAnalysisAt,
        },
        lastAnalysisAt: shop?.lastAnalysisAt,
        currencyConfig,
      },
    });
  } catch (error) {
    console.error("Error fetching bundle analysis results:", error);
    return json(
      {
        success: false,
        error: "Failed to fetch bundle analysis results",
      },
      { status: 500 },
    );
  }
};
