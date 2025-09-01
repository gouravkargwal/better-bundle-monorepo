/**
 * Billing API endpoint for performance-based billing calculations
 */

import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { performanceBillingService } from "../services/performance-billing.service";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  try {
    // Authenticate the request
    const { admin, session } = await authenticate.admin(request);
    
    if (!session?.shop) {
      return json({ error: "Shop not found" }, { status: 400 });
    }

    const shopDomain = session.shop;
    const url = new URL(request.url);
    const months = parseInt(url.searchParams.get("months") || "6");

    // Generate billing report
    const billingReport = await performanceBillingService.generateBillingReport(
      shopDomain,
      months
    );

    return json({
      success: true,
      shop_domain: shopDomain,
      period_months: months,
      ...billingReport
    });

  } catch (error) {
    console.error("Billing API error:", error);
    return json({ error: "Internal server error" }, { status: 500 });
  }
};
