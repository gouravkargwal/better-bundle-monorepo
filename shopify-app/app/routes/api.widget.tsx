import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { prisma } from "../core/database/prisma.server";

// Helper function to add CORS headers to JSON responses
const jsonWithCors = (data: any, init?: ResponseInit) => {
  return json(data, {
    ...init,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
      ...init?.headers,
    },
  });
};

export const loader = async ({ request }: LoaderFunctionArgs) => {
  console.log("API Widget endpoint called");

  // Handle CORS preflight requests
  if (request.method === "OPTIONS") {
    return new Response(null, {
      status: 200,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Max-Age": "86400",
      },
    });
  }

  try {
    // Check for App Bridge session token
    const authHeader = request.headers.get("Authorization");
    let isAuthenticated = false;

    if (authHeader && authHeader.startsWith("Bearer ")) {
      const token = authHeader.substring(7);
      console.log("App Bridge token received:", token.substring(0, 10) + "...");
      // In production, you would validate this token with Shopify
      isAuthenticated = true;
    }

    console.log("Request authenticated:", isAuthenticated);
    const url = new URL(request.url);
    const productId = url.searchParams.get("productId");
    const shopDomain = url.searchParams.get("shopDomain");

    if (!productId || !shopDomain) {
      return jsonWithCors(
        {
          success: false,
          error: "Missing required parameters: productId and shopDomain",
        },
        { status: 400 },
      );
    }

    // Find the shop by domain
    const shop = await prisma.shop.findFirst({
      where: { shopDomain },
    });

    if (!shop) {
      return jsonWithCors(
        {
          success: false,
          error: "Shop not found",
        },
        { status: 404 },
      );
    }

    // Convert numeric product ID to Shopify GraphQL format if needed
    const shopifyProductId = productId.includes("gid://")
      ? productId
      : `gid://shopify/Product/${productId}`;

    console.log(`Looking for product ID: ${shopifyProductId}`);

    // Find the best bundle recommendation for this product
    const bundleRecommendation = await prisma.bundleAnalysisResult.findFirst({
      where: {
        shopId: shop.id,
        productIds: {
          has: shopifyProductId,
        },
        isActive: true,
      },
      orderBy: [{ confidence: "desc" }, { lift: "desc" }, { revenue: "desc" }],
    });

    if (!bundleRecommendation) {
      return jsonWithCors(
        {
          success: false,
          message: "No bundle recommendations found for this product",
        },
        { status: 404 },
      );
    }

    // Get the bundle partner product (the other product in the bundle)
    const bundleProductId = bundleRecommendation.productIds.find(
      (id: string) => id !== shopifyProductId,
    );

    if (!bundleProductId) {
      return jsonWithCors(
        {
          success: false,
          error: "Invalid bundle configuration",
        },
        { status: 500 },
      );
    }

    // Get the bundle partner product details
    const bundleProduct = await prisma.productData.findFirst({
      where: {
        shopId: shop.id,
        productId: bundleProductId,
      },
    });

    if (!bundleProduct) {
      return jsonWithCors(
        {
          success: false,
          error: "Bundle product not found",
        },
        { status: 404 },
      );
    }

    // Get the main product details for pricing
    const mainProduct = await prisma.productData.findFirst({
      where: {
        shopId: shop.id,
        productId: shopifyProductId,
      },
    });

    if (!mainProduct) {
      return jsonWithCors(
        {
          success: false,
          error: "Main product not found",
        },
        { status: 404 },
      );
    }

    // Calculate bundle pricing
    const mainProductPrice = parseFloat(mainProduct.price) || 0;
    const bundleProductPrice = parseFloat(bundleProduct.price) || 0;
    const bundleTotal = mainProductPrice + bundleProductPrice;

    // Get store currency from shop data or detect from domain
    let storeCurrency = shop.currencyCode || "INR";
    let storeLocale = "en-IN";

    // Detect currency from shop domain
    if (shopDomain.includes(".myshopify.com")) {
      // For Indian stores, default to INR
      if (shopDomain.includes(".in") || shopDomain.includes("vnsaid")) {
        storeCurrency = "INR";
        storeLocale = "en-IN";
      }
    }

    // Format prices with store's currency
    const formatPrice = (price: number) => {
      try {
        return new Intl.NumberFormat(storeLocale, {
          style: "currency",
          currency: storeCurrency,
        }).format(price);
      } catch (error) {
        // Fallback to INR if currency formatting fails
        return new Intl.NumberFormat("en-IN", {
          style: "currency",
          currency: "INR",
        }).format(price);
      }
    };

    const bundle = {
      id: bundleProduct.productId,
      title: bundleProduct.title,
      price: formatPrice(bundleProductPrice),
      imageUrl: bundleProduct.imageUrl || null,
      imageAlt: bundleProduct.imageAlt || bundleProduct.title,
      bundlePrice: formatPrice(bundleTotal),
      confidence: bundleRecommendation.confidence,
      lift: bundleRecommendation.lift,
      coPurchaseCount: bundleRecommendation.coPurchaseCount,
    };

    return jsonWithCors({
      success: true,
      bundle,
      metadata: {
        confidence: bundleRecommendation.confidence,
        lift: bundleRecommendation.lift,
        coPurchaseCount: bundleRecommendation.coPurchaseCount,
        revenue: bundleRecommendation.revenue,
      },
    });
  } catch (error) {
    console.error("Error in widget API:", error);
    return jsonWithCors(
      {
        success: false,
        error: "Internal server error",
      },
      { status: 500 },
    );
  }
};
