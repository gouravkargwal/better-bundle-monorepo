import { json, type LoaderFunctionArgs } from "@remix-run/node";
import prisma from "../db.server";

// Helper function to generate recommendation reasons
function getRecommendationReason(index: number, context: string): string {
  const reasons = [
    "Frequently bought together",
    "Similar products",
    "Popular choice",
    "Perfect match",
    "Essential accessory",
    "Customers also viewed",
    "Trending now",
    "Best seller",
    "Recommended for you",
    "Complete the look",
  ];

  // Use context-specific reasons for certain contexts
  if (context === "cart") {
    const cartReasons = [
      "Frequently bought together",
      "Complete your order",
      "Perfect addition",
      "Customers also added",
    ];
    return cartReasons[index % cartReasons.length];
  }

  if (context === "product_page") {
    const productReasons = [
      "Similar products",
      "Frequently bought together",
      "Perfect match",
      "Customers also viewed",
    ];
    return productReasons[index % productReasons.length];
  }

  return reasons[index % reasons.length];
}

// Public API route for recommendations (no authentication required)
export const loader = async ({ request }: LoaderFunctionArgs) => {
  // Get query parameters
  const url = new URL(request.url);
  const context = url.searchParams.get("context") || "product_page";
  const productId = url.searchParams.get("product_id");
  const userId = url.searchParams.get("user_id");
  const sessionId = url.searchParams.get("session_id");
  const limit = parseInt(url.searchParams.get("limit") || "6");

  console.log("🌐 Public API Recommendations called:", {
    context,
    productId,
    userId,
    sessionId,
    limit,
    url: request.url,
    origin: request.headers.get("origin"),
    timestamp: new Date().toISOString(),
  });

  // Extract shop domain from origin header
  const origin = request.headers.get("origin");
  let shopDomain = "test-shop.myshopify.com";

  if (origin && origin.includes(".myshopify.com")) {
    shopDomain = origin.replace("https://", "");
    console.log("✅ Using shop domain from origin:", shopDomain);
  }

  try {
    // Get shop information from database
    const shop = await prisma.shop.findUnique({ where: { shopDomain } });
    if (!shop) {
      console.log("⚠️ Shop not found for domain:", shopDomain);
      return json(
        {
          success: false,
          error: "Shop not found",
          message: "No shop found for the provided domain",
          recommendations: [],
        },
        { status: 404 },
      );
    }

    if (!shop.accessToken) {
      console.log("⚠️ No access token for shop:", shopDomain);
      return json(
        {
          success: false,
          error: "No access token",
          message: "Shop has no access token configured",
          recommendations: [],
        },
        { status: 401 },
      );
    }

    console.log("🏪 Found shop with access token for domain:", shopDomain);

    // GraphQL query to fetch products from Shopify using shop's access token
    const PRODUCTS_QUERY = `
      query getProducts($first: Int!) {
        products(first: $first, query: "status:active") {
          nodes {
            id
            title
            handle
            description
            productType
            vendor
            status
            totalInventory
            images(first: 1) {
              nodes {
                url
                altText
              }
            }
            variants(first: 1) {
              nodes {
                price
                compareAtPrice
              }
            }
          }
        }
      }
    `;

    // Make direct GraphQL request to Shopify using shop's access token
    const shopifyUrl = `https://${shopDomain}/admin/api/2025-01/graphql.json`;
    const response = await fetch(shopifyUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": shop.accessToken,
      },
      body: JSON.stringify({
        query: PRODUCTS_QUERY,
        variables: { first: limit },
      }),
    });

    if (!response.ok) {
      console.error(
        "❌ Shopify API error:",
        response.status,
        response.statusText,
      );
      throw new Error(`Shopify API error: ${response.status}`);
    }

    const responseJson = (await response.json()) as any;

    if (responseJson.errors) {
      console.error("❌ GraphQL errors:", responseJson.errors);
      throw new Error("GraphQL query failed");
    }

    const products = responseJson.data?.products?.nodes || [];
    console.log(`📦 Found ${products.length} products from Shopify`);

    // Format products to match expected API structure
    const formattedProducts = products.map((product: any, index: number) => {
      const variant = product.variants?.nodes?.[0];
      const image = product.images?.nodes?.[0];

      return {
        id: product.id.replace("gid://shopify/Product/", ""),
        title: product.title,
        handle: product.handle,
        price: variant?.price?.amount || "0.00",
        currency: variant?.price?.currencyCode || "USD",
        compareAtPrice: variant?.compareAtPrice?.amount || null,
        compareAtPriceCurrency: variant?.compareAtPrice?.currencyCode || null,
        image:
          image?.url ||
          `data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzAwIiBoZWlnaHQ9IjMwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjBmMGYwIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPk5vIEltYWdlPC90ZXh0Pjwvc3ZnPg==`,
        imageAlt: image?.altText || product.title,
        productType: product.productType,
        vendor: product.vendor,
        inventory: product.totalInventory,
        reason: getRecommendationReason(index, context),
      };
    });

    console.log(
      `✅ Returning ${formattedProducts.length} formatted products from Shopify`,
    );

    return json(
      {
        success: true,
        recommendations: formattedProducts,
        context,
        source: "shopify-graphql",
        count: formattedProducts.length,
        shopDomain,
        shopId: shop.id,
        message: "Real products from Shopify GraphQL",
        timestamp: new Date().toISOString(),
      },
      {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization",
          "Access-Control-Max-Age": "86400",
        },
      },
    );
  } catch (error) {
    console.error("❌ Error fetching products from Shopify:", error);
    return json(
      {
        success: false,
        error: "Shopify API error",
        message: "Failed to fetch products from Shopify",
        recommendations: [],
      },
      { status: 500 },
    );
  }
};

// Handle OPTIONS requests for CORS preflight
export const action = async ({ request }: LoaderFunctionArgs) => {
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

  return json({ error: "Method not allowed" }, { status: 405 });
};
