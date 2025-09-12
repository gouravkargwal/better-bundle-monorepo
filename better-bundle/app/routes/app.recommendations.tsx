import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";

// Mock recommendations for testing when Python worker is not available
function generateMockRecommendations(limit: number, context: string) {
  const mockProducts = [
    {
      id: "mock-1",
      title: "Premium Wireless Headphones",
      handle: "premium-wireless-headphones",
      price: "199.99",
      currency: "$",
      image: "https://via.placeholder.com/300x300?text=Headphones",
      reason: "Frequently bought together",
    },
    {
      id: "mock-2",
      title: "Smart Fitness Tracker",
      handle: "smart-fitness-tracker",
      price: "149.99",
      currency: "$",
      image: "https://via.placeholder.com/300x300?text=Fitness+Tracker",
      reason: "Similar products",
    },
    {
      id: "mock-3",
      title: "Bluetooth Speaker",
      handle: "bluetooth-speaker",
      price: "79.99",
      currency: "$",
      image: "https://via.placeholder.com/300x300?text=Speaker",
      reason: "Popular choice",
    },
    {
      id: "mock-4",
      title: "Wireless Charging Pad",
      handle: "wireless-charging-pad",
      price: "39.99",
      currency: "$",
      image: "https://via.placeholder.com/300x300?text=Charger",
      reason: "Perfect match",
    },
    {
      id: "mock-5",
      title: "Phone Case & Screen Protector",
      handle: "phone-case-screen-protector",
      price: "24.99",
      currency: "$",
      image: "https://via.placeholder.com/300x300?text=Phone+Case",
      reason: "Essential accessory",
    },
    {
      id: "mock-6",
      title: "Portable Power Bank",
      handle: "portable-power-bank",
      price: "49.99",
      currency: "$",
      image: "https://via.placeholder.com/300x300?text=Power+Bank",
      reason: "Customers also viewed",
    },
  ];

  // Return limited number of mock products
  return mockProducts.slice(0, Math.min(limit, mockProducts.length));
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  // Get query parameters
  const url = new URL(request.url);
  const context = url.searchParams.get("context") || "product_page";
  const productId = url.searchParams.get("product_id");
  const userId = url.searchParams.get("user_id");
  const sessionId = url.searchParams.get("session_id");
  const category = url.searchParams.get("category");
  const limit = parseInt(url.searchParams.get("limit") || "6");

  console.log("🎯 Recommendations API called:", {
    context,
    productId,
    userId,
    sessionId,
    limit,
    url: request.url,
  });

  // Get session from request context (this works for both admin and frontend)
  const { session } = await authenticate.admin(request);
  const shopDomain = session.shop;

  try {
    // Check if Python worker is available
    if (!process.env.PYTHON_WORKER_URL) {
      console.log("⚠️ Python worker not configured, returning mock data");
      return json({
        success: true,
        recommendations: generateMockRecommendations(limit, context),
        context,
        source: "mock",
        count: limit,
      });
    }

    // Call Python worker recommendations API
    const recommendationsResponse = await fetch(
      `${process.env.PYTHON_WORKER_URL}/api/v1/recommendations`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${process.env.PYTHON_WORKER_API_KEY}`,
        },
        body: JSON.stringify({
          shop_domain: shopDomain,
          context,
          product_id: productId,
          user_id: userId,
          session_id: sessionId,
          category,
          limit,
        }),
      },
    );

    if (!recommendationsResponse.ok) {
      throw new Error(
        `Recommendations API error: ${recommendationsResponse.status}`,
      );
    }

    const recommendationsData = await recommendationsResponse.json();

    // Python worker returns data in correct format - no transformation needed
    return json(
      {
        success: recommendationsData.success,
        recommendations: recommendationsData.recommendations || [],
        context: recommendationsData.context,
        source: recommendationsData.source || "unknown",
        count: recommendationsData.count || 0,
      },
      {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
      },
    );
  } catch (error) {
    console.error("Recommendations error:", error);

    // Fallback to mock data for testing
    console.log("🔄 Falling back to mock recommendations");
    return json(
      {
        success: true,
        recommendations: generateMockRecommendations(limit, context),
        context,
        source: "fallback",
        count: limit,
      },
      {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
      },
    );
  }
};

export default function Recommendations() {
  // This route is primarily for API consumption by the theme extension
  // The actual UI rendering happens in the Liquid template
  return null;
}
