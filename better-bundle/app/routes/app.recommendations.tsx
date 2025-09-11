import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  // Get query parameters
  const url = new URL(request.url);
  const context = url.searchParams.get("context") || "product_page";
  const productId = url.searchParams.get("product_id");
  const userId = url.searchParams.get("user_id");
  const sessionId = url.searchParams.get("session_id");
  const category = url.searchParams.get("category");
  const limit = parseInt(url.searchParams.get("limit") || "6");

  // Get shop domain from session
  const { session } = await authenticate.admin(request);
  const shopDomain = session.shop;

  try {
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
    return json({
      success: recommendationsData.success,
      recommendations: recommendationsData.recommendations || [],
      context: recommendationsData.context,
      source: recommendationsData.source || "unknown",
      count: recommendationsData.count || 0,
    });
  } catch (error) {
    console.error("Recommendations error:", error);

    // No fallback - return error response
    return json({
      success: false,
      recommendations: [],
      context,
      source: "error",
      error: error instanceof Error ? error.message : "Unknown error",
    });
  }
};

export default function Recommendations() {
  // This route is primarily for API consumption by the theme extension
  // The actual UI rendering happens in the Liquid template
  return null;
}
