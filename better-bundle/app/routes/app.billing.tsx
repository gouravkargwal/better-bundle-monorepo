import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { BillingService } from "../features/billing/services/billing.service";
import { TabbedBillingPage } from "../features/billing/components/TabbedBillingPage";
import logger from "../utils/logger";

export async function loader({ request }: LoaderFunctionArgs) {
  const { session, admin } = await authenticate.admin(request);
  const { shop } = session;

  try {
    // Get shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true, currency_code: true },
    });

    if (!shopRecord) {
      throw new Error("Shop not found");
    }

    // ✅ Get billing state with admin context for Shopify API calls
    const billingState = await BillingService.getBillingState(
      shopRecord.id,
      admin,
    );
    console.log("billingState", billingState);

    // Check URL parameters for callback status
    const url = new URL(request.url);
    const subscriptionStatus = url.searchParams.get("subscription");

    return json({
      shopId: shopRecord.id,
      shopCurrency: shopRecord.currency_code || "USD",
      billingState,
      subscriptionStatus, // Pass the status to the component
    });
  } catch (error) {
    logger.error({ error, shop }, "Billing loader error");
    return json({
      error: "Failed to load billing data",
    });
  }
}

export default function BillingPage() {
  const loaderData = useLoaderData<typeof loader>();

  if ("error" in loaderData) {
    return (
      <div style={{ padding: "24px", textAlign: "center" }}>
        <p>Error: {loaderData.error}</p>
      </div>
    );
  }

  const { shopId, shopCurrency, billingState, subscriptionStatus } = loaderData;

  return (
    <TabbedBillingPage
      shopId={shopId}
      shopCurrency={shopCurrency}
      billingState={billingState}
      subscriptionStatus={subscriptionStatus}
    />
  );
}
